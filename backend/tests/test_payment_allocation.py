"""
Critical tests for payment allocation correctness.

Covers:
  - Overpayment rejection (allocation > outstanding is blocked)
  - API-level payment allocation triggers correct invoice status recompute (regression for
    the bug where recompute_invoice_status was called with a UUID instead of an Invoice object)
  - Allocating a payment to an invoice from a different org is blocked (403)
"""
from datetime import date, datetime, timezone
from decimal import Decimal
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.organization import Organization
from app.models.payment import Payment, PaymentAllocation, PaymentMode
from app.models.user import User
from app.services.invoice_service import get_outstanding_balance, recompute_invoice_status
from app.services.payment_service import create_payment
from app.schemas.payment import PaymentCreate, AllocationIn


# ─── Unit-level overpayment prevention ───────────────────────────────────────

def test_overpayment_raises_422_via_api(
    client: TestClient, db: Session, test_org: Organization, test_customer: Customer, auth_headers: dict
):
    """Allocating more than the invoice outstanding must return 422."""
    inv = Invoice(
        org_id=test_org.id,
        customer_id=test_customer.id,
        invoice_number="INV-OVERPAY-001",
        issue_date=date(2024, 5, 1),
        due_date=date(2024, 5, 31),
        total_amount=Decimal("10000.00"),
        status=InvoiceStatus.sent.value,
    )
    db.add(inv)
    db.flush()

    payload = {
        "customer_id": str(test_customer.id),
        "received_date": "2024-05-20",
        "amount": "15000.00",
        "payment_mode": "neft",
        "allocations": [
            {
                "invoice_id": str(inv.id),
                "allocated_amount": "15000.00",   # exceeds invoice total by 5000
            }
        ],
    }
    resp = client.post("/api/v1/payments", json=payload, headers=auth_headers)
    assert resp.status_code == 422, f"Expected 422 but got {resp.status_code}: {resp.text}"
    assert "exceeds outstanding" in resp.text


def test_full_payment_via_api_marks_invoice_paid(
    client: TestClient, db: Session, test_org: Organization, test_customer: Customer, auth_headers: dict
):
    """
    Regression test for bug: recompute_invoice_status was called with invoice_id (UUID)
    instead of Invoice ORM object, causing AttributeError at runtime.

    After the fix the payment endpoint must correctly transition invoice to 'paid'.
    """
    inv = Invoice(
        org_id=test_org.id,
        customer_id=test_customer.id,
        invoice_number="INV-API-STATUS-001",
        issue_date=date(2024, 6, 1),
        due_date=date(2024, 6, 30),
        total_amount=Decimal("25000.00"),
        status=InvoiceStatus.sent.value,
    )
    db.add(inv)
    db.flush()

    payload = {
        "customer_id": str(test_customer.id),
        "received_date": "2024-06-25",
        "amount": "25000.00",
        "payment_mode": "rtgs",
        "allocations": [
            {
                "invoice_id": str(inv.id),
                "allocated_amount": "25000.00",
            }
        ],
    }
    resp = client.post("/api/v1/payments", json=payload, headers=auth_headers)
    assert resp.status_code == 201, f"Payment creation failed: {resp.text}"

    # Reload invoice and check status was recomputed
    db.expire(inv)
    updated = db.get(Invoice, inv.id)
    assert updated.status == InvoiceStatus.paid.value, (
        f"Invoice status should be 'paid' but got '{updated.status}'. "
        "Likely the recompute_invoice_status bug was not fixed."
    )

    # Balance must be zero
    balance = get_outstanding_balance(db, inv.id)
    assert balance == Decimal("0.00")


def test_partial_payment_via_api_marks_invoice_partial(
    client: TestClient, db: Session, test_org: Organization, test_customer: Customer, auth_headers: dict
):
    """Partial allocation transitions invoice to 'partial' status when due date is in the future."""
    from datetime import timedelta
    today = date.today()
    inv = Invoice(
        org_id=test_org.id,
        customer_id=test_customer.id,
        invoice_number="INV-API-PARTIAL-001",
        issue_date=today,
        due_date=today + timedelta(days=30),
        total_amount=Decimal("50000.00"),
        status=InvoiceStatus.sent.value,
    )
    db.add(inv)
    db.flush()

    payload = {
        "customer_id": str(test_customer.id),
        "received_date": today.isoformat(),
        "amount": "30000.00",
        "payment_mode": "upi",
        "allocations": [
            {"invoice_id": str(inv.id), "allocated_amount": "30000.00"}
        ],
    }
    resp = client.post("/api/v1/payments", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text

    db.expire(inv)
    updated = db.get(Invoice, inv.id)
    assert updated.status == InvoiceStatus.partial.value

    balance = get_outstanding_balance(db, inv.id)
    assert balance == Decimal("20000.00")


def test_cross_org_payment_allocation_blocked(
    client: TestClient, db: Session, test_org: Organization, other_org: Organization,
    test_customer: Customer, auth_headers: dict
):
    """A user cannot allocate a payment to an invoice that belongs to another org."""
    other_cust = Customer(
        org_id=other_org.id,
        name="Other Org Customer",
        is_active=True,
    )
    db.add(other_cust)
    db.flush()

    other_inv = Invoice(
        org_id=other_org.id,
        customer_id=other_cust.id,
        invoice_number="INV-CROSS-ORG-001",
        issue_date=date(2024, 1, 1),
        due_date=date(2024, 1, 31),
        total_amount=Decimal("10000.00"),
        status=InvoiceStatus.sent.value,
    )
    db.add(other_inv)
    db.flush()

    payload = {
        "customer_id": str(test_customer.id),
        "received_date": "2024-01-15",
        "amount": "10000.00",
        "payment_mode": "neft",
        "allocations": [
            {"invoice_id": str(other_inv.id), "allocated_amount": "10000.00"}
        ],
    }
    resp = client.post("/api/v1/payments", json=payload, headers=auth_headers)
    # Must be 403 (access denied for the cross-org invoice)
    assert resp.status_code == 403, f"Expected 403 but got {resp.status_code}"
