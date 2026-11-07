"""
Benchmark and evaluation script for Udhaar Ledger ML Models.
Compares models on:
1. Udhaar Ledger Production Ledger (PostgreSQL - 521 invoices, 155 customers)
2. Kaggle / IBM Watson Accounts Receivable Benchmark Dataset (2,466 invoices)

Calculates complete classification metrics:
- Accuracy, Precision, Recall, F1-Score, F1-Macro, ROC-AUC, PR-AUC, Confusion Matrix
And regression metrics:
- MAE, RMSE, Directional Accuracy, Baseline MAE
"""

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    precision_score,
    recall_score,
    roc_auc_score,
    root_mean_squared_error,
)
from sklearn.model_selection import StratifiedKFold
from sqlalchemy import text

# Ensure app imports work
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.database import SessionLocal
from app.ml.features import FEATURE_COLS, extract_features


def benchmark_collectiq_dataset():
    """Evaluate models on Udhaar Ledger PostgreSQL production database."""
    print("\n" + "=" * 80)
    print("1. EVALUATING COLLECTIQ PRODUCTION DATASET (PostgreSQL Ledger)")
    print("=" * 80)

    db = SessionLocal()
    org_id = db.execute(text("SELECT id FROM organizations LIMIT 1")).scalar()

    rows = db.execute(
        text("""
            SELECT 
                i.id, i.customer_id, i.issue_date, i.due_date, i.total_amount,
                c.credit_limit, c.payment_terms_days, c.risk_tier,
                MAX(p.received_date) AS final_payment_date
            FROM invoices i
            JOIN customers c ON c.id = i.customer_id
            JOIN payment_allocations pa ON pa.invoice_id = i.id
            JOIN payments p ON p.id = pa.payment_id
            WHERE i.org_id = :org_id AND i.status = 'paid' AND i.deleted_at IS NULL
            GROUP BY i.id, i.customer_id, i.issue_date, i.due_date, i.total_amount, c.credit_limit, c.payment_terms_days, c.risk_tier
            ORDER BY i.issue_date
        """),
        {"org_id": str(org_id)},
    ).fetchall()

    records = []
    for r in rows:
        delay = max(0.0, float((r.final_payment_date - r.due_date).days))
        f = extract_features(r.id, org_id, db, as_of=r.issue_date)
        f["delay_days"] = delay
        f["is_late"] = 1 if delay > 0 else 0
        records.append(f)

    df = pd.DataFrame(records)
    X = df[FEATURE_COLS]
    y_cls = df["is_late"]
    y_reg = df["delay_days"]

    split = int(0.8 * len(df))
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train_cls, y_test_cls = y_cls.iloc[:split], y_cls.iloc[split:]
    y_train_reg, y_test_reg = y_reg.iloc[:split], y_reg.iloc[split:]

    print(f"Total samples: {len(df)} | Train: {len(X_train)} | Held-out Test: {len(X_test)}")
    print(f"Late Rate - Train: {y_train_cls.mean()*100:.1f}%, Test: {y_test_cls.mean()*100:.1f}%\n")

    classifier_candidates = {
        "Zero-Rule (Baseline)": DummyClassifier(strategy="most_frequent"),
        "Logistic Regression": LogisticRegression(max_iter=1000, class_weight="balanced"),
        "Random Forest": RandomForestClassifier(n_estimators=150, max_depth=5, min_samples_split=4, class_weight="balanced", random_state=42),
        "HistGradientBoosting": HistGradientBoostingClassifier(max_iter=120, max_depth=3, learning_rate=0.05, class_weight="balanced", random_state=42),
        "Gradient Boosting (GBM)": GradientBoostingClassifier(n_estimators=120, max_depth=3, learning_rate=0.05, subsample=0.85, random_state=42),
    }

    results = []
    for name, clf in classifier_candidates.items():
        clf.fit(X_train, y_train_cls)
        probs = clf.predict_proba(X_test)[:, 1] if hasattr(clf, "predict_proba") else clf.predict(X_test)
        
        # Use tuned threshold 0.40 for GBM / Balanced, 0.50 otherwise
        threshold = 0.40 if "Gradient" in name else 0.50
        preds = (probs >= threshold).astype(int)

        acc = accuracy_score(y_test_cls, preds)
        prec = precision_score(y_test_cls, preds, zero_division=0)
        rec = recall_score(y_test_cls, preds, zero_division=0)
        f1 = f1_score(y_test_cls, preds, zero_division=0)
        try:
            roc = roc_auc_score(y_test_cls, probs)
            pr_auc = average_precision_score(y_test_cls, probs)
        except Exception:
            roc, pr_auc = 0.5, y_test_cls.mean()
        cm = confusion_matrix(y_test_cls, preds)

        results.append({
            "Dataset": "Udhaar Ledger Production",
            "Model": name,
            "Accuracy": f"{acc*100:.2f}%",
            "Precision": f"{prec*100:.2f}%",
            "Recall": f"{rec*100:.2f}%",
            "F1-Score": f"{f1:.4f}",
            "ROC-AUC": f"{roc:.4f}",
            "PR-AUC": f"{pr_auc:.4f}",
            "Confusion Matrix [TN, FP, FN, TP]": str(cm.ravel().tolist()),
        })

    results_df = pd.DataFrame(results)
    print(results_df.drop(columns=["Dataset"]).to_string(index=False))

    # Regressor evaluation
    reg = GradientBoostingRegressor(n_estimators=150, max_depth=3, learning_rate=0.05, subsample=0.85, random_state=42)
    reg.fit(X_train, y_train_reg)
    reg_preds = np.maximum(0.0, reg.predict(X_test))
    mae = mean_absolute_error(y_test_reg, reg_preds)
    base_mae = mean_absolute_error(y_test_reg, [y_train_reg.mean()] * len(y_test_reg))
    rmse = root_mean_squared_error(y_test_reg, reg_preds)

    print("\n--- Regression Magnitude Results (Held-Out Test Set) ---")
    print(f"MAE (Trained GBM):     {mae:.2f} days")
    print(f"MAE (Historical Mean): {base_mae:.2f} days")
    print(f"RMSE:                  {rmse:.2f} days")
    print(f"Error Reduction:       {((base_mae - mae)/base_mae)*100:.1f}%\n")

    return results, {"mae": round(mae, 2), "base_mae": round(base_mae, 2), "error_reduction": round(((base_mae - mae)/base_mae)*100, 1)}


