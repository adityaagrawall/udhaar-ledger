"""Tests for the lane-based Today worklist (case study Section 6)."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.customer import Customer, RiskTier
from app.models.follow_up import FollowUp
from app.models.invoice import Invoice
from app.models.payment import Payment, PaymentAllocation
from app.services import today_service as ts

TODAY = date.today()


# --- The study's worked example (scored accounts only) -----------------------
@pytest.mark.parametrize(
    "overdue,pattern,days,recent,expected",
    [
        (200_000, "pays_on_its_own", 9, False, 80_000),      # Big Self-Payer
        (95_000, "pays_when_asked", 12, False, 95_000),      # Specimen Mart
        (48_000, "missed_promise", 35, False, 34_560),       # Example Kirana
        (60_000, "pays_on_its_own", 5, False, 12_000),       # Test General
        (30_000, "pays_when_asked", 40, True, 18_000),       # Model Provisions (called yesterday)
        (22_000, "thin_history", 18, False, 15_400),         # New Account
    ],
)
def test_score_matches_case_study_example(overdue, pattern, days, recent, expected):
    assert ts.compute_score(Decimal(overdue), pattern, days, recent) == pytest.approx(expected)


def test_lane_rules():
    assert ts.assign_lane(True, "pays_when_asked", 10) == "resolve"
    assert ts.assign_lane(False, "unresponsive", 62) == "escalate"
    assert ts.assign_lane(False, "pays_when_asked", 100) == "escalate"
    assert ts.assign_lane(False, "pays_when_asked", 90) is None


def test_pattern_detection():
    f = ts.AccountFacts(customer_id=None, name="x", phone=None)
    assert ts.detect_pattern(f, TODAY) == "thin_history"

    f.settled = [ts.SettledInvoice(TODAY - timedelta(days=60 + i), TODAY - timedelta(days=58 + i), False) for i in range(4)]
    assert ts.detect_pattern(f, TODAY) == "pays_on_its_own"

    f.contacts = [ts.Contact(TODAY - timedelta(days=10), False), ts.Contact(TODAY - timedelta(days=4), False)]
    assert ts.detect_pattern(f, TODAY) == "unresponsive"

    f.contacts = [ts.Contact(TODAY - timedelta(days=20), True, TODAY - timedelta(days=5))]
    assert ts.detect_pattern(f, TODAY) == "missed_promise"


# --- DB integration ----------------------------------------------------------
def _customer(db, org, name):
    c = Customer(org_id=org.id, name=name, credit_limit=Decimal("500000"), payment_terms_days=30,
                 risk_tier=RiskTier.medium.value, is_active=True)
    db.add(c)
    db.flush()
    return c


def _invoice(db, org, cust, number, days_overdue, amount, disputed=False, status="overdue"):
    due = TODAY - timedelta(days=days_overdue)
    inv = Invoice(org_id=org.id, customer_id=cust.id, invoice_number=number, issue_date=due - timedelta(days=30),
                  due_date=due, total_amount=Decimal(amount), status=status, is_disputed=disputed)
    db.add(inv)
    db.flush()
    return inv


def test_today_endpoint_lanes(client, db, test_org, auth_headers):
    a = _customer(db, test_org, "Specimen Mart")
    b = _customer(db, test_org, "Sample Traders")
    c = _customer(db, test_org, "Placeholder Co")
    _invoice(db, test_org, a, "A-1", 12, "95000")
    _invoice(db, test_org, b, "B-1", 48, "180000", disputed=True)
    _invoice(db, test_org, c, "C-1", 100, "75000")

    resp = client.get("/api/v1/collections/today?call_slots=3", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert [x["customer_name"] for x in body["call"]] == ["Specimen Mart"]
    assert [x["customer_name"] for x in body["resolve"]] == ["Sample Traders"]
    assert [x["customer_name"] for x in body["escalate"]] == ["Placeholder Co"]
    assert "Disputed invoice B-1" in body["resolve"][0]["reason"]
    assert body["data_stale"] is True  # no receipts entered yet


def test_paid_invoice_not_listed_and_balance_uses_allocations(client, db, test_org, auth_headers):
    a = _customer(db, test_org, "Partial Payer")
    inv = _invoice(db, test_org, a, "P-1", 20, "100000")
    pay = Payment(org_id=test_org.id, customer_id=a.id, received_date=TODAY, amount=Decimal("40000"),
                  payment_mode="neft")
    db.add(pay)
    db.flush()
    db.add(PaymentAllocation(payment_id=pay.id, invoice_id=inv.id, allocated_amount=Decimal("40000"),
                             allocated_at=datetime.now(timezone.utc)))
    db.flush()

    body = client.get("/api/v1/collections/today", headers=auth_headers).json()
    acct = body["call"][0]
    assert Decimal(acct["overdue_amount"]) == Decimal("60000")
    assert body["data_stale"] is False


def test_contact_cooldown_and_dispute_toggle(client, db, test_org, test_user, auth_headers):
    a = _customer(db, test_org, "Called Yesterday")
    inv = _invoice(db, test_org, a, "CY-1", 40, "30000")
    db.add(FollowUp(org_id=test_org.id, invoice_id=inv.id, customer_id=a.id, status="contacted", channel="call",
                    created_by=test_user.id))
    db.flush()
    acct = client.get("/api/v1/collections/today", headers=auth_headers).json()["call"][0]
    assert acct["score"] == pytest.approx(30000 * 0.7 * 1.2 * 0.5)  # thin history, 31-60d, cooldown

    r = client.post(f"/api/v1/collections/invoices/{inv.id}/dispute", json={"disputed": True}, headers=auth_headers)
    assert r.status_code == 200
    body = client.get("/api/v1/collections/today", headers=auth_headers).json()
    assert body["call"] == [] and len(body["resolve"]) == 1


def test_dispute_is_tenant_scoped(client, db, other_org, auth_headers):
    c = _customer(db, other_org, "Other Tenant Customer")
    inv = _invoice(db, other_org, c, "O-1", 10, "1000")
    r = client.post(f"/api/v1/collections/invoices/{inv.id}/dispute", json={"disputed": True}, headers=auth_headers)
    assert r.status_code == 404
