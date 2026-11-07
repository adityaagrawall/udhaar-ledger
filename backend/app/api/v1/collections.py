"""Collection priority queue endpoints."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.invoice import Invoice
from app.schemas.analytics import CollectionQueueResponse
from app.schemas.today import DisputeUpdate, TodayResponse
from app.services.today_service import get_today as get_today_worklist
import app.services.collection_service as svc

router = APIRouter()


@router.get("/today", response_model=TodayResponse)
def get_today(
    call_slots: int = Query(5, ge=1, le=50, description="Calls the team can make today (N)"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lane-based daily worklist: Call today / Escalate / Resolve / Message."""
    return get_today_worklist(db, current_user.org_id, call_slots=call_slots)


@router.post("/invoices/{invoice_id}/dispute")
def set_invoice_dispute(
    invoice_id: UUID,
    payload: DisputeUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark or clear a dispute. Disputed invoices are routed to Resolve and not chased."""
    inv = db.query(Invoice).filter(
        Invoice.id == invoice_id, Invoice.org_id == current_user.org_id, Invoice.deleted_at == None  # noqa: E711
    ).first()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    inv.is_disputed = payload.disputed
    db.commit()
    return {"invoice_id": str(inv.id), "is_disputed": inv.is_disputed}


@router.get("/queue", response_model=CollectionQueueResponse)
@router.get("", response_model=CollectionQueueResponse)
def get_collection_queue(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    risk_tier: Optional[str] = Query(None),
    min_days_overdue: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    promise_filter: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return invoices ranked by explainable collection priority score (descending)."""
    return svc.get_collection_queue(
        db=db,
        org_id=current_user.org_id,
        page=page,
        per_page=per_page,
        risk_tier=risk_tier,
        min_days_overdue=min_days_overdue,
        search=search,
        promise_filter=promise_filter,
    )
