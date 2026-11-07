# Udhaar Ledger — Financial Systems QA & Mathematical Validation Report

**Auditor:** Senior Financial Systems QA Engineer  
**Scope:** Receivables Ledger, Allocation Mechanics, Aging Buckets, KPI Aggregations  
**Validation Date:** November 5, 2026  
**Status:** Validated & Formally Reconciled  

---

## 1. Core Financial Principles & Guarantees

In financial accounting systems, rounding discrepancies, duplicate row multiplier bugs from SQL joins, and floating-point errors create unacceptable reporting liabilities. Udhaar Ledger was audited against four non-negotiable financial guarantees:

1. **Deterministic Ledger Balance:** An invoice's outstanding balance must always equal its original invoice gross amount minus the exact sum of all verified payment allocations applied to that invoice.
2. **Join Immunity:** Calculating an invoice balance or outstanding portfolio total must never be influenced by relational row multiplicity from customer, item, or payment join trees.
3. **Over-Allocation Prevention:** The system must reject any payment allocation that exceeds either the unallocated remainder of the payment or the remaining unpaid balance of the invoice.
4. **Idempotent Data Mutation:** Ingestion of duplicate transaction files or re-transmission of payment records must never create phantom credits, doubled payments, or corrupted aging classifications.

---

## 2. Hand-Calculated Test Fixtures & Invariant Verification

### Fixture 1: Full Payment Liquidation
- **Invoice:** Gross Amount = ₹50,000.00
- **Payment 1:** NEFT ₹50,000.00 allocated on 2024-01-20
- **Expected Outcome:** Outstanding = ₹0.00; Status = `paid`
- **Result:** **PASSED** (Verified in `test_full_payment_zeros_balance` and `test_full_payment_via_api_marks_invoice_paid`).

### Fixture 2: Partial Payment Reduction
- **Invoice:** Gross Amount = ₹1,00,000.00
- **Payment 1:** RTGS ₹35,000.00 allocated on 2024-01-15
- **Expected Outcome:** Outstanding = ₹65,000.00; Status = `partial`
- **Result:** **PASSED** (Verified in `test_partial_payment_reduces_balance`).

### Fixture 3: Multiple Fragmented Partial Payments
- **Invoice:** Gross Amount = ₹75,000.00
- **Payments Applied:**
  - Payment A: ₹20,000.00 (UPI)
  - Payment B: ₹15,000.00 (UPI)
  - Payment C: ₹10,000.00 (UPI)
  - Total Allocated: ₹45,000.00
- **Expected Outcome:** Outstanding = ₹30,000.00 (Exact subtraction `75,000.00 - 45,000.00`); Status = `partial`
- **Result:** **PASSED** (Verified in `test_multiple_partial_payments`).

### Fixture 4: Over-Allocation Defense
- **Invoice:** Gross Amount = ₹10,000.00; Outstanding = ₹10,000.00
- **Attempted Allocation:** ₹15,000.00 (₹5,000.00 in excess of balance)
- **Expected Outcome:** HTTP 422 Unprocessable Content; Database transaction rollbacked.
- **Result:** **PASSED** (Verified in `test_overpayment_raises_422_via_api`).

### Fixture 5: Isolation from Relational JOIN Multipliers
- **Scenario:** Customer has 3 separate invoices (₹50k, ₹50k, ₹50k). Invoice 1 receives 2 payments of ₹10k each. Invoices 2 and 3 receive ₹0.
- **Naïve SQL Trap:** Joining `invoices` with `payments` produces 2 rows for Invoice 1 and multiplies row sums if not grouped per invoice.
- **Verified Result:**
  - Invoice 1 Outstanding: ₹30,000.00
  - Invoice 2 Outstanding: ₹50,000.00
  - Invoice 3 Outstanding: ₹50,000.00
  - Cross-row balance distortion: **0.00%** (Verified in `test_outstanding_balance_not_affected_by_joins`).

---

## 3. Mathematical Reconciliation Across Aggregations

A live database audit was executed across the 800 synthetic invoices of Sharma Distributors Pvt Ltd to verify that ledger balances reconcile regardless of the querying abstraction layer.

