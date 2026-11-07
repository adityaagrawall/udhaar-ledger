from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.follow_up import FollowUp, FollowUpStatus
from app.schemas.follow_up import FollowUpCreate, FollowUpUpdate, FollowUpOut, FollowUpListResponse
from app.schemas.analytics import PtpStats
from app.services.invoice_service import _get_outstanding_balance


def create_follow_up(payload: FollowUpCreate, org_id: UUID, user_id: UUID, db: Session) -> FollowUpOut:
    # Verify invoice belongs to org
    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == payload.invoice_id, Invoice.org_id == org_id, Invoice.deleted_at == None)
        .first()
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Verify customer belongs to org
    customer = (
        db.query(Customer)
        .filter(Customer.id == payload.customer_id, Customer.org_id == org_id, Customer.deleted_at == None)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Verify invoice belongs to customer
    if invoice.customer_id != payload.customer_id:
        raise HTTPException(status_code=400, detail="Invoice does not belong to specified customer")

    status_val = getattr(payload, "status", None) or "pending"
    promised_amount = payload.promised_amount
    promised_date = payload.promised_date
    promise_status = payload.promise_status

    if promised_date is not None:
        if status_val == "pending":
            status_val = "promised"
        if not promise_status:
            promise_status = "pending"
        if promised_amount is None:
            promised_amount = _get_outstanding_balance(db, invoice.id)

    fu = FollowUp(
        org_id=org_id,
        invoice_id=payload.invoice_id,
        customer_id=payload.customer_id,
        status=status_val,
        channel=payload.channel,
        notes=payload.notes,
        scheduled_at=payload.scheduled_at,
        created_by=user_id,
        promised_amount=promised_amount,
        promised_date=promised_date,
        promise_status=promise_status,
    )
    db.add(fu)
    db.commit()
    db.refresh(fu)

    out = FollowUpOut.model_validate(fu)
    out.customer_name = customer.name
    out.invoice_number = invoice.invoice_number
    out.outstanding_balance = _get_outstanding_balance(db, invoice.id)
    return out


def get_follow_up(follow_up_id: UUID, org_id: UUID, db: Session) -> FollowUpOut:
    fu = (
        db.query(FollowUp)
        .filter(FollowUp.id == follow_up_id, FollowUp.org_id == org_id)
        .first()
    )
    if fu is None:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    return FollowUpOut.model_validate(fu)


def list_follow_ups(
    org_id: UUID,
    db: Session,
    invoice_id: UUID | None = None,
    customer_id: UUID | None = None,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> FollowUpListResponse:
    stmt = select(FollowUp).where(FollowUp.org_id == org_id)
    if invoice_id:
        stmt = stmt.where(FollowUp.invoice_id == invoice_id)
    if customer_id:
        stmt = stmt.where(FollowUp.customer_id == customer_id)
    if status_filter:
        stmt = stmt.where(FollowUp.status == status_filter)
    stmt = stmt.order_by(FollowUp.created_at.desc(), FollowUp.id.desc())
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    items = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return FollowUpListResponse(
        items=[FollowUpOut.model_validate(f) for f in items],
        total=total,
        page=page,
        per_page=page_size,
        page_size=page_size,
    )


def update_follow_up(follow_up_id: UUID, org_id: UUID, payload: FollowUpUpdate, db: Session) -> FollowUpOut:
    fu = (
        db.query(FollowUp)
        .filter(FollowUp.id == follow_up_id, FollowUp.org_id == org_id)
        .first()
    )
    if fu is None:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(fu, field, val)
    db.commit()
    db.refresh(fu)
    return FollowUpOut.model_validate(fu)


def sync_ptp_statuses(org_id: UUID, db: Session) -> dict:
    """Auto-detect broken promises: promised_date < today and invoice still unpaid/overdue."""
    today = date.today()
    open_promises = (
        db.query(FollowUp)
        .filter(
            FollowUp.org_id == org_id,
            FollowUp.promise_status.in_(["pending", "partially_fulfilled"]),
            FollowUp.promised_date != None,
            FollowUp.promised_date < today,
        )
        .all()
    )

    broken_count = 0
    for fu in open_promises:
        outstanding = _get_outstanding_balance(db, fu.invoice_id)
        if outstanding > Decimal("0"):
            fu.promise_status = "broken"
            broken_count += 1

    if broken_count > 0:
        db.commit()

    return {"synced_count": len(open_promises), "broken_marked": broken_count}


def get_ptp_summary(org_id: UUID, db: Session) -> PtpStats:
    """Return aggregated promise-to-pay statistics."""
    sync_ptp_statuses(org_id, db)

    records = (
        db.query(FollowUp.promise_status, FollowUp.promised_amount)
        .filter(
            FollowUp.org_id == org_id,
            FollowUp.promise_status != None,
        )
        .all()
    )

    pending_count = 0
    pending_amount = Decimal("0")
    fulfilled_count = 0
    fulfilled_amount = Decimal("0")
    broken_count = 0
    broken_amount = Decimal("0")

    for status_name, amt in records:
        amt_val = amt or Decimal("0")
        if status_name == "pending":
            pending_count += 1
            pending_amount += amt_val
        elif status_name in ("fulfilled", "partially_fulfilled"):
            fulfilled_count += 1
            fulfilled_amount += amt_val
        elif status_name == "broken":
            broken_count += 1
            broken_amount += amt_val

    total_resolved = fulfilled_count + broken_count
    recovery_rate = (
        round((fulfilled_count / total_resolved) * 100.0, 1)
        if total_resolved > 0
        else (100.0 if fulfilled_count > 0 else 0.0)
    )

    return PtpStats(
        pending_count=pending_count,
        pending_amount=pending_amount,
        fulfilled_count=fulfilled_count,
        fulfilled_amount=fulfilled_amount,
        broken_count=broken_count,
        broken_amount=broken_amount,
        recovery_rate_pct=recovery_rate,
    )
