"""Tests for deterministic receivables balance calculations."""
from datetime import date, datetime, timezone
from decimal import Decimal
import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.organization import Organization
from app.models.payment import Payment, PaymentAllocation, PaymentMode
from app.services.invoice_service import get_outstanding_balance, recompute_invoice_status


def test_full_payment_zeros_balance(db: Session, test_org: Organization, test_customer: Customer):
    """Full payment reduces outstanding balance exactly to 0 and marks invoice as paid."""
    inv = Invoice(
        org_id=test_org.id,
        customer_id=test_customer.id,
        invoice_number="INV-BAL-001",
        issue_date=date(2024, 1, 1),
        due_date=date(2024, 1, 31),
        total_amount=Decimal("50000.00"),
        status=InvoiceStatus.sent.value,
    )
    db.add(inv)
    db.flush()

    balance_initial = get_outstanding_balance(db, inv.id)
    assert balance_initial == Decimal("50000.00")

    # Add full payment
    payment = Payment(
        org_id=test_org.id,
        customer_id=test_customer.id,
        received_date=date(2024, 1, 20),
        amount=Decimal("50000.00"),
        payment_mode=PaymentMode.neft.value,
    )
    db.add(payment)
    db.flush()

    allocation = PaymentAllocation(
        payment_id=payment.id,
        invoice_id=inv.id,
        allocated_amount=Decimal("50000.00"),
        allocated_at=datetime.now(timezone.utc),
    )
    db.add(allocation)
    db.flush()

    balance_final = get_outstanding_balance(db, inv.id)
    assert balance_final == Decimal("0.00")

    recompute_invoice_status(db, inv)
    assert inv.status == InvoiceStatus.paid.value


def test_partial_payment_reduces_balance(db: Session, test_org: Organization, test_customer: Customer):
    """Partial payment accurately subtracts allocated amount and transitions status based on due date."""
    from datetime import timedelta
    today = date.today()
    inv = Invoice(
        org_id=test_org.id,
        customer_id=test_customer.id,
        invoice_number="INV-BAL-002",
        issue_date=today,
        due_date=today + timedelta(days=30),
        total_amount=Decimal("100000.00"),
        status=InvoiceStatus.sent.value,
    )
    db.add(inv)
    db.flush()

    payment = Payment(
        org_id=test_org.id,
        customer_id=test_customer.id,
        received_date=today,
        amount=Decimal("35000.00"),
        payment_mode=PaymentMode.rtgs.value,
    )
    db.add(payment)
    db.flush()

    allocation = PaymentAllocation(
        payment_id=payment.id,
        invoice_id=inv.id,
        allocated_amount=Decimal("35000.00"),
        allocated_at=datetime.now(timezone.utc),
    )
    db.add(allocation)
    db.flush()

    balance = get_outstanding_balance(db, inv.id)
    assert balance == Decimal("65000.00")

    recompute_invoice_status(db, inv)
    assert inv.status == InvoiceStatus.partial.value

    # When due date is in the past, partially paid invoice transitions to overdue
    inv.due_date = today - timedelta(days=5)
    recompute_invoice_status(db, inv)
    assert inv.status == InvoiceStatus.overdue.value


def test_multiple_partial_payments(db: Session, test_org: Organization, test_customer: Customer):
    """Multiple partial payments are summed without discrepancy."""
    inv = Invoice(
        org_id=test_org.id,
        customer_id=test_customer.id,
        invoice_number="INV-BAL-003",
        issue_date=date(2024, 1, 1),
        due_date=date(2024, 1, 31),
        total_amount=Decimal("75000.00"),
        status=InvoiceStatus.sent.value,
    )
    db.add(inv)
    db.flush()

    amounts = [Decimal("20000.00"), Decimal("15000.00"), Decimal("10000.00")]
    for amt in amounts:
        pay = Payment(
            org_id=test_org.id,
            customer_id=test_customer.id,
            received_date=date(2024, 1, 10),
            amount=amt,
            payment_mode=PaymentMode.upi.value,
        )
        db.add(pay)
        db.flush()
        alloc = PaymentAllocation(
            payment_id=pay.id,
            invoice_id=inv.id,
            allocated_amount=amt,
            allocated_at=datetime.now(timezone.utc),
        )
        db.add(alloc)

    db.flush()
    balance = get_outstanding_balance(db, inv.id)
    assert balance == Decimal("30000.00")  # 75000 - 45000


def test_outstanding_balance_not_affected_by_joins(db: Session, test_org: Organization, test_customer: Customer):
    """
    Critical requirement:
    Never calculate outstanding amounts by summing duplicated invoice rows from joins.
    Each invoice's balance must be evaluated in isolation without cross-row multiplier effects.
    """
    # Create 3 invoices for the same customer
    invoices = []
    for i in range(3):
        inv = Invoice(
            org_id=test_org.id,
            customer_id=test_customer.id,
            invoice_number=f"INV-JOIN-{i+1}",
            issue_date=date(2024, 2, 1),
            due_date=date(2024, 2, 28),
            total_amount=Decimal("50000.00"),
            status=InvoiceStatus.sent.value,
        )
        db.add(inv)
        invoices.append(inv)
    db.flush()

    # Invoice 1 gets 2 payments
    for _ in range(2):
        p = Payment(
            org_id=test_org.id,
            customer_id=test_customer.id,
            received_date=date(2024, 2, 10),
            amount=Decimal("10000.00"),
            payment_mode=PaymentMode.neft.value,
        )
        db.add(p)
        db.flush()
        db.add(PaymentAllocation(
            payment_id=p.id,
            invoice_id=invoices[0].id,
            allocated_amount=Decimal("10000.00"),
            allocated_at=datetime.now(timezone.utc),
        ))
    db.flush()

    # Balances must be independently correct:
    # inv[0]: 50000 - 20000 = 30000
    # inv[1]: 50000 - 0 = 50000
    # inv[2]: 50000 - 0 = 50000
    assert get_outstanding_balance(db, invoices[0].id) == Decimal("30000.00")
    assert get_outstanding_balance(db, invoices[1].id) == Decimal("50000.00")
    assert get_outstanding_balance(db, invoices[2].id) == Decimal("50000.00")
