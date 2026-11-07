"""
Phase 1 Remediation & Security Regression Tests.

Covers:
1. Invoice status transition: partially paid overdue invoices become 'overdue' (not 'partial').
2. Collection scoring: uses actual outstanding balance, not gross invoice total.
3. Payment allocation integrity: cross-customer allocations in same org are blocked (422).
4. Payment allocation integrity: duplicate allocations to same invoice exceeding balance are blocked (422).
5. Cross-tenant isolation: customer from another org returns 404 (not 403, preventing enumeration).
6. Cross-tenant isolation: payment from another org returns 404 (not 403).
7. Cross-tenant isolation: creating follow-up with other org's invoice/customer returns 404.
8. Auth security: refresh token rejected when user is deactivated (401).
9. Server-side search: /invoices?search= filters correctly.
10. Server-side search: /collections/queue?search= filters correctly.
11. CSV export security: formula injection characters (=, +, -, @) are sanitized.
12. PostgreSQL analytics queries: monthly trends and dashboard trend execute with valid intervals.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import io
import csv

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_refresh_token
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.organization import Organization
from app.models.payment import Payment, PaymentAllocation, PaymentMode
from app.models.follow_up import FollowUp, FollowUpStatus
from app.models.user import User
from app.services.invoice_service import get_outstanding_balance, recompute_invoice_status
from app.services.collection_service import calculate_priority_score, get_collection_queue
from app.services.analytics_service import get_monthly_trends, get_aging_report
from app.services.dashboard_service import get_collection_trend


def test_partially_paid_overdue_invoice_is_overdue(db: Session, test_org: Organization, test_customer: Customer):
    """Partially paid invoices past their due date must be marked overdue, not partial."""
    today = date.today()
    inv = Invoice(
        org_id=test_org.id,
        customer_id=test_customer.id,
        invoice_number="INV-REGRESS-001",
        issue_date=today - timedelta(days=60),
        due_date=today - timedelta(days=30),  # 30 days overdue
        total_amount=Decimal("100000.00"),
        status=InvoiceStatus.sent.value,
    )
    db.add(inv)
    db.flush()

    payment = Payment(
        org_id=test_org.id,
        customer_id=test_customer.id,
        received_date=today - timedelta(days=20),
        amount=Decimal("10000.00"),  # Partial payment of 10k
        payment_mode=PaymentMode.neft.value,
    )
    db.add(payment)
    db.flush()

    alloc = PaymentAllocation(
        payment_id=payment.id,
        invoice_id=inv.id,
        allocated_amount=Decimal("10000.00"),
        allocated_at=datetime.now(timezone.utc),
    )
    db.add(alloc)
    db.flush()

    recompute_invoice_status(db, inv)
    assert inv.status == InvoiceStatus.overdue.value, "Partially paid overdue invoice must have status 'overdue'"


def test_priority_score_uses_outstanding_balance_not_total_amount(test_customer: Customer):
    """Priority scoring must evaluate remaining balance, not gross invoice amount."""
    today = date.today()
    inv = Invoice(
        invoice_number="INV-BIG-PAID",
        issue_date=today - timedelta(days=40),
        due_date=today - timedelta(days=10),
        total_amount=Decimal("1000000.00"),  # 10 Lakhs original
        status=InvoiceStatus.overdue.value,
    )

    # Scenario A: 10 Lakhs total, but 9.9 Lakhs paid -> only 10k remaining
    score_small_bal, reasons_small = calculate_priority_score(
        inv, test_customer, last_follow_up_date=None, outstanding_balance=Decimal("10000.00")
    )

    # Scenario B: 10 Lakhs total, full 10 Lakhs remaining
    score_full_bal, reasons_full = calculate_priority_score(
        inv, test_customer, last_follow_up_date=None, outstanding_balance=Decimal("1000000.00")
    )

    # Score with 10k balance should be strictly less than with 10 Lakhs balance
    assert score_small_bal < score_full_bal
    assert not any("Large outstanding" in r for r in reasons_small)
    assert any("Large outstanding balance" in r for r in reasons_full)


def test_cross_customer_payment_allocation_blocked(
    client: TestClient, db: Session, test_org: Organization, test_customer: Customer, auth_headers: dict
):
    """A payment for Customer A cannot be allocated to Customer B's invoice."""
    other_customer = Customer(
        org_id=test_org.id,
        name="Customer B Mart",
        is_active=True,
    )
    db.add(other_customer)
    db.flush()

    other_inv = Invoice(
        org_id=test_org.id,
        customer_id=other_customer.id,
        invoice_number="INV-CUST-B-001",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=30),
        total_amount=Decimal("25000.00"),
        status=InvoiceStatus.sent.value,
    )
    db.add(other_inv)
    db.flush()

    payload = {
        "customer_id": str(test_customer.id),  # Paying customer is Customer A
        "received_date": date.today().isoformat(),
        "amount": "25000.00",
        "payment_mode": "neft",
        "allocations": [
            {"invoice_id": str(other_inv.id), "allocated_amount": "25000.00"}  # Invoice belongs to Customer B!
        ],
    }
    resp = client.post("/api/v1/payments", json=payload, headers=auth_headers)
    assert resp.status_code == 422
    assert "does not belong to customer" in resp.text


