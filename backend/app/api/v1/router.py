"""v1 API router — aggregates all sub-routers."""
from fastapi import APIRouter

from app.api.v1 import (
    auth,
    customers,
    invoices,
    payments,
    follow_ups,
    import_jobs,
    dashboard,
    analytics,
    collections,
    ml,
    reminders,
    export,
)

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(customers.router, prefix="/customers", tags=["customers"])
router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
router.include_router(payments.router, prefix="/payments", tags=["payments"])
router.include_router(follow_ups.router, prefix="/follow-ups", tags=["follow-ups"])
router.include_router(import_jobs.router, prefix="/import", tags=["import"])
router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
router.include_router(collections.router, prefix="/collections", tags=["collections"])
router.include_router(ml.router, prefix="/ml", tags=["ml"])
router.include_router(reminders.router, prefix="/reminders", tags=["reminders"])
router.include_router(export.router, prefix="/export", tags=["export"])
