from decimal import Decimal
from typing import Optional

from typing import Literal
from pydantic import BaseModel, Field


class CollectionQueueItem(BaseModel):
    invoice_id: str
    invoice_number: str
    customer_id: str
    customer_name: str
    customer_phone: Optional[str] = None
    outstanding_balance: Decimal
    total_amount: Decimal
    due_date: str
    days_overdue: int
    priority_score: float
    priority_reasons: list[str]
    risk_tier: str
    last_follow_up_status: Optional[str] = None
    last_follow_up_date: Optional[str] = None
    open_follow_up_id: Optional[str] = None
    has_broken_promise: bool = False
    promised_date: Optional[str] = None
    promise_status: Optional[str] = None


class CollectionQueueResponse(BaseModel):
    items: list[CollectionQueueItem]
    total: int
    page: int
    per_page: int


class ReminderDraftRequest(BaseModel):
    follow_up_id: str = Field(max_length=64)
    channel: Literal["whatsapp", "sms"] = "whatsapp"
    language: Literal["english", "hindi"] = "english"


class ReminderDraftResponse(BaseModel):
    draft: str
    channel: str
    language: str
    invoice_number: str
    customer_name: str
    outstanding_amount: Decimal
    due_date: str
    is_demo: bool = False


class AnalyticsSummary(BaseModel):
    collection_rate_pct: float
    avg_days_to_payment: float
    overdue_balance: Decimal
    total_invoiced: Decimal
    total_collected: Decimal
    follow_up_completion_rate_pct: float


class MonthlyTrend(BaseModel):
    month: str
    invoiced: Decimal
    collected: Decimal
    outstanding: Decimal


class CustomerOutstanding(BaseModel):
    customer_id: str
    customer_name: str
    total_outstanding: Decimal
    overdue_amount: Decimal
    risk_tier: str


class AgingReport(BaseModel):
    customer_id: str
    customer_name: str
    current: Decimal
    days_1_30: Decimal = Decimal("0")
    days_31_60: Decimal = Decimal("0")
    days_61_90: Decimal = Decimal("0")
    beyond_90: Decimal = Decimal("0")
    days_91_120: Optional[Decimal] = Decimal("0")
    beyond_120: Optional[Decimal] = Decimal("0")
    total: Decimal


class CollectionEfficiency(BaseModel):
    total_invoiced: Decimal
    total_collected: Decimal
    efficiency_pct: float


class PtpStats(BaseModel):
    pending_count: int
    pending_amount: Decimal
    fulfilled_count: int
    fulfilled_amount: Decimal
    broken_count: int
    broken_amount: Decimal
    recovery_rate_pct: float


class AgingBucketTotal(BaseModel):
    bucket: str
    label: str
    amount: Decimal
    count: int
    percentage: float


class ProjectedInflows(BaseModel):
    next_7_days: Decimal
    next_15_days: Decimal
    next_30_days: Decimal


class DebtorConcentrationItem(BaseModel):
    customer_id: str
    customer_name: str
    outstanding: Decimal
    percentage_of_total: float
    risk_tier: str


class DistributorKPIsResponse(BaseModel):
    total_receivables: Decimal
    overdue_receivables: Decimal
    overdue_percentage: float
    dso_days: float
    dso_formula: str
    dso_status: str
    collection_effectiveness_index: float
    cei_formula: str
    active_retailers_count: int
    overdue_retailers_count: int
    ptp_stats: PtpStats
    aging_summary: list[AgingBucketTotal]
    projected_inflows: ProjectedInflows
    top_debtors: list[DebtorConcentrationItem]
    top_5_debtor_concentration_pct: float

