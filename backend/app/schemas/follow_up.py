from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class FollowUpCreate(BaseModel):
    invoice_id: UUID
    customer_id: UUID
    status: str = "pending"
    channel: str = "whatsapp"
    notes: Optional[str] = Field(default=None, max_length=2000)
    scheduled_at: Optional[datetime] = None
    promised_amount: Optional[Decimal] = None
    promised_date: Optional[date] = None
    promise_status: Optional[str] = None


class FollowUpUpdate(BaseModel):
    status: Optional[str] = None
    channel: Optional[str] = None
    notes: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    reminder_draft: Optional[str] = None
    reminder_approved: Optional[bool] = None
    promised_amount: Optional[Decimal] = None
    promised_date: Optional[date] = None
    promise_status: Optional[str] = None


class FollowUpResponse(BaseModel):
    id: UUID
    org_id: UUID
    invoice_id: UUID
    customer_id: UUID
    status: str
    channel: str
    notes: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    reminder_draft: Optional[str] = None
    reminder_approved: bool
    promised_amount: Optional[Decimal] = None
    promised_date: Optional[date] = None
    promise_status: Optional[str] = None
    created_at: datetime

    # Enriched
    customer_name: Optional[str] = None
    invoice_number: Optional[str] = None
    outstanding_balance: Optional[Decimal] = None

    model_config = {"from_attributes": True}


FollowUpOut = FollowUpResponse


class FollowUpListResponse(BaseModel):
    items: list[FollowUpResponse]
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
