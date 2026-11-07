"""Payment service: record payments and allocate to invoices."""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.payment import Payment, PaymentAllocation
from app.models.invoice import Invoice
from app.models.follow_up import FollowUp, FollowUpStatus
from app.schemas.payment import (
    AllocationOut,
    FifoAllocationSuggestionResponse,
    SuggestedAllocationItem,
    PaymentCreate,
    PaymentOut,
    PaymentListResponse,
)
from app.services.invoice_service import recompute_invoice_status, _get_outstanding_balance


def suggest_fifo_allocation(
    customer_id: UUID,
    amount: Decimal,
    org_id: UUID,
    db: Session,
) -> FifoAllocationSuggestionResponse:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.org_id == org_id, Customer.deleted_at == None)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    today = date.today()
    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.customer_id == customer_id,
            Invoice.org_id == org_id,
            Invoice.deleted_at == None,
            Invoice.status.notin_(["paid", "cancelled"]),
        )
        .order_by(Invoice.due_date.asc(), Invoice.issue_date.asc())
        .all()
    )

    remaining = max(Decimal("0"), amount)
    total_allocated = Decimal("0")
    total_outstanding = Decimal("0")
    invoices_covered = 0
    suggested_allocations: list[SuggestedAllocationItem] = []

    for inv in invoices:
        outstanding = _get_outstanding_balance(db, inv.id)
        if outstanding <= Decimal("0"):
            continue

        total_outstanding += outstanding
        suggested_amount = Decimal("0")

        if remaining > Decimal("0"):
            suggested_amount = min(remaining, outstanding)
            remaining -= suggested_amount
            total_allocated += suggested_amount
            if suggested_amount > Decimal("0"):
                invoices_covered += 1

        days_overdue = max(0, (today - inv.due_date).days)
        suggested_allocations.append(
            SuggestedAllocationItem(
                invoice_id=inv.id,
                invoice_number=inv.invoice_number,
                issue_date=inv.issue_date,
                due_date=inv.due_date,
                days_overdue=days_overdue,
                total_amount=inv.total_amount,
                outstanding_balance=outstanding,
                suggested_allocated_amount=suggested_amount,
                status=inv.status,
            )
        )

    unallocated_amount = max(Decimal("0"), amount - total_allocated)

    return FifoAllocationSuggestionResponse(
        customer_id=customer.id,
        customer_name=customer.name,
        total_payment_amount=amount,
        total_outstanding=total_outstanding,
        total_allocated=total_allocated,
        unallocated_amount=unallocated_amount,
        invoices_covered=invoices_covered,
        allocations=suggested_allocations,
    )


