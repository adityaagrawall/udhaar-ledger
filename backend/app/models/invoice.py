import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import expression
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class InvoiceStatus(str, PyEnum):
    draft = "draft"
    sent = "sent"
    partial = "partial"
    paid = "paid"
    overdue = "overdue"
    cancelled = "cancelled"


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("org_id", "invoice_number", name="uq_invoice_number_per_org"),
        Index("ix_invoices_org_status", "org_id", "status"),
        Index("ix_invoices_org_customer", "org_id", "customer_id"),
        Index("ix_invoices_org_due_date", "org_id", "due_date"),
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
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status"), default=InvoiceStatus.sent, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Disputed invoices are excluded from chasing and routed to the "Resolve" lane.
    is_disputed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=expression.false(), nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="invoices")
    customer = relationship("Customer", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    payment_allocations = relationship("PaymentAllocation", back_populates="invoice")
    follow_ups = relationship("FollowUp", back_populates="invoice")
    predictions = relationship("ModelPrediction", back_populates="invoice")


class InvoiceItem(Base, TimestampMixin):
    __tablename__ = "invoice_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("1.000"), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    # Relationships
    invoice = relationship("Invoice", back_populates="items")
