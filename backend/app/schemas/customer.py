from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CustomerBase(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    gst_number: Optional[str] = Field(default=None, max_length=15)
    address: Optional[str] = Field(default=None, max_length=2000)
    credit_limit: Decimal = Decimal("100000.00")
    payment_terms_days: int = 30
    risk_tier: str = "medium"


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=300)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    gst_number: Optional[str] = Field(default=None, max_length=15)
    credit_limit: Optional[Decimal] = None
    payment_terms_days: Optional[int] = None
    risk_tier: Optional[str] = None


class CustomerResponse(CustomerBase):
    id: UUID
    org_id: UUID
    is_active: bool
    created_at: datetime

    # Computed fields (not from DB directly)
    total_outstanding: Optional[Decimal] = None
    total_overdue: Optional[Decimal] = None
    invoice_count: Optional[int] = None

    model_config = {"from_attributes": True}


CustomerOut = CustomerResponse


class CustomerListResponse(BaseModel):
    items: list[CustomerResponse]
    total: int
    page: int
    per_page: int = 50
    page_size: Optional[int] = None

    def __init__(self, **data):
        if "page_size" in data and "per_page" not in data:
            data["per_page"] = data["page_size"]
        elif "per_page" in data and "page_size" not in data:
            data["page_size"] = data["per_page"]
        super().__init__(**data)


class CustomerCreditSummary(BaseModel):
    credit_limit: Decimal
    total_outstanding: Decimal
    available_credit: Decimal
    utilization_pct: float
    total_overdue: Decimal
    overdue_invoices_count: int
    lifetime_invoiced: Decimal
    lifetime_collected: Decimal
    health_status: str


class CustomerAgingSummary(BaseModel):
    current: Decimal
    days_1_30: Decimal
    days_31_60: Decimal
    days_61_90: Decimal
    beyond_90: Decimal


class CustomerLedgerEntry(BaseModel):
    id: str
    entry_type: str  # "INVOICE" | "PAYMENT"
    date: date
    reference: str
    debit: Optional[Decimal] = None
    credit: Optional[Decimal] = None
    running_balance: Decimal
    status: str
    notes: Optional[str] = None


class CustomerOpenInvoiceItem(BaseModel):
    id: UUID
    invoice_number: str
    issue_date: date
    due_date: date
    days_overdue: int
    total_amount: Decimal
    paid_amount: Decimal
    outstanding_balance: Decimal
    status: str


class CustomerPtpItem(BaseModel):
    id: UUID
    invoice_id: UUID
    invoice_number: str
    promised_amount: Optional[Decimal] = None
    promised_date: Optional[date] = None
    promise_status: Optional[str] = None
    channel: str
    notes: Optional[str] = None
    created_at: datetime


class CustomerLedgerResponse(BaseModel):
    customer: CustomerResponse
    credit_summary: CustomerCreditSummary
    aging_summary: CustomerAgingSummary
    ledger: list[CustomerLedgerEntry]
    open_invoices: list[CustomerOpenInvoiceItem]
    promises: list[CustomerPtpItem]
