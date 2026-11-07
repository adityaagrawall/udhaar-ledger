from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator


class InvoiceItemCreate(BaseModel):
    description: str
    quantity: Decimal = Decimal("1.000")
    unit_price: Decimal
    line_total: Optional[Decimal] = None

    @model_validator(mode="after")
    def compute_line_total(self) -> "InvoiceItemCreate":
        if self.line_total is None:
            self.line_total = self.quantity * self.unit_price
        return self


class InvoiceItemResponse(BaseModel):
    id: UUID
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


class InvoiceCreate(BaseModel):
    customer_id: UUID
    invoice_number: str
    issue_date: date
    due_date: date
    total_amount: Decimal
    notes: Optional[str] = None
    items: list[InvoiceItemCreate] = []

    @field_validator("total_amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("total_amount must be positive")
        return v

    @model_validator(mode="after")
    def due_date_after_issue(self) -> "InvoiceCreate":
        if self.due_date < self.issue_date:
            raise ValueError("due_date must be on or after issue_date")
        return self


class InvoiceUpdate(BaseModel):
    notes: Optional[str] = None
    status: Optional[str] = None


class PaymentAllocationResponse(BaseModel):
    id: UUID
    payment_id: UUID
    allocated_amount: Decimal
    allocated_at: datetime

    model_config = {"from_attributes": True}


class InvoiceResponse(BaseModel):
    id: UUID
    org_id: UUID
    customer_id: UUID
    invoice_number: str
    issue_date: date
    due_date: date
    total_amount: Decimal
    status: str
    notes: Optional[str] = None
    created_at: datetime

    # Computed
    outstanding_balance: Optional[Decimal] = None
    days_overdue: Optional[int] = None
    customer_name: Optional[str] = None
    allocations: list[PaymentAllocationResponse] = []

    model_config = {"from_attributes": True}


InvoiceOut = InvoiceResponse


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int
    page: int
    per_page: int