def create_payment(payload: PaymentCreate, org_id: UUID, db: Session) -> PaymentOut:
    """Record a payment and apply allocations; validates over-allocation and customer ownership."""
    # Verify customer exists in org
    customer = (
        db.query(Customer)
        .filter(Customer.id == payload.customer_id, Customer.org_id == org_id, Customer.deleted_at == None)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    if payload.amount <= Decimal("0"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payment amount must be greater than zero",
        )

    # UTR / Reference deduplication check within org
    if payload.reference_no and payload.reference_no.strip():
        existing_ref = (
            db.query(Payment)
            .filter(
                Payment.org_id == org_id,
                func.lower(Payment.reference_no) == func.lower(payload.reference_no.strip()),
            )
            .first()
        )
        if existing_ref:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Payment with reference/UTR '{payload.reference_no.strip()}' already exists in this organization.",
            )

    payment = Payment(
        org_id=org_id,
        customer_id=payload.customer_id,
        received_date=payload.received_date,
        amount=payload.amount,
        reference_no=payload.reference_no.strip() if payload.reference_no else None,
        payment_mode=payload.payment_mode,
        notes=payload.notes,
    )
    db.add(payment)
    db.flush()

    total_allocated = Decimal("0")
    # Track cumulative allocation per invoice to prevent intra-request over-allocation
    allocated_per_invoice: dict[UUID, Decimal] = {}

    for alloc_in in payload.allocations:
        if alloc_in.allocated_amount <= Decimal("0"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Allocated amount must be greater than zero",
            )

        # Fetch invoice with row-level lock and validate org and customer
        invoice = (
            db.query(Invoice)
            .filter(Invoice.id == alloc_in.invoice_id, Invoice.deleted_at == None)
            .with_for_update()
            .first()
        )
        if invoice is None or invoice.org_id != org_id:
            raise HTTPException(status_code=403, detail=f"Invoice {alloc_in.invoice_id} not accessible")

        if invoice.customer_id != payload.customer_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invoice {invoice.invoice_number} does not belong to customer {payload.customer_id}",
            )

        allocated_per_invoice[alloc_in.invoice_id] = (
            allocated_per_invoice.get(alloc_in.invoice_id, Decimal("0")) + alloc_in.allocated_amount
        )

        outstanding = _get_outstanding_balance(db, alloc_in.invoice_id)
        if allocated_per_invoice[alloc_in.invoice_id] > outstanding:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Allocation of {allocated_per_invoice[alloc_in.invoice_id]} exceeds outstanding balance {outstanding} for invoice {invoice.invoice_number}",
            )
        total_allocated += alloc_in.allocated_amount

        alloc = PaymentAllocation(
            payment_id=payment.id,
            invoice_id=alloc_in.invoice_id,
            allocated_amount=alloc_in.allocated_amount,
            allocated_at=datetime.now(timezone.utc),
        )
        db.add(alloc)

    if total_allocated > payload.amount:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Total allocations {total_allocated} exceed payment amount {payload.amount}",
        )

    db.flush()

    # Recompute statuses and reconcile open PTPs for all affected invoices
    for alloc_in in payload.allocations:
        affected_invoice = db.get(Invoice, alloc_in.invoice_id)
        if affected_invoice:
            new_status = recompute_invoice_status(db, affected_invoice)
            new_balance = _get_outstanding_balance(db, affected_invoice.id)
            # Reconcile open PTPs on this invoice
            open_pts = (
                db.query(FollowUp)
                .filter(
                    FollowUp.invoice_id == affected_invoice.id,
                    FollowUp.promise_status.in_(["pending", "broken", "partially_fulfilled"]),
                )
                .all()
            )
            for p in open_pts:
                if new_balance <= Decimal("0"):
                    p.promise_status = "fulfilled"
                    p.status = FollowUpStatus.resolved
                    p.completed_at = datetime.now(timezone.utc)
                else:
                    p.promise_status = "partially_fulfilled"

    db.commit()
    db.refresh(payment)

    out = PaymentOut.model_validate(payment)
    out.customer_name = customer.name
    out.unallocated_amount = max(Decimal("0"), payload.amount - total_allocated)
    out.allocations = [
        AllocationOut(
            id=a.id,
            invoice_id=a.invoice_id,
            invoice_number=db.query(Invoice.invoice_number).filter(Invoice.id == a.invoice_id).scalar(),
            allocated_amount=a.allocated_amount,
            allocated_at=a.allocated_at,
        )
        for a in payment.allocations
    ]
    return out


def get_payment(payment_id: UUID, org_id: UUID, db: Session) -> PaymentOut:
    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id, Payment.org_id == org_id)
        .first()
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return PaymentOut.model_validate(payment)


def list_payments(
    org_id: UUID,
    db: Session,
    customer_id: UUID | None = None,
    page: int = 1,
    page_size: int = 50,
) -> PaymentListResponse:
    stmt = select(Payment).where(Payment.org_id == org_id)
    if customer_id:
        stmt = stmt.where(Payment.customer_id == customer_id)
    stmt = stmt.order_by(Payment.received_date.desc(), Payment.id.desc())
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    payments = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return PaymentListResponse(
        items=[PaymentOut.model_validate(p) for p in payments],
        total=total,
        page=page,
        per_page=page_size,
        page_size=page_size,
    )
