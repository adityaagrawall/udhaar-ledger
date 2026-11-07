# Udhaar Ledger — Known Limitations & Operational Constraints

**Document Purpose:** Transparently record architectural boundaries, known trade-offs, and operational limitations identified during the technical and financial audit.  
**Auditor Principle:** *Do not claim the application is production-ready merely because services start or tests pass.*  

---

## 1. Machine Learning & Predictive Limitations

### Temporal Feature Leakage — RESOLVED (Nov 2026)
- `extract_features(..., as_of=...)` counts an earlier invoice only if its last payment date is on or before `as_of`. Training and benchmarking pass `as_of=invoice.issue_date`; live inference uses today. Covered by `tests/test_ml_and_import_fixes.py`.
- Remaining caveat: customer-level history still overlaps between train and test splits (the same customers appear in both). Generalisation to brand-new customers is not measured; use a grouped split for that.
- Models are now stored per organisation (`artifacts/<org_id>/`). The older shared `delay_model.pkl` / `delay_classifier.pkl` are no longer read, so retrain once per tenant.

### Continuous Regression vs. Zero-Delay Bimodal Distribution
- **Current Behavior:** The delay model is a single `GradientBoostingRegressor` predicting continuous delay days.
- **Limitation:** Over 45% of commercial invoices are paid on or before the due date (delay = 0). A continuous regressor cannot easily model both the binary probability of on-time payment and the heavy-tailed magnitude of long-term delinquency simultaneously.
- **Recommended Architecture:** A two-stage hurdle model (Binary classifier for delay probability + Log-normal regressor for delay duration).

---

## 2. Ingestion & File Processing Limitations

### In-Memory Preview Cache (`_preview_cache`)
- **Current Behavior:** The file preview stage caches parsed records in a Python process memory dictionary (`_preview_cache: dict[str, dict] = {}` in `import_service.py`).
- **Mitigation:** previews expire after 15 minutes so the cache cannot grow without bound.
- **Limitation:**
  - If the backend process restarts between the `/import/preview` and `/import/commit` calls, the preview token is lost and the user receives a 400 error.
  - In a multi-worker or horizontally scaled deployment (e.g. Uvicorn with `--workers 4` or multiple Kubernetes pods), the commit request may route to a worker that does not hold the preview in memory.
- **Remediation Needed:** Store serialized preview payloads in an external Redis cache with a 15-minute TTL.

### Lack of Asynchronous Background Ingestion
- **Current Behavior:** Parsing and committing CSV/XLSX files happens synchronously within the HTTP request thread.
- **Limitation:** For datasets exceeding 5,000 rows, request execution time may exceed standard reverse-proxy timeouts (e.g. Nginx 60s timeout), causing HTTP 504 errors while the database transaction continues executing.
- **Remediation Needed:** Offload file processing to a Celery or ARQ background task queue with WebSocket status updates.

---

## 3. Financial Ledger & Accounting Limitations

### Credit Notes and Debit Adjustments Unsupported
- **Current Behavior:** Ledger entries consist strictly of `invoices`, `payments`, and `payment_allocations`.
- **Limitation:** Commercial wholesale operations frequently issue credit notes (for damaged goods, trade discounts, return of expired stock, or billing disputes) and debit notes (for interest or freight adjustments). In Udhaar Ledger V1, a disputed invoice cannot be credited; it can only be marked as `cancelled` or settled via payment allocations.

### Multi-Currency & FX Exchange Limitations
- **Current Behavior:** All financial calculations assume Indian Rupees (`₹` / INR). Database columns are defined as `Numeric(15, 2)` without an associated currency code.
- **Limitation:** International or cross-border trade requiring USD/EUR invoices or fluctuating foreign exchange gain/loss calculations is unsupported.

### Single-Invoice Allocation Granularity
- **Current Behavior:** In the frontend UI, payments are recorded and allocated invoice-by-invoice.
- **Limitation:** Bulk unallocated payments (e.g. a lump-sum payment of ₹10,00,000 intended to be auto-allocated FIFO across the oldest outstanding invoices of a customer) must be calculated on the client side or explicitly broken down into individual allocation line items by the operator.

---

## 4. Frontend & Session State Limitations

### Bearer Token Storage in `localStorage`
- **Current Behavior:** Authentication JWT tokens are persisted in browser `localStorage`.
- **Limitation:** Tokens stored in `localStorage` are accessible to JavaScript executing in the same origin, making them vulnerable to Cross-Site Scripting (XSS) extraction if a third-party dependency is compromised.
- **Production Standard:** Migrate session management to `HttpOnly`, `Secure`, `SameSite=Lax` browser cookies.

### Absence of Granular Permission Scopes in UI
- **Current Behavior:** While backend API routes enforce `admin`, `manager`, and `viewer` roles via `require_roles`, the frontend does not dynamically hide or disable action buttons (e.g. "Record Payment" or "Delete Customer") based on the logged-in user's role. A `viewer` user will see buttons that subsequently trigger HTTP 403 errors when clicked.

---

## 5. Synthetic vs. Production Data Disclaimer

### Synthetic Data Distribution
- **Dataset:** 150 customers, 800 invoices, 677 payments generated using `Faker(locale='en_IN')` with random seed 42.
- **Limitation:** While the synthetic dataset accurately models Indian payment term intervals (15, 30, 45, 60 days) and GST customer identifiers, it does not reflect macroeconomic shocks (e.g. demonetization, GST policy changes, or seasonal Diwali inventory build-ups) that dictate real-world distributor receivables cycles.
- **Principle:** Historical predictive accuracy on this dataset must be re-calibrated before relying on delay predictions for underwriting commercial credit decisions.
