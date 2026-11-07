from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, get_org_id
from app.models.user import User
from app.schemas.invoice import InvoiceCreate, InvoiceListResponse, InvoiceResponse
from app.services.invoice_service import (
    create_invoice,
    get_invoice,
    get_outstanding_balance,
    list_invoices,
    recompute_invoice_status,
)

router = APIRouter()


@router.get("", response_model=InvoiceListResponse)
def list_invoices_route(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    customer_id: Optional[UUID] = Query(None),
    overdue_only: bool = Query(False),
    search: Optional[str] = Query(None),
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    items, total = list_invoices(
        db, UUID(org_id), page=page, per_page=per_page,
        status=status, customer_id=customer_id, overdue_only=overdue_only,
        search=search,
    )
    return InvoiceListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice_route(
    invoice_id: UUID,
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    invoice = get_invoice(db, invoice_id, UUID(org_id))
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    outstanding = get_outstanding_balance(db, invoice_id)
    from datetime import date
    today = date.today()
    days_overdue = max(0, (today - invoice.due_date).days) if invoice.status != "paid" else 0

    return {
        "id": invoice.id,
        "org_id": invoice.org_id,
        "customer_id": invoice.customer_id,
        "customer_name": invoice.customer.name if invoice.customer else None,
        "invoice_number": invoice.invoice_number,
        "issue_date": invoice.issue_date,
        "due_date": invoice.due_date,
        "total_amount": invoice.total_amount,
        "status": invoice.status,
        "notes": invoice.notes,
        "created_at": invoice.created_at,
        "outstanding_balance": outstanding,
        "days_overdue": days_overdue,
        "allocations": [
            {
                "id": pa.id,
                "payment_id": pa.payment_id,
                "allocated_amount": pa.allocated_amount,
                "allocated_at": pa.allocated_at,
            }
            for pa in invoice.payment_allocations
        ],
    }


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice_route(
    data: InvoiceCreate,
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.customer import Customer
    # Verify customer belongs to org
    customer = db.query(Customer).filter(
        Customer.id == data.customer_id,
        Customer.org_id == UUID(org_id),
    ).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    invoice = create_invoice(db, UUID(org_id), data)
    outstanding = get_outstanding_balance(db, invoice.id)
    from datetime import date
    days_overdue = max(0, (date.today() - invoice.due_date).days) if invoice.status != "paid" else 0

    return {
        "id": invoice.id,
        "org_id": invoice.org_id,
        "customer_id": invoice.customer_id,
        "customer_name": customer.name,
        "invoice_number": invoice.invoice_number,
        "issue_date": invoice.issue_date,
        "due_date": invoice.due_date,
        "total_amount": invoice.total_amount,
        "status": invoice.status,
        "notes": invoice.notes,
        "created_at": invoice.created_at,
        "outstanding_balance": outstanding,
        "days_overdue": days_overdue,
        "allocations": [],
    }
