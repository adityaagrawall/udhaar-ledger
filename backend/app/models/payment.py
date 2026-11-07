import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class PaymentMode(str, PyEnum):
    cash = "cash"
    cheque = "cheque"
    neft = "neft"
    rtgs = "rtgs"
    upi = "upi"
    other = "other"


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_org_customer", "org_id", "customer_id"),
        Index("ix_payments_received_date", "received_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True
    )
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    reference_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payment_mode: Mapped[str] = mapped_column(
        Enum(PaymentMode, name="payment_mode"), default=PaymentMode.neft, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    customer = relationship("Customer", back_populates="payments")
    allocations = relationship("PaymentAllocation", back_populates="payment", cascade="all, delete-orphan")


class PaymentAllocation(Base, TimestampMixin):
    __tablename__ = "payment_allocations"
    __table_args__ = (
        Index("ix_payment_alloc_invoice", "invoice_id"),
        Index("ix_payment_alloc_payment", "payment_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False, index=True
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False, index=True
    )
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    allocated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    payment = relationship("Payment", back_populates="allocations")
    invoice = relationship("Invoice", back_populates="payment_allocations")
