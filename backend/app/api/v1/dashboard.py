from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_org_id
from app.schemas.dashboard import AgingReport, DashboardSummary
from app.services.dashboard_service import get_collection_trend, get_dashboard_summary

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    return get_dashboard_summary(db, UUID(org_id))


@router.get("/trend")
def collection_trend(
    months: int = Query(6, ge=1, le=24),
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    return get_collection_trend(db, UUID(org_id), months=months)
