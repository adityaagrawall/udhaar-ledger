from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AllocationIn(BaseModel):
    invoice_id: UUID
    allocated_amount: Decimal


class PaymentCreate(BaseModel):
    customer_id: UUID
    received_date: date
    amount: Decimal
    reference_no: Optional[str] = Field(default=None, max_length=100)
    payment_mode: str = Field(default="neft", max_length=20)
    notes: Optional[str] = Field(default=None, max_length=2000)
    # Invoice allocations: list of allocations to specific invoices
    allocations: list[AllocationIn] = []

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Payment amount must be positive")
        return v


class AllocationOut(BaseModel):
    id: UUID
    invoice_id: UUID
    invoice_number: Optional[str] = None
    allocated_amount: Decimal
    allocated_at: datetime

    model_config = {"from_attributes": True}


class SuggestedAllocationItem(BaseModel):
    invoice_id: UUID
    invoice_number: str
    issue_date: date
    due_date: date
    days_overdue: int
    total_amount: Decimal
    outstanding_balance: Decimal
    suggested_allocated_amount: Decimal
    status: str


class FifoAllocationSuggestionResponse(BaseModel):
    customer_id: UUID
    customer_name: str
    total_payment_amount: Decimal
    total_outstanding: Decimal
    total_allocated: Decimal
    unallocated_amount: Decimal
    invoices_covered: int
    allocations: list[SuggestedAllocationItem]


class PaymentResponse(BaseModel):
    id: UUID
    org_id: UUID
    customer_id: UUID
    received_date: date
    amount: Decimal
    reference_no: Optional[str] = None
    payment_mode: str
    notes: Optional[str] = None
    created_at: datetime
    customer_name: Optional[str] = None
    unallocated_amount: Optional[Decimal] = None
    allocations: list[AllocationOut] = []

    model_config = {"from_attributes": True}


PaymentOut = PaymentResponse


class PaymentListResponse(BaseModel):
    items: list[PaymentResponse]
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
