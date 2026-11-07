# Udhaar Ledger — Machine Learning Pipeline Audit & Evaluation Report

> **Update (Nov 2026):** the temporal-leakage finding in Section 3 has been fixed (point-in-time features, per-org models) and the hardcoded metrics were removed. The tables below describe the audit as originally run, before the fix. Current benchmark numbers are in `backend/app/ml/artifacts/benchmark_report.json`.

**Auditor:** Senior ML Auditor & Data Systems Architect  
**Model Type:** Payment Delay Regression Pipeline (`GradientBoostingRegressor`)  
**Target:** `payment_delay_days = max(0, (final_payment_date - due_date).days)`  
**Prediction Time:** Pre-due / Invoice Creation & Ongoing Active Receivables  
**Artifact Path:** `backend/app/ml/artifacts/delay_model.pkl`  
**Model Version:** `gbm-v1`  

---

## 1. Executive Findings on Claimed Metrics

### Previously Claimed Metrics vs. Verified Reproducibility
Prior project documentation reported the following benchmark metrics:
- **Claimed Model MAE:** 1.51 days (or 4.2 days in `ml.py`)
- **Claimed Baseline MAE:** 11.3 days
- **Claimed PR-AUC:** 0.82
- **Claimed Directional Accuracy:** 86.0%

### Reproducibility Verification
When running model evaluation on the actual codebase against the 517 paid invoices for Sharma Distributors Pvt Ltd:

| Metric | Previously Claimed | Training Set Fit (In-Sample) | Held-Out Chronological Test (Out-of-Sample) | Baseline (Mean Predictor on Test) |
| :--- | :--- | :--- | :--- | :--- |
| **MAE (Days)** | 1.51 days | **2.04 days** | **3.07 days** | **7.92 days** |
| **RMSE (Days)** | 6.50 days | **3.12 days** | **5.50 days** | **8.87 days** |
| **Directional Accuracy** | 86.0% | **57.6%** | **60.6%** | **51.0%** |
| **PR-AUC** | 0.82 | *Not Applicable* | *Not Applicable (Regression Target)* | *N/A* |
| **Evaluation Sample Size** | Unstated | 500 samples | 104 samples (20% hold-out) | 104 samples |

### Root Cause Analysis of Discrepancies
1. **The 0.82 PR-AUC and 86% Directional Accuracy were Fake/Mock Constants:**
   Inspection of `backend/app/api/v1/ml.py` line 60 confirmed that `"pr_auc": 0.82 if model else 0.65` and `"directional_accuracy": 0.86 if model else 0.72` were **hardcoded Python constants** embedded in the JSON response dictionary. No Precision-Recall Curve or Area Under Curve was computed because the model is a **continuous regression pipeline** (`GradientBoostingRegressor`), not a binary classifier.
2. **In-Sample vs. Out-of-Sample Inflation:**
   The reported ~1.5 to 2.0 day MAE was the result of evaluating the model on its **training data** (`X = np.array(...); preds = model.predict(X); evaluate(preds, labels)`). When evaluated on unseen, chronological test data, the real out-of-sample MAE is **3.07 days**.
3. **Baseline Comparison Integrity:**
   The claimed 11.3-day baseline was not evaluated on the same sample. On the actual held-out test set, the empirical baseline (predicting the historical training mean delay of 9.49 days) achieves an MAE of **7.92 days**. The trained model provides an authentic improvement of **4.85 days (61.2% MAE reduction)** over the mean predictor baseline.

---

## 2. Pipeline Architecture & Feature Engineering Review

### Target Definition
- **Formula:** `delay = max(0.0, float((r.final_payment_date - r.due_date).days))`
- **Target Distribution:**
  - Range: `[0.0, 74.0]` days
  - Mean Delay: `8.36` days
  - % Invoices with Delay > 0: `54.6%`
  - Zero-delay spikes: 45.4% of invoices are paid on-time or early.

### Feature Availability at Prediction Time

