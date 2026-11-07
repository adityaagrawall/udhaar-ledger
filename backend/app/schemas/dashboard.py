from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class AgingBucket(BaseModel):
    label: str
    days_min: int
    days_max: Optional[int]  # None = unbounded
    amount: Decimal
    invoice_count: int
    percentage: float


class DashboardSummary(BaseModel):
    # Key metrics
    total_outstanding: Decimal
    total_overdue: Decimal
    overdue_count: int
    collected_this_month: Decimal
    collection_rate_pct: float  # % of invoiced amount collected

    # Buckets
    aging_buckets: list[AgingBucket]

    # Workload
    pending_follow_ups: int
    invoices_due_this_week: int
    high_risk_outstanding: Decimal

    # Data label
    is_synthetic: bool = True


class CollectionTrendPoint(BaseModel):
    month: str  # YYYY-MM
    invoiced: Decimal
    collected: Decimal
    overdue: Decimal
    collection_rate_pct: float


class AgingReport(BaseModel):
    buckets: list[AgingBucket]
    total_outstanding: Decimal
    as_of_date: str
