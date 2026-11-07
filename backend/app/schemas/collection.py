"""Collection priority queue schemas."""
from __future__ import annotations
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class PriorityInvoice(BaseModel):
    invoice_id: UUID
    invoice_number: str
    customer_id: UUID
    customer_name: str
    risk_tier: str
    outstanding_balance: Decimal
    days_overdue: int
    priority_score: float
    priority_reasons: list[str]
    last_follow_up_days_ago: int | None


class CollectionQueueResponse(BaseModel):
    items: list[PriorityInvoice]
    total: int
