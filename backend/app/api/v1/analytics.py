"""Analytics endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.schemas.analytics import MonthlyTrend, CustomerOutstanding, AgingReport, DistributorKPIsResponse
import app.services.analytics_service as svc

router = APIRouter()


@router.get("/distributor-kpis", response_model=DistributorKPIsResponse)
def get_distributor_kpis(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.get_distributor_kpis(current_user.org_id, db)


@router.get("/trends", response_model=list[MonthlyTrend])
def get_trends(
    months: int = Query(12, ge=1, le=36),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.get_monthly_trends(current_user.org_id, db, months)


@router.get("/top-outstanding", response_model=list[CustomerOutstanding])
def get_top_outstanding(
    limit: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.get_top_outstanding_customers(current_user.org_id, db, limit)


@router.get("/aging-report", response_model=list[AgingReport])
def get_aging_report(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.get_aging_report(current_user.org_id, db)