### Ledger Total Audit Results

```python
1. Sum of individual invoice subqueries:   ₹11,48,80,850.00
2. invoice_service total query:            ₹11,48,80,850.00
3. dashboard_service total_outstanding:    ₹11,48,80,850.00
4. Sum of all aging bucket amounts:        ₹11,48,80,850.00
------------------------------------------------------------
RECONCILIATION DISCREPANCY:                ₹0.00 (EXACT MATCH)
```

### Overdue Balance Reconciliation
- **Itemized sum of invoices where `due_date < CURRENT_DATE`:** ₹10,66,23,850.00
- **Dashboard aggregate `total_overdue` KPI:** ₹10,66,23,850.00
- **Discrepancy:** **₹0.00 (EXACT MATCH)**

---

## 4. Aging Bucket Classification Logic

Udhaar Ledger groups receivables into 5 standard aging intervals based on days elapsed past the invoice due date:

$$\text{Days Overdue} = \max(0, \text{CURRENT\_DATE} - \text{due\_date})$$

| Bucket Key | UI Display Label | Overdue Days Range | Active Invoices | Total Outstanding (₹) | % of Portfolio |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `current` | Not Yet Due | $\le 0$ days | 19 | ₹82,57,000.00 | 7.2% |
| `1-30` | 1–30 Days Overdue | $1 \text{ to } 30$ days | 22 | ₹89,45,000.00 | 7.8% |
| `31-60` | 31–60 Days Overdue | $31 \text{ to } 60$ days | 25 | ₹1,02,10,000.00 | 8.9% |
| `61-90` | 61–90 Days Overdue | $61 \text{ to } 90$ days | 28 | ₹1,14,35,000.00 | 10.0% |
| `91+` | 91+ Days Overdue | $> 90$ days | 190 | ₹7,60,33,850.00 | 66.1% |
| **Total** | — | — | **284** | **₹11,48,80,850.00** | **100.0%** |

### Audit Finding on Aging Column Labels in `analytics_service.py`
During inspection of `backend/app/services/analytics_service.py`, a naming shift bug was identified where SQL alias `days_31_60` was applied to records with `BETWEEN 1 AND 30` days overdue. This resulted in an off-by-one bucket error in customer-level aging breakdowns.
- **Fix:** Corrected SQL case intervals and mapped Pydantic field names to align with standard 1–30, 31–60, 61–90, and >90 day intervals.

---

## 5. Collection Rate Metric Definition & Ambiguity Analysis

In `backend/app/services/dashboard_service.py`:
```python
total_invoiced = db.execute(
    text("SELECT COALESCE(SUM(total_amount), 0) FROM invoices WHERE org_id = :org_id AND deleted_at IS NULL AND status != 'cancelled'")
).scalar()

total_collected = db.execute(
    text("SELECT COALESCE(SUM(pa.allocated_amount), 0) FROM payment_allocations pa JOIN payments p ON p.id = pa.payment_id WHERE p.org_id = :org_id")
).scalar()

collection_rate = float(total_collected / total_invoiced * 100)
```

### Critical Clarity Observation:
- **Numerator:** Total payment allocations ever recorded across all time.
- **Denominator:** Total gross value of all non-cancelled invoices ever issued.
- **Business Interpretation:** This represents **Cumulative Lifetime Collection Efficiency (76.9%)**.
- **Limitation:** It is not a "Monthly Collection Rate" (i.e., cash collected in month $M$ divided by billing in month $M$). For monthly operational cash efficiency, the platform provides the separate `get_collection_trend()` endpoint, which computes month-by-month billing vs. cash collected.

---

## 6. Financial QA Verdict

The financial core of Udhaar Ledger conforms to deterministic accounting standards:
- Outstanding balances are strictly derived from subqueries against `payment_allocations`.
- No floating-point rounding errors (all amounts stored and calculated using `Numeric(15, 2)` / Python `Decimal`).
- Zero mathematical discrepancy exists between ledger totals, service functions, and dashboard KPI cards.
