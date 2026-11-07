"""Tests for ML classification, regression, and evaluation metrics."""
import pytest
import numpy as np
from app.ml.evaluate import evaluate_classification, evaluate_regression


def test_evaluate_classification_perfect():
    y_true = [0, 0, 1, 1, 1]
    y_pred = [0, 0, 1, 1, 1]
    y_prob = [0.1, 0.2, 0.8, 0.9, 0.95]

    metrics = evaluate_classification(y_true, y_pred, y_prob)
    assert metrics["accuracy"] == 1.0
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1_score"] == 1.0
    assert metrics["roc_auc"] == 1.0
    assert metrics["confusion_matrix"]["true_negatives"] == 2
    assert metrics["confusion_matrix"]["true_positives"] == 3
    assert metrics["confusion_matrix"]["false_positives"] == 0
    assert metrics["confusion_matrix"]["false_negatives"] == 0


def test_evaluate_classification_mixed():
    y_true = [1, 1, 0, 0]
    y_pred = [1, 0, 0, 1]  # 1 TP, 1 FN, 1 TN, 1 FP
    y_prob = [0.8, 0.4, 0.3, 0.7]

    metrics = evaluate_classification(y_true, y_pred, y_prob)
    assert metrics["accuracy"] == 0.5
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1_score"] == 0.5
    assert metrics["confusion_matrix"]["true_positives"] == 1
    assert metrics["confusion_matrix"]["false_positives"] == 1
    assert metrics["confusion_matrix"]["true_negatives"] == 1
    assert metrics["confusion_matrix"]["false_negatives"] == 1


def test_evaluate_regression():
    preds = [10.0, 5.0, 0.0]
    actuals = [8.0, 5.0, 2.0]

    metrics = evaluate_regression(preds, actuals)
    # Errors: |10-8|=2, |5-5|=0, |0-2|=2 -> mean = 4/3 = 1.33
    assert round(metrics["mae_days"], 2) == 1.33
    assert "rmse_days" in metrics
    assert "directional_accuracy" in metrics
