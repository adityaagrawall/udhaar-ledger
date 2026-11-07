"""ML evaluation utilities for both classification and regression metrics."""
from __future__ import annotations

from typing import Any
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
    brier_score_loss,
    mean_absolute_error,
    root_mean_squared_error,
)


def evaluate_classification(
    y_true: list[int] | np.ndarray,
    y_pred: list[int] | np.ndarray,
    y_prob: list[float] | np.ndarray | None = None,
) -> dict[str, Any]:
    """
    Compute comprehensive classification metrics.
    Includes Accuracy, Precision, Recall, F1 Score (binary, macro, weighted),
    ROC-AUC, PR-AUC (Average Precision), and Confusion Matrix.
    """
    yt = np.array(y_true, dtype=int)
    yp = np.array(y_pred, dtype=int)

    acc = float(accuracy_score(yt, yp))
    prec = float(precision_score(yt, yp, zero_division=0))
    rec = float(recall_score(yt, yp, zero_division=0))
    f1 = float(f1_score(yt, yp, zero_division=0))
    f1_macro = float(f1_score(yt, yp, average="macro", zero_division=0))
    f1_weighted = float(f1_score(yt, yp, average="weighted", zero_division=0))

    cm = confusion_matrix(yt, yp)
    if cm.shape == (2, 2):
        tn, fp, fn, tp = map(int, cm.ravel())
    else:
        tn, fp, fn, tp = int(cm[0, 0]), 0, 0, 0

    metrics: dict[str, Any] = {
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1_score": round(f1, 4),
        "f1_macro": round(f1_macro, 4),
        "f1_weighted": round(f1_weighted, 4),
        "confusion_matrix": {
            "true_negatives": tn,
            "false_positives": fp,
            "false_negatives": fn,
            "true_positives": tp,
        },
        "n_samples": len(yt),
    }

    if y_prob is not None:
        ypr = np.array(y_prob, dtype=float)
        try:
            metrics["roc_auc"] = round(float(roc_auc_score(yt, ypr)), 4)
            metrics["pr_auc"] = round(float(average_precision_score(yt, ypr)), 4)
            metrics["brier_score"] = round(float(brier_score_loss(yt, ypr)), 4)
        except Exception:
            metrics["roc_auc"] = 0.5
            metrics["pr_auc"] = round(float(np.mean(yt)), 4)
            metrics["brier_score"] = 0.25

    return metrics


def evaluate_regression(
    predictions: list[float] | np.ndarray,
    actuals: list[float] | np.ndarray,
) -> dict[str, float]:
    """
    Compute regression metrics for delay prediction.
    Returns MAE, RMSE, and directional accuracy.
    """
    preds = np.array(predictions, dtype=float)
    acts = np.array(actuals, dtype=float)

    mae = float(np.mean(np.abs(preds - acts)))
    rmse = float(np.sqrt(np.mean((preds - acts) ** 2)))

    # Directional accuracy: predicted late when actually late, on-time when on-time
    pred_late = preds > 0
    actual_late = acts > 0
    directional_acc = float(np.mean(pred_late == actual_late))

    return {
        "mae_days": round(mae, 2),
        "rmse_days": round(rmse, 2),
        "directional_accuracy": round(directional_acc, 3),
        "n_samples": len(preds),
    }


def evaluate(predictions: list[float], actuals: list[float]) -> dict[str, float]:
    """Backward compatibility wrapper for evaluate_regression."""
    return evaluate_regression(predictions, actuals)


def feature_importance(model_pipeline) -> list[dict[str, Any]]:
    """Extract feature importances from the trained model pipeline."""
    from app.ml.features import FEATURE_COLS

    try:
        if hasattr(model_pipeline, "named_steps"):
            model = model_pipeline.named_steps.get("model", model_pipeline)
        else:
            model = model_pipeline

        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
        elif hasattr(model, "coef_"):
            importances = np.abs(model.coef_[0])
        else:
            return []

        return sorted(
            [{"feature": col, "importance": float(imp)} for col, imp in zip(FEATURE_COLS, importances)],
            key=lambda x: x["importance"],
            reverse=True,
        )
    except Exception:
        return []
