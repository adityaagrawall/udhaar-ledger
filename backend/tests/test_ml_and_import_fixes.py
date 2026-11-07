"""Regression tests for ML leakage / tenancy fixes and import validation fixes."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import io
import uuid

import pytest

from app.core.security import create_access_token, hash_password
from app.ml import train as ml_train
from app.ml.features import extract_features
from app.models.customer import Customer, RiskTier
from app.models.invoice import Invoice
from app.models.payment import Payment, PaymentAllocation
from app.models.user import User
from app.services.import_service import preview_import

T0 = date(2025, 1, 1)


def _cust(db, org, name="C"):
    c = Customer(org_id=org.id, name=name, credit_limit=Decimal("100000"), payment_terms_days=30,
                 risk_tier=RiskTier.medium.value, is_active=True)
    db.add(c)
    db.flush()
    return c


def _paid_invoice(db, org, cust, number, issue, due, paid_on, amount="1000"):
    inv = Invoice(org_id=org.id, customer_id=cust.id, invoice_number=number, issue_date=issue, due_date=due,
                  total_amount=Decimal(amount), status="paid")
    db.add(inv)
    db.flush()
    pay = Payment(org_id=org.id, customer_id=cust.id, received_date=paid_on, amount=Decimal(amount), payment_mode="neft")
    db.add(pay)
    db.flush()
    db.add(PaymentAllocation(payment_id=pay.id, invoice_id=inv.id, allocated_amount=Decimal(amount),
                             allocated_at=datetime.now(timezone.utc)))
    db.flush()
    return inv


def test_features_ignore_payments_made_after_as_of(db, test_org):
    c = _cust(db, test_org)
    # A: issued Jan 1, due Jan 31, paid late on Mar 2 (after B is issued on Jan 11)
    _paid_invoice(db, test_org, c, "A", T0, T0 + timedelta(days=30), T0 + timedelta(days=60))
    b = _paid_invoice(db, test_org, c, "B", T0 + timedelta(days=10), T0 + timedelta(days=40), T0 + timedelta(days=41))

    at_issue = extract_features(b.id, test_org.id, db, as_of=b.issue_date)
    assert at_issue["total_historical_invoices"] == 0  # A was not yet settled when B was issued

    later = extract_features(b.id, test_org.id, db, as_of=T0 + timedelta(days=70))
    assert later["total_historical_invoices"] == 1
    assert later["late_payment_rate"] == 1.0
    assert later["avg_days_late"] == 30.0


def test_features_reject_other_orgs_invoice(db, test_org, other_org):
    c = _cust(db, other_org)
    inv = _paid_invoice(db, other_org, c, "X", T0, T0 + timedelta(days=30), T0 + timedelta(days=31))
    with pytest.raises(ValueError):
        extract_features(inv.id, test_org.id, db)


def test_model_artifacts_are_per_org():
    a, b = uuid.uuid4(), uuid.uuid4()
    assert ml_train.regressor_path(a) != ml_train.regressor_path(b)
    assert ml_train.load_model(b) is None  # an untrained tenant never sees another tenant's model


def test_viewer_cannot_train(client, db, test_org):
    viewer = User(org_id=test_org.id, email="viewer@example.com", hashed_password=hash_password("x" * 12),
                  full_name="V", role="viewer", is_active=True)
    db.add(viewer)
    db.flush()
    token = create_access_token({"sub": str(viewer.id), "org_id": str(test_org.id), "role": "viewer"})
    r = client.post("/api/v1/ml/train", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def _csv(rows):
    head = "invoice_number,customer_name,issue_date,due_date,total_amount,payment_amount,payment_date\n"
    return (head + "\n".join(rows) + "\n").encode()


def test_payment_without_valid_date_is_rejected(db, test_org):
    data = _csv(["N1,Acme,2025-01-01,2025-01-31,1000,500,", "N2,Acme,2025-01-01,2025-01-31,1000,500,not-a-date"])
    prev = preview_import(data, "p.csv", {}, test_org.id, db)
    assert prev.valid_rows == 0
    assert sum(1 for e in prev.errors if e.field == "payment_date") == 2


def test_payment_exceeding_invoice_total_is_rejected(db, test_org):
    data = _csv(["N3,Acme,2025-01-01,2025-01-31,1000,1500,2025-02-01"])
    prev = preview_import(data, "q.csv", {}, test_org.id, db)
    assert prev.valid_rows == 0
    assert any(e.field == "payment_amount" for e in prev.errors)


def test_duplicate_invoice_within_same_file_flagged(db, test_org):
    data = _csv(["N4,Acme,2025-01-01,2025-01-31,1000,,", "N4,Acme,2025-01-01,2025-01-31,1000,,"])
    prev = preview_import(data, "r.csv", {}, test_org.id, db)
    assert prev.valid_rows == 1 and prev.duplicate_rows == 1