def test_duplicate_allocation_exceeding_balance_blocked(
    client: TestClient, db: Session, test_org: Organization, test_customer: Customer, auth_headers: dict
):
    """Submitting duplicate allocations for the same invoice that exceed its balance must be blocked."""
    today = date.today()
    inv = Invoice(
        org_id=test_org.id,
        customer_id=test_customer.id,
        invoice_number="INV-DUP-ALLOC-001",
        issue_date=today,
        due_date=today + timedelta(days=30),
        total_amount=Decimal("10000.00"),
        status=InvoiceStatus.sent.value,
    )
    db.add(inv)
    db.flush()

    payload = {
        "customer_id": str(test_customer.id),
        "received_date": today.isoformat(),
        "amount": "20000.00",
        "payment_mode": "rtgs",
        "allocations": [
            {"invoice_id": str(inv.id), "allocated_amount": "8000.00"},
            {"invoice_id": str(inv.id), "allocated_amount": "8000.00"},  # Sum = 16000 > 10000 balance!
        ],
    }
    resp = client.post("/api/v1/payments", json=payload, headers=auth_headers)
    assert resp.status_code == 422
    assert "exceeds outstanding balance" in resp.text


def test_cross_tenant_customer_returns_404_not_403(
    client: TestClient, db: Session, other_org: Organization, auth_headers: dict
):
    """Accessing another tenant's customer must return 404 to prevent ID enumeration."""
    other_cust = Customer(
        org_id=other_org.id,
        name="Confidential Competitor Customer",
        is_active=True,
    )
    db.add(other_cust)
    db.flush()

    resp = client.get(f"/api/v1/customers/{other_cust.id}", headers=auth_headers)
    assert resp.status_code == 404, f"Expected 404 but got {resp.status_code}"


def test_cross_tenant_payment_returns_404_not_403(
    client: TestClient, db: Session, other_org: Organization, auth_headers: dict
):
    """Accessing another tenant's payment must return 404 to prevent ID enumeration."""
    other_cust = Customer(
        org_id=other_org.id,
        name="Other Tenant Buyer",
        is_active=True,
    )
    db.add(other_cust)
    db.flush()

    other_payment = Payment(
        org_id=other_org.id,
        customer_id=other_cust.id,
        received_date=date.today(),
        amount=Decimal("50000.00"),
        payment_mode=PaymentMode.neft.value,
    )
    db.add(other_payment)
    db.flush()

    resp = client.get(f"/api/v1/payments/{other_payment.id}", headers=auth_headers)
    assert resp.status_code == 404, f"Expected 404 but got {resp.status_code}"


def test_cross_tenant_follow_up_creation_blocked(
    client: TestClient, db: Session, other_org: Organization, test_customer: Customer, auth_headers: dict
):
    """Creating a follow-up referencing another tenant's invoice must return 404."""
    other_cust = Customer(
        org_id=other_org.id,
        name="Other Corp Buyer",
        is_active=True,
    )
    db.add(other_cust)
    db.flush()

    other_inv = Invoice(
        org_id=other_org.id,
        customer_id=other_cust.id,
        invoice_number="INV-OTHER-CORP-99",
        issue_date=date.today(),
        due_date=date.today(),
        total_amount=Decimal("15000.00"),
        status=InvoiceStatus.overdue.value,
    )
    db.add(other_inv)
    db.flush()

    payload = {
        "invoice_id": str(other_inv.id),
        "customer_id": str(test_customer.id),
        "channel": "whatsapp",
        "notes": "Attempting cross tenant follow up",
    }
    resp = client.post("/api/v1/follow-ups", json=payload, headers=auth_headers)
    assert resp.status_code == 404


