"""ML / prediction schemas."""
from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    invoice_id: UUID


class PredictionOut(BaseModel):
    id: UUID
    invoice_id: UUID
    model_version: str
    predicted_delay_days: float
    delay_probability: float
    risk_tier: str
    features_json: dict[str, Any] | None = None
    predicted_at: datetime

    model_config = {"from_attributes": True}


class BatchPredictionRequest(BaseModel):
    invoice_ids: list[UUID] = Field(max_length=100)


class BatchPredictionResponse(BaseModel):
    predictions: list[PredictionOut]
    model_version: str
