"""Follow-up endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.schemas.follow_up import FollowUpCreate, FollowUpUpdate, FollowUpOut, FollowUpListResponse
import app.services.follow_up_service as svc

router = APIRouter()


@router.get("/ptp-summary", response_model=svc.PtpStats)
def get_ptp_summary(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.get_ptp_summary(current_user.org_id, db)


@router.post("/sync-ptp")
def sync_ptp(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.sync_ptp_statuses(current_user.org_id, db)


@router.get("", response_model=FollowUpListResponse)
def list_follow_ups(
    invoice_id: UUID | None = Query(None),
    customer_id: UUID | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.list_follow_ups(current_user.org_id, db, invoice_id, customer_id, status, page, page_size)


@router.post("", response_model=FollowUpOut, status_code=201)
def create_follow_up(
    payload: FollowUpCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.create_follow_up(payload, current_user.org_id, current_user.id, db)


@router.get("/{follow_up_id}", response_model=FollowUpOut)
def get_follow_up(
    follow_up_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.get_follow_up(follow_up_id, current_user.org_id, db)


@router.patch("/{follow_up_id}", response_model=FollowUpOut)
def update_follow_up(
    follow_up_id: UUID,
    payload: FollowUpUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.update_follow_up(follow_up_id, current_user.org_id, payload, db)