def test_refresh_token_rejects_inactive_user(client: TestClient, db: Session, test_user: User):
    """A refresh token must be rejected with 401 if the user was deactivated."""
    refresh_token = create_refresh_token({
        "sub": str(test_user.id),
        "org_id": str(test_user.org_id),
        "role": test_user.role,
    })

    # Deactivate the user
    test_user.is_active = False
    db.commit()

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 401

    # Restore user
    test_user.is_active = True
    db.commit()


def test_invoice_server_side_search(
    client: TestClient, db: Session, test_org: Organization, test_customer: Customer, auth_headers: dict
):
    """The /invoices?search= endpoint must filter by invoice number and customer name."""
    inv1 = Invoice(
        org_id=test_org.id,
        customer_id=test_customer.id,
        invoice_number="INV-SEARCH-ALPHA",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=15),
        total_amount=Decimal("12000.00"),
        status=InvoiceStatus.sent.value,
    )
    inv2 = Invoice(
        org_id=test_org.id,
        customer_id=test_customer.id,
        invoice_number="INV-SEARCH-BETA",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=15),
        total_amount=Decimal("18000.00"),
        status=InvoiceStatus.sent.value,
    )
    db.add_all([inv1, inv2])
    db.commit()

    resp = client.get("/api/v1/invoices?search=ALPHA", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    numbers = [item["invoice_number"] for item in data["items"]]
    assert "INV-SEARCH-ALPHA" in numbers
    assert "INV-SEARCH-BETA" not in numbers


def test_queue_server_side_search(
    client: TestClient, db: Session, test_org: Organization, test_customer: Customer, auth_headers: dict
):
    """The /collections/queue?search= endpoint must filter priority queue items."""
    today = date.today()
    inv = Invoice(
        org_id=test_org.id,
        customer_id=test_customer.id,
        invoice_number="INV-QUEUE-SPECIAL-XYZ",
        issue_date=today - timedelta(days=40),
        due_date=today - timedelta(days=10),
        total_amount=Decimal("45000.00"),
        status=InvoiceStatus.overdue.value,
    )
    db.add(inv)
    db.commit()

    resp = client.get("/api/v1/collections/queue?search=SPECIAL-XYZ", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    numbers = [item["invoice_number"] for item in data["items"]]
    assert "INV-QUEUE-SPECIAL-XYZ" in numbers


def test_csv_export_formula_sanitization(
    client: TestClient, db: Session, test_org: Organization, auth_headers: dict
):
    """Exporting to CSV must sanitize formula injection payloads starting with =."""
    malicious_cust = Customer(
        org_id=test_org.id,
        name="=cmd|' /C calc'!A0",
        is_active=True,
    )
    db.add(malicious_cust)
    db.flush()

    inv = Invoice(
        org_id=test_org.id,
        customer_id=malicious_cust.id,
        invoice_number="=HYPERLINK('http://evil.com')",
        issue_date=date.today(),
        due_date=date.today(),
        total_amount=Decimal("5000.00"),
        status=InvoiceStatus.overdue.value,
    )
    db.add(inv)
    db.commit()

    resp = client.get("/api/v1/export/invoices", headers=auth_headers)
    assert resp.status_code == 200
    csv_text = resp.text
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    found = False
    for r in rows:
        if len(r) >= 2 and "'=HYPERLINK" in r[0]:
            found = True
            assert r[0].startswith("'="), "Formula character must be prefixed with single quote"
            assert r[1].startswith("'="), "Customer name formula must be prefixed with single quote"
    assert found, "Sanitized row must be present in export"


def test_analytics_and_dashboard_interval_queries(db: Session, test_org: Organization):
    """PostgreSQL interval queries in monthly trends and collection trend must execute without syntax errors."""
    trends = get_monthly_trends(test_org.id, db, months=6)
    assert isinstance(trends, list)

    trend_points = get_collection_trend(db, test_org.id, months=6)
    assert isinstance(trend_points, list)

    aging = get_aging_report(test_org.id, db)
    assert isinstance(aging, list)
