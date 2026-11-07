"""Prediction module: score invoices with trained models or heuristic fallback."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.ml.features import extract_features
from app.ml.train import load_model, load_classifier, features_to_array, MODEL_VERSION
from app.models.prediction import ModelPrediction
from app.schemas.ml import PredictionOut


def _heuristic_predict(features: dict[str, Any]) -> tuple[float, float, str]:
    """
    Simple heuristic when no trained model is available.
    Returns (predicted_delay_days, delay_probability, risk_tier).
    """
    late_rate = float(features.get("late_payment_rate", 0.35))
    avg_late = float(features.get("avg_days_late", 3.0))
    risk_enc = int(features.get("customer_risk_tier_encoded", 1))

    # Estimated delay in days
    predicted_delay = max(0.0, avg_late * 0.75 + risk_enc * 4.0)

    # Calibrated probability of late payment
    delay_prob = min(0.95, max(0.05, late_rate * 0.70 + risk_enc * 0.12))

    risk_tier = "high" if (delay_prob > 0.60 or predicted_delay >= 15) else ("medium" if delay_prob > 0.30 else "low")
    return round(predicted_delay, 1), round(delay_prob, 3), risk_tier


def predict_invoice(invoice_id: UUID, org_id: UUID, db: Session) -> PredictionOut:
    """Generate and persist a prediction for a single invoice."""
    features = extract_features(invoice_id, org_id, db)
    reg_model = load_model(org_id)
    cls_model = load_classifier(org_id)

    if reg_model is not None and cls_model is not None:
        X = features_to_array(features)
        predicted_delay = max(0.0, float(reg_model.predict(X)[0]))
        probs = cls_model.predict_proba(X)[0]
        delay_prob = float(probs[1]) if len(probs) > 1 else float(probs[0])
        delay_prob = round(min(0.99, max(0.01, delay_prob)), 3)

        if delay_prob >= 0.60 or predicted_delay >= 15.0:
            risk_tier = "high"
        elif delay_prob >= 0.35 or predicted_delay >= 5.0:
            risk_tier = "medium"
        else:
            risk_tier = "low"
    else:
        predicted_delay, delay_prob, risk_tier = _heuristic_predict(features)

    prediction = ModelPrediction(
        org_id=org_id,
        invoice_id=invoice_id,
        model_version=MODEL_VERSION if (reg_model and cls_model) else "heuristic-v1",
        predicted_delay_days=round(predicted_delay, 1),
        delay_probability=delay_prob,
        risk_tier=risk_tier,
        features_json=features,
        predicted_at=datetime.now(timezone.utc),
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return PredictionOut.model_validate(prediction)


def batch_predict(invoice_ids: list[UUID], org_id: UUID, db: Session) -> list[PredictionOut]:
    return [predict_invoice(inv_id, org_id, db) for inv_id in invoice_ids]
