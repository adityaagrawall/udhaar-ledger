"""ML and payment delay prediction endpoints."""
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
import numpy as np

from app.core.deps import get_db, get_current_user, require_roles
from app.ml.predict import predict_invoice, batch_predict
from app.ml.train import train_model, load_model, load_classifier, FEATURE_COLS, MODEL_VERSION
from app.ml.evaluate import feature_importance, evaluate_classification, evaluate_regression
from app.ml.features import extract_features
from app.schemas.ml import PredictionRequest, PredictionOut, BatchPredictionRequest, BatchPredictionResponse

router = APIRouter()


@router.post("/predict", response_model=PredictionOut)
def predict_single_invoice(
    payload: PredictionRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return predict_invoice(payload.invoice_id, current_user.org_id, db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/predict/batch", response_model=BatchPredictionResponse)
def predict_batch_invoices(
    payload: BatchPredictionRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        preds = batch_predict(payload.invoice_ids, current_user.org_id, db)
        return BatchPredictionResponse(
            predictions=preds,
            model_version=MODEL_VERSION if load_model(current_user.org_id) else "heuristic-v1",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/evaluation")
def get_ml_evaluation(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    reg_model = load_model(current_user.org_id)
    cls_model = load_classifier(current_user.org_id)

    importances = feature_importance(reg_model or cls_model) if (reg_model or cls_model) else []
    computed_metrics: dict[str, Any] = {}

    if reg_model and cls_model:
        try:
            rows = db.execute(
                text("""
                    SELECT i.id, i.due_date, i.issue_date, MAX(p.received_date) AS final_payment_date
                    FROM invoices i
                    JOIN payment_allocations pa ON pa.invoice_id = i.id
                    JOIN payments p ON p.id = pa.payment_id
                    WHERE i.org_id = :org_id AND i.status = 'paid' AND i.deleted_at IS NULL
                    GROUP BY i.id, i.due_date, i.issue_date
                    HAVING COUNT(pa.id) > 0
                    ORDER BY i.issue_date
                """),
                {"org_id": str(current_user.org_id)},
            ).fetchall()

            if len(rows) >= 20:
                feature_dicts = []
                labels_days = []
                labels_binary = []
                for r in rows:
                    try:
                        feats = extract_features(r.id, current_user.org_id, db, as_of=r.issue_date)
                        delay = max(0.0, float((r.final_payment_date - r.due_date).days))
                        feature_dicts.append(feats)
                        labels_days.append(delay)
                        labels_binary.append(1 if delay > 0 else 0)
                    except Exception:
                        continue

                if len(feature_dicts) >= 20:
                    split = int(0.8 * len(feature_dicts))
                    train_labels_days = labels_days[:split]
                    test_features = feature_dicts[split:]
                    test_labels_days = labels_days[split:]
                    test_labels_binary = labels_binary[split:]

                    test_X = np.array([[float(f.get(col, 0.0)) for col in FEATURE_COLS] for f in test_features])

                    # Classification metrics
                    cls_probs = cls_model.predict_proba(test_X)[:, 1]
                    cls_preds = (cls_probs >= 0.40).astype(int)
                    cls_metrics = evaluate_classification(test_labels_binary, cls_preds, cls_probs)

                    # Regression metrics
                    reg_preds = np.maximum(0.0, reg_model.predict(test_X))
                    reg_metrics = evaluate_regression(list(reg_preds), test_labels_days)

                    base_delay = float(np.mean(train_labels_days))
                    base_mae = float(np.mean(np.abs(np.array(test_labels_days) - base_delay)))
                    err_reduction = round(((base_mae - reg_metrics["mae_days"]) / base_mae) * 100, 1)

                    computed_metrics = {
                        # Regression
                        "mae_days": reg_metrics["mae_days"],
                        "rmse_days": reg_metrics["rmse_days"],
                        "baseline_mae_days": round(base_mae, 2),
                        "directional_accuracy": reg_metrics["directional_accuracy"],
                        "error_reduction_pct": err_reduction,
                        # Classification
                        "f1_score": cls_metrics["f1_score"],
                        "f1_macro": cls_metrics["f1_macro"],
                        "f1_weighted": cls_metrics["f1_weighted"],
                        "accuracy": cls_metrics["accuracy"],
                        "precision": cls_metrics["precision"],
                        "recall": cls_metrics["recall"],
                        "roc_auc": cls_metrics.get("roc_auc", 0.5),
                        "pr_auc": cls_metrics.get("pr_auc", 0.5),
                        "brier_score": cls_metrics.get("brier_score", 0.2),
                        "confusion_matrix": cls_metrics["confusion_matrix"],
                        # Data split sizes
                        "test_samples": len(test_features),
                        "train_samples": split,
                        "evaluation_method": "chronological_holdout_20pct",
                        "note": "Evaluated strictly on held-out 20% newest invoices sorted by issue_date.",
                    }
        except Exception as e:
            computed_metrics = {"error": f"Metric computation failed: {str(e)}"}

    return {
        "status": "ready" if (reg_model and cls_model) else "demo_heuristic",
        "model_version": MODEL_VERSION if (reg_model and cls_model) else "heuristic-v1",
        "target": "payment_delay_days & is_delinquent",
        "description": "Dual pipeline: Gradient Boosting Classifier for delay probability + Regressor for days late magnitude",
        "metrics": computed_metrics if computed_metrics else {
            "note": "No trained model. Train via POST /api/v1/ml/train to get real metrics."
        },
        "feature_importance": importances,
        "is_demo": reg_model is None or cls_model is None,
    }


@router.post("/train")
def trigger_training(
    current_user=Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    try:
        metrics = train_model(current_user.org_id, db)
        return {"status": "trained", "metrics": metrics}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Training failed: {e}")
