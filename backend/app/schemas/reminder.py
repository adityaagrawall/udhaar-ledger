"""Reminder schemas."""
from __future__ import annotations
from uuid import UUID

from pydantic import BaseModel


class ReminderRequest(BaseModel):
    invoice_id: UUID
    channel: str = "email"  # whatsapp / sms / call / email
    message: str | None = None  # if None, LLM generates it


class ReminderResponse(BaseModel):
    follow_up_id: UUID
    channel: str
    message_sent: str
    status: str


class BulkReminderRequest(BaseModel):
    invoice_ids: list[UUID]
    channel: str = "email"
    message: str | None = None


class BulkReminderResponse(BaseModel):
    sent: int
    failed: int
    results: list[ReminderResponse]
