import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class FollowUpStatus(str, PyEnum):
    pending = "pending"
    contacted = "contacted"
    promised = "promised"
    resolved = "resolved"
    escalated = "escalated"


class FollowUpChannel(str, PyEnum):
    whatsapp = "whatsapp"
    sms = "sms"
    call = "call"
    email = "email"
    in_person = "in_person"


class FollowUp(Base, TimestampMixin):
    __tablename__ = "follow_ups"
    __table_args__ = (
        Index("ix_followup_org_status", "org_id", "status"),
        Index("ix_followup_invoice", "invoice_id"),
        Index("ix_followup_org_customer", "org_id", "customer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        Enum(FollowUpStatus, name="follow_up_status"),
        default=FollowUpStatus.pending,
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(
        Enum(FollowUpChannel, name="follow_up_channel"),
        default=FollowUpChannel.whatsapp,
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reminder_draft: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reminder_approved: Mapped[bool] = mapped_column(default=False, nullable=False)
    promised_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    promised_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    promise_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    # Relationships
    invoice = relationship("Invoice", back_populates="follow_ups")
    customer = relationship("Customer", back_populates="follow_ups")
    creator = relationship("User", foreign_keys=[created_by])