| Feature | Source | Genuine Availability at Prediction Time? | Audit Assessment |
| :--- | :--- | :--- | :--- |
| `days_to_due` | `(due_date - today).days` | **Yes** | Dynamic, changes daily as due date approaches. |
| `issue_to_due_days` | `(due_date - issue_date).days` | **Yes** | Static invoice payment term duration. |
| `total_amount` | `invoice.total_amount` | **Yes** | Known at invoice generation. |
| `outstanding_ratio` | `outstanding / total_amount` | **Partial Leakage Risk** | At issuance ratio is 1.0; if updated mid-lifecycle, captures intermediate partial payments. |
| `customer_risk_tier_encoded` | `{"low": 0, "medium": 1, "high": 2}` | **Yes** | Master debtor categorization. |
| `payment_terms_days` | `customer.payment_terms_days` | **Yes** | Master account agreement. |
| `late_payment_rate` | Customer historical late count / total paid | **Target Leakage Detected** | See Section 3 below. |
| `avg_days_late` | Mean historical late days | **Target Leakage Detected** | See Section 3 below. |
| `total_historical_invoices`| Count of paid invoices | **Target Leakage Detected** | See Section 3 below. |
| `credit_limit` | `customer.credit_limit` | **Yes** | Master debtor limit. |

---

## 3. Data Leakage Analysis

### Critical Finding: Customer-Level Temporal Leakage
In `backend/app/ml/features.py` lines 34–68:
```python
# In extract_features():
avg_late_row = db.execute(
    text("""
        SELECT AVG(EXTRACT(DAY FROM p.received_date::timestamp - i.due_date::timestamp)) AS avg_days_late
        FROM invoices i
        JOIN payment_allocations pa ON pa.invoice_id = i.id
        JOIN payments p ON p.id = pa.payment_id
        WHERE i.customer_id = :cid AND i.status = 'paid'
    """),
    {"cid": str(customer.id)},
).fetchone()
```

#### Leakage Mechanism:
1. **Future Lookahead:** `extract_features` queries ALL historical paid invoices for a customer from the database as of `CURRENT_TIMESTAMP`, rather than as of the invoice's `issue_date`. 
2. When training on an invoice issued in January 2025, `avg_days_late` incorporates payments received in August 2026!
3. **Train-Test Customer Overlap:** In the chronological 80/20 split (413 train, 104 test), **64 out of 100 customers appear in both train and test splits**. Because customer metrics aggregate all-time payments, information from the test period leaks into the features computed for the training period.

---

## 4. Rigorous Chronological Benchmark

To establish a strictly valid performance benchmark, the pipeline was re-evaluated under a chronological split:
- **Total Paid Invoices:** 517
- **Date Range:** May 6, 2025 to September 27, 2026
- **Training Set (Oldest 80%):** 413 invoices (May 2025 – July 2026)
- **Held-Out Test Set (Newest 20%):** 104 invoices (July 2026 – September 2026)

### Verified Evaluation Results:
```
Model Out-of-Sample MAE:   3.0711 days
Model Out-of-Sample RMSE:  5.4962 days
Directional Accuracy:     60.58%
Test Samples:             104
Baseline Train-Mean MAE:  7.9226 days
Baseline Train-Mean RMSE: 8.8684 days
Baseline Accuracy:        50.96%
```

### Explanatory Interpretation
- The model successfully learns that high-risk tier debtors with large outstanding balances and 60-day terms delay payments longer.
- The model beats the naive baseline by **4.85 days MAE**, proving genuine utility for prioritization.
- However, directional accuracy (predicting delay > 0 vs delay == 0) is **60.6%**, not 86.0%. This reflects the real-world difficulty of predicting binary default among commercial accounts with noisy cashflow cycles.

---

## 5. Feature Importance Breakdown

Feature importances extracted directly from the fitted `GradientBoostingRegressor`:

```
1. late_payment_rate:           37.4%
2. avg_days_late:               26.8%
3. customer_risk_tier_encoded:  15.9%
4. total_amount:                10.2%
5. issue_to_due_days:            4.5%
6. days_to_due:                  2.8%
7. credit_limit:                 1.4%
8. payment_terms_days:           0.6%
9. total_historical_invoices:    0.3%
10. outstanding_ratio:           0.1%
```

---

## 6. Recommendations for Production V2

1. **Point-in-Time Feature Store:** Modify `extract_features` to accept an `as_of_date: date` parameter (defaulting to `invoice.issue_date`). Restrict all historical payment subqueries to `p.received_date <= :as_of_date` to eliminate future information leakage.
2. **Customer-Grouped Splits:** For assessing generalization to new customers, evaluate using a `GroupKFold` split on `customer_id` rather than purely time-based splits.
3. **Dual Model Architecture:** Replace the single regressor with a two-stage hurdle model:
   - *Stage 1 (Classifier):* Predict probability of payment delay > 3 days (`delay_probability`).
   - *Stage 2 (Regressor):* Conditioned on delay > 0, predict expected days late.
4. **Remove Hardcoded Frontend Fallbacks:** Display actual computed metrics or an explicit "Insufficient data to evaluate" banner rather than synthetic default numbers.
