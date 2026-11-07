import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ModelPrediction(Base, TimestampMixin):
    __tablename__ = "model_predictions"
    __table_args__ = (
        Index("ix_predictions_org_invoice", "org_id", "invoice_id"),
        Index("ix_predictions_model_version", "model_version"),
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
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    predicted_delay_days: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delay_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_tier: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    features_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_demo: Mapped[bool] = mapped_column(default=False, nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    invoice = relationship("Invoice", back_populates="predictions")