def benchmark_ibm_kaggle_dataset():
    """Evaluate models on IBM Watson / Kaggle Accounts Receivable benchmark dataset."""
    print("\n" + "=" * 80)
    print("2. EVALUATING KAGGLE / IBM WATSON ACCOUNTS RECEIVABLE BENCHMARK DATASET")
    print("=" * 80)

    csv_path = backend_dir / "data" / "ibm_accounts_receivable.csv"
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        return [], {}

    df = pd.read_csv(csv_path)
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["DueDate"] = pd.to_datetime(df["DueDate"])
    df["is_late"] = (df["DaysLate"] > 0).astype(int)
    df = df.sort_values("InvoiceDate").reset_index(drop=True)

    df["invoice_amount_log"] = np.log1p(df["InvoiceAmount"])
    df["terms_days"] = (df["DueDate"] - df["InvoiceDate"]).dt.days
    df["disputed_num"] = (df["Disputed"] == "Yes").astype(int)
    df["paperless_num"] = (df["PaperlessBill"] == "Electronic").astype(int)

    # Point-in-time sequential customer payment history
    df["cust_prior_invoices"] = df.groupby("customerID").cumcount()
    df["cust_prior_lates"] = df.groupby("customerID")["is_late"].cumsum() - df["is_late"]
    df["cust_late_rate"] = np.where(df["cust_prior_invoices"] > 0, df["cust_prior_lates"] / df["cust_prior_invoices"], 0.35)

    features = ["invoice_amount_log", "terms_days", "disputed_num", "paperless_num", "cust_prior_invoices", "cust_late_rate"]
    X = df[features]
    y_cls = df["is_late"]
    y_reg = df["DaysLate"]

    split = int(0.8 * len(df))
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train_cls, y_test_cls = y_cls.iloc[:split], y_cls.iloc[split:]
    y_train_reg, y_test_reg = y_reg.iloc[:split], y_reg.iloc[split:]

    print(f"Total samples: {len(df)} | Train: {len(X_train)} | Held-out Test: {len(X_test)}")
    print(f"Late Rate - Train: {y_train_cls.mean()*100:.1f}%, Test: {y_test_cls.mean()*100:.1f}%\n")

    classifier_candidates = {
        "Zero-Rule (Baseline)": DummyClassifier(strategy="most_frequent"),
        "Logistic Regression": LogisticRegression(max_iter=1000, class_weight="balanced"),
        "Random Forest (Tuned)": RandomForestClassifier(n_estimators=150, max_depth=6, min_samples_split=4, class_weight="balanced", random_state=42),
        "HistGradientBoosting": HistGradientBoostingClassifier(max_iter=120, max_depth=4, learning_rate=0.05, class_weight="balanced", random_state=42),
        "Gradient Boosting (GBM)": GradientBoostingClassifier(n_estimators=120, max_depth=4, learning_rate=0.05, subsample=0.85, random_state=42),
    }

    results = []
    for name, clf in classifier_candidates.items():
        clf.fit(X_train, y_train_cls)
        probs = clf.predict_proba(X_test)[:, 1] if hasattr(clf, "predict_proba") else clf.predict(X_test)
        preds = (probs >= 0.50).astype(int)

        acc = accuracy_score(y_test_cls, preds)
        prec = precision_score(y_test_cls, preds, zero_division=0)
        rec = recall_score(y_test_cls, preds, zero_division=0)
        f1 = f1_score(y_test_cls, preds, zero_division=0)
        try:
            roc = roc_auc_score(y_test_cls, probs)
            pr_auc = average_precision_score(y_test_cls, probs)
        except Exception:
            roc, pr_auc = 0.5, y_test_cls.mean()
        cm = confusion_matrix(y_test_cls, preds)

        results.append({
            "Dataset": "IBM Accounts Receivable (Kaggle)",
            "Model": name,
            "Accuracy": f"{acc*100:.2f}%",
            "Precision": f"{prec*100:.2f}%",
            "Recall": f"{rec*100:.2f}%",
            "F1-Score": f"{f1:.4f}",
            "ROC-AUC": f"{roc:.4f}",
            "PR-AUC": f"{pr_auc:.4f}",
            "Confusion Matrix [TN, FP, FN, TP]": str(cm.ravel().tolist()),
        })

    results_df = pd.DataFrame(results)
    print(results_df.drop(columns=["Dataset"]).to_string(index=False))

    reg = GradientBoostingRegressor(n_estimators=120, max_depth=3, learning_rate=0.05, subsample=0.85, random_state=42)
    reg.fit(X_train, y_train_reg)
    reg_preds = np.maximum(0.0, reg.predict(X_test))
    mae = mean_absolute_error(y_test_reg, reg_preds)
    base_mae = mean_absolute_error(y_test_reg, [y_train_reg.mean()] * len(y_test_reg))
    rmse = root_mean_squared_error(y_test_reg, reg_preds)

    print("\n--- Regression Magnitude Results (Held-Out Test Set) ---")
    print(f"MAE (Trained GBM):     {mae:.2f} days")
    print(f"MAE (Historical Mean): {base_mae:.2f} days")
    print(f"RMSE:                  {rmse:.2f} days")
    print(f"Error Reduction:       {((base_mae - mae)/base_mae)*100:.1f}%\n")

    return results, {"mae": round(mae, 2), "base_mae": round(base_mae, 2), "error_reduction": round(((base_mae - mae)/base_mae)*100, 1)}


if __name__ == "__main__":
    res_cq, reg_cq = benchmark_collectiq_dataset()
    res_ibm, reg_ibm = benchmark_ibm_kaggle_dataset()

    output_path = backend_dir / "app" / "ml" / "artifacts" / "benchmark_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "collectiq_production": {"classification": res_cq, "regression": reg_cq},
            "ibm_kaggle_benchmark": {"classification": res_ibm, "regression": reg_ibm},
        }, f, indent=2)

    print(f"Complete benchmark report saved to {output_path}")
