"""ML training module for Udhaar Ledger dual classifier & regressor pipeline."""
from __future__ import annotations

import json
import os
import pickle
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from app.ml.features import FEATURE_COLS

MODEL_DIR = Path(__file__).parent / "artifacts"


def _org_dir(org_id: UUID) -> Path:
    """Models are trained on one organisation's data and must never be shared across tenants."""
    return MODEL_DIR / str(org_id)


def regressor_path(org_id: UUID) -> Path:
    return _org_dir(org_id) / "delay_model.pkl"


def classifier_path(org_id: UUID) -> Path:
    return _org_dir(org_id) / "delay_classifier.pkl"


MODEL_VERSION = "v2.0-dual"


def features_to_array(features: dict[str, Any]) -> np.ndarray:
    return np.array([[float(features.get(col, 0.0)) for col in FEATURE_COLS]])


def train_regressor(feature_dicts: list[dict[str, Any]], labels: list[float]) -> Pipeline:
    """Train GradientBoostingRegressor for payment delay days."""
    X = np.array([[float(f.get(col, 0.0)) for col in FEATURE_COLS] for f in feature_dicts])
    y = np.array(labels, dtype=float)

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model", GradientBoostingRegressor(
            n_estimators=150,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.85,
            random_state=42,
        )),
    ])
    pipeline.fit(X, y)
    return pipeline


def train_classifier(feature_dicts: list[dict[str, Any]], labels_binary: list[int]) -> Pipeline:
    """Train GradientBoostingClassifier for probability of delay."""
    X = np.array([[float(f.get(col, 0.0)) for col in FEATURE_COLS] for f in feature_dicts])
    y = np.array(labels_binary, dtype=int)

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model", GradientBoostingClassifier(
            n_estimators=120,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.85,
            random_state=42,
        )),
    ])
    pipeline.fit(X, y)
    return pipeline


def train(feature_dicts: list[dict[str, Any]], labels: list[float], org_id: UUID) -> None:
    """
    Train and persist both the classifier and regressor models.
    Labels are actual delay days (0 = on time, >0 = late).
    """
    if len(feature_dicts) < 10:
        raise ValueError("Need at least 10 training samples")

    labels_binary = [1 if d > 0 else 0 for d in labels]

    reg_pipeline = train_regressor(feature_dicts, labels)
    cls_pipeline = train_classifier(feature_dicts, labels_binary)

    _org_dir(org_id).mkdir(parents=True, exist_ok=True)
    with open(regressor_path(org_id), "wb") as f:
        pickle.dump(reg_pipeline, f)
    with open(classifier_path(org_id), "wb") as f:
        pickle.dump(cls_pipeline, f)

    print(f"Models trained on {len(feature_dicts)} samples for org {org_id}")


def load_model(org_id: UUID):
    """Load this organisation's regressor. Returns None if not trained."""
    path = regressor_path(org_id)
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def load_classifier(org_id: UUID):
    """Load this organisation's classifier. Returns None if not trained."""
    path = classifier_path(org_id)
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def train_model(org_id: UUID, db: Any) -> dict[str, Any]:
    """
    Extract historical paid invoices and train dual models on a chronological split.
    Returns both classification (F1, Accuracy, Precision, Recall, PR-AUC, ROC-AUC)
    and regression metrics (MAE, RMSE, Baseline MAE).
    """
    from sqlalchemy import text
    from app.ml.features import extract_features
    from app.ml.evaluate import evaluate_classification, evaluate_regression

    rows = db.execute(
        text("""
            SELECT i.id, i.due_date, i.issue_date, MAX(p.received_date) AS final_payment_date
            FROM invoices i
            JOIN payment_allocations pa ON pa.invoice_id = i.id
            JOIN payments p ON p.id = pa.payment_id
            WHERE i.org_id = :org_id AND i.status = 'paid' AND i.deleted_at IS NULL
            GROUP BY i.id, i.due_date, i.issue_date
            HAVING COUNT(pa.id) > 0
            ORDER BY i.issue_date  -- strict chronological sorting to prevent future leakage
        """),
        {"org_id": str(org_id)},
    ).fetchall()

    if len(rows) < 10:
        raise ValueError(f"Insufficient historical paid records ({len(rows)} found, minimum 10 required for training)")

    feature_dicts = []
    labels_days = []
    labels_binary = []

    for r in rows:
        try:
            feats = extract_features(r.id, org_id, db, as_of=r.issue_date)
            delay = max(0.0, float((r.final_payment_date - r.due_date).days))
            feature_dicts.append(feats)
            labels_days.append(delay)
            labels_binary.append(1 if delay > 0 else 0)
        except Exception:
            continue

    if len(feature_dicts) < 10:
        raise ValueError(f"Only {len(feature_dicts)} valid feature sets extracted; minimum 10 required.")

    # Chronological 80/20 train/test split
    split = int(0.8 * len(feature_dicts))
    train_features = feature_dicts[:split]
    test_features = feature_dicts[split:]

    train_labels_days = labels_days[:split]
    test_labels_days = labels_days[split:]

    train_labels_binary = labels_binary[:split]
    test_labels_binary = labels_binary[split:]

    # Train and persist models using the training split
    train(train_features, train_labels_days, org_id)

    # Load persisted models to evaluate on held-out test split
    reg_model = load_model(org_id)
    cls_model = load_classifier(org_id)

    test_X = np.array([[float(f.get(col, 0.0)) for col in FEATURE_COLS] for f in test_features])

    # Classifier evaluation
    cls_probs = cls_model.predict_proba(test_X)[:, 1]
    cls_preds = (cls_probs >= 0.40).astype(int)  # fixed 0.40 operating point (not tuned on the test split)
    cls_metrics = evaluate_classification(test_labels_binary, cls_preds, cls_probs)

    # Regressor evaluation
    reg_preds = np.maximum(0.0, reg_model.predict(test_X))
    reg_metrics = evaluate_regression(list(reg_preds), test_labels_days)

    # Baseline calculations
    baseline_delay = float(np.mean(train_labels_days))
    base_mae = float(np.mean(np.abs(np.array(test_labels_days) - baseline_delay)))
    reg_metrics["baseline_mae_days"] = round(base_mae, 2)
    reg_metrics["error_reduction_pct"] = round(((base_mae - reg_metrics["mae_days"]) / base_mae) * 100, 1)

    return {
        "status": "success",
        "model_version": MODEL_VERSION,
        "train_samples": split,
        "test_samples": len(test_features),
        "classification": cls_metrics,
        "regression": reg_metrics,
    }
