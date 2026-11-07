"""
Invoice service: business logic for creating, querying, and updating invoices.

IMPORTANT: Outstanding balance is ALWAYS computed as:
  total_amount - SUM(payment_allocations.allocated_amount)
Never calculated from joined rows to avoid double-counting.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, text, or_
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus
from app.models.payment import PaymentAllocation
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate


def get_outstanding_balance(db: Session, invoice_id: UUID) -> Decimal:
    """
    Compute outstanding balance for a single invoice.
    Uses a subquery to avoid double-counting from JOINs.
    """
    allocated = (
        db.query(func.coalesce(func.sum(PaymentAllocation.allocated_amount), Decimal("0")))
        .filter(PaymentAllocation.invoice_id == invoice_id)
        .scalar()
    )
    invoice = db.query(Invoice.total_amount).filter(Invoice.id == invoice_id).scalar()
    if invoice is None:
        raise ValueError(f"Invoice {invoice_id} not found")
    return Decimal(str(invoice)) - Decimal(str(allocated))


_get_outstanding_balance = get_outstanding_balance


def recompute_invoice_status(db: Session, invoice: Invoice) -> None:
    """
    Recalculate and persist invoice status based on allocations and due date.
    Call this after any payment allocation change.
    """
    outstanding = get_outstanding_balance(db, invoice.id)
    today = date.today()

    if outstanding <= Decimal("0"):
        new_status = InvoiceStatus.paid
    elif invoice.due_date < today:
        new_status = InvoiceStatus.overdue
    elif outstanding < invoice.total_amount:
        new_status = InvoiceStatus.partial
    else:
        if invoice.status in [InvoiceStatus.draft.value, InvoiceStatus.cancelled.value]:
            new_status = InvoiceStatus(invoice.status)
        else:
            new_status = InvoiceStatus.sent

    invoice.status = new_status.value
    db.add(invoice)


def get_invoice(db: Session, invoice_id: UUID, org_id: UUID) -> Optional[Invoice]:
    return (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.org_id == org_id, Invoice.deleted_at == None)
        .first()
    )


def list_invoices(
    db: Session,
    org_id: UUID,
    page: int = 1,
    per_page: int = 50,
    status: Optional[str] = None,
    customer_id: Optional[UUID] = None,
    overdue_only: bool = False,
    search: Optional[str] = None,
) -> tuple[list[dict], int]:
    """
    Returns invoices enriched with outstanding_balance and days_overdue.
    Balance is computed per-invoice using a correlated subquery — never from JOIN rows.
    """
    today = date.today()

    query = db.query(Invoice).filter(
        Invoice.org_id == org_id,
        Invoice.deleted_at == None,
    )

    if status:
        query = query.filter(Invoice.status == status)
    if customer_id:
        query = query.filter(Invoice.customer_id == customer_id)
    if overdue_only:
        query = query.filter(Invoice.due_date < today, Invoice.status != InvoiceStatus.paid.value)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.join(Customer, Customer.id == Invoice.customer_id).filter(
            or_(
                Invoice.invoice_number.ilike(term),
                Customer.name.ilike(term),
            )
        )

    total = query.count()
    invoices = query.order_by(Invoice.due_date.desc()).offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for inv in invoices:
        outstanding = get_outstanding_balance(db, inv.id)
        days_overdue = max(0, (today - inv.due_date).days) if inv.status != InvoiceStatus.paid.value else 0
        customer_name = inv.customer.name if inv.customer else None
        item_dict = {
            "id": inv.id,
            "org_id": inv.org_id,
            "customer_id": inv.customer_id,
            "customer_name": customer_name,
            "invoice_number": inv.invoice_number,
            "issue_date": inv.issue_date,
            "due_date": inv.due_date,
            "total_amount": inv.total_amount,
            "status": inv.status,
            "notes": inv.notes,
            "created_at": inv.created_at,
            "outstanding_balance": outstanding,
            "days_overdue": days_overdue,
            "allocations": [
                {
                    "id": pa.id,
                    "payment_id": pa.payment_id,
                    "allocated_amount": pa.allocated_amount,
                    "allocated_at": pa.allocated_at,
                }
                for pa in inv.payment_allocations
            ],
        }
        result.append(item_dict)

    return result, total


def create_invoice(db: Session, org_id: UUID, data: InvoiceCreate) -> Invoice:
    invoice = Invoice(
        org_id=org_id,
        customer_id=data.customer_id,
        invoice_number=data.invoice_number,
        issue_date=data.issue_date,
        due_date=data.due_date,
        total_amount=data.total_amount,
        status=InvoiceStatus.sent.value,
        notes=data.notes,
    )
    db.add(invoice)
    db.flush()  # Get ID without committing

    for item_data in data.items:
        item = InvoiceItem(
            invoice_id=invoice.id,
            description=item_data.description,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            line_total=item_data.line_total or (item_data.quantity * item_data.unit_price),
        )
        db.add(item)

    # Set overdue status if already past due date at creation
    if data.due_date < date.today():
        invoice.status = InvoiceStatus.overdue.value

    db.commit()
    db.refresh(invoice)
    return invoice


def get_invoices_outstanding_total(db: Session, org_id: UUID) -> Decimal:
    """Aggregate outstanding balance across all active invoices for an org."""
    result = db.execute(
        text("""
            SELECT COALESCE(
                SUM(i.total_amount) - COALESCE(SUM(pa_totals.allocated), 0),
                0
            )
            FROM invoices i
            LEFT JOIN (
                SELECT invoice_id, SUM(allocated_amount) AS allocated
                FROM payment_allocations
                GROUP BY invoice_id
            ) pa_totals ON pa_totals.invoice_id = i.id
            WHERE i.org_id = :org_id
              AND i.deleted_at IS NULL
              AND i.status NOT IN ('paid', 'cancelled')
        """),
        {"org_id": str(org_id)},
    ).scalar()
    return Decimal(str(result or "0"))
