import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class RiskTier(str, PyEnum):
    low = "low"
    medium = "medium"
    high = "high"


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_customers_org_name", "org_id", "name"),
        Index("ix_customers_org_active", "org_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    gst_number: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    credit_limit: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("100000.00"), nullable=False
    )
    payment_terms_days: Mapped[int] = mapped_column(default=30, nullable=False)
    risk_tier: Mapped[str] = mapped_column(
        Enum(RiskTier, name="risk_tier"), default=RiskTier.medium, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="customers")
    invoices = relationship("Invoice", back_populates="customer")
    payments = relationship("Payment", back_populates="customer")
    follow_ups = relationship("FollowUp", back_populates="customer")
