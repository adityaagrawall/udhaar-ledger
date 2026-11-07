"""Schemas for the lane-based 'Today' worklist (case study Section 6/7)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class TodayAccount(BaseModel):
    customer_id: UUID
    customer_name: str
    customer_phone: Optional[str] = None
    lane: str  # call | escalate | resolve | message
    overdue_amount: Decimal
    oldest_days_past_due: int
    open_invoice_count: int
    pattern: str  # pays_when_asked | pays_on_its_own | missed_promise | unresponsive | thin_history | no_clear_pattern
    limited_history: bool
    # Raw value of the ranking formula. Lanes carry the meaning; the UI must not
    # present this as a rank number (the order is only stable as a tier).
    score: Optional[float] = None
    reason: str
    suggested_action: str
    what_would_change: str
    days_since_last_contact: Optional[int] = None
    invoice_ids: list[UUID]
    disputed_invoice_numbers: list[str] = []
    disputed_invoice_ids: list[UUID] = []


class TodayResponse(BaseModel):
    as_of: date
    call_slots: int
    call: list[TodayAccount]
    escalate: list[TodayAccount]
    resolve: list[TodayAccount]
    message: list[TodayAccount]
    days_since_last_receipt: Optional[int] = None
    data_stale: bool
    method: str = "rules-v1 (assumed weights, not validated on real outcomes)"


class DisputeUpdate(BaseModel):
    disputed: bool
