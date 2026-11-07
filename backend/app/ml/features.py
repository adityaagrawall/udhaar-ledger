"""Feature engineering for payment delay prediction."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID
import math

from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.payment import Payment, PaymentAllocation

FEATURE_COLS = [
    "issue_to_due_days",
    "total_amount",
    "log_amount",
    "credit_limit",
    "credit_utilization",
    "customer_risk_tier_encoded",
    "payment_terms_days",
    "late_payment_rate",
    "avg_days_late",
    "total_historical_invoices",
]


def extract_features(
    invoice_id: UUID, org_id: UUID, db: Session, as_of: date | None = None
) -> dict[str, Any]:
    """
    Extract a feature vector for a single invoice, using only information known at `as_of`.

    History counts an earlier invoice only if it was FULLY settled on or before `as_of`
    (its last payment date <= as_of). Training must pass as_of=invoice.issue_date so a
    sample never sees payments made after it was issued. Live inference leaves as_of=None
    (today), which is legitimate because everything up to today is already known.
    """
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or invoice.org_id != org_id:
        raise ValueError(f"Invoice {invoice_id} not found")
    as_of = as_of or date.today()
    customer = db.get(Customer, invoice.customer_id)
    if customer is None:
        raise ValueError(f"Customer {invoice.customer_id} not found")

    issue_to_due = max(1, (invoice.due_date - invoice.issue_date).days)
    total_amt = float(invoice.total_amount)
    log_amt = float(math.log1p(max(0.0, total_amt)))
    credit_lim = float(customer.credit_limit) if customer.credit_limit else 100000.0
    credit_util = min(5.0, total_amt / credit_lim) if credit_lim > 0 else 0.5

    risk_tier_map = {"low": 0, "medium": 1, "high": 2}
    customer_risk_encoded = risk_tier_map.get(customer.risk_tier, 1)

    # Point-in-time history: earlier invoices of this customer fully settled by `as_of`.
    hist_stats = db.execute(
        text("""
            SELECT
                COUNT(*) AS total_prior,
                COUNT(CASE WHEN h.paid_date > h.due_date THEN 1 END) AS late_prior,
                COALESCE(AVG(CASE WHEN h.paid_date > h.due_date THEN (h.paid_date - h.due_date) END), 0.0) AS avg_days_late
            FROM (
                SELECT i.id, i.due_date, MAX(p.received_date) AS paid_date
                FROM invoices i
                JOIN payment_allocations pa ON pa.invoice_id = i.id
                JOIN payments p ON p.id = pa.payment_id
                WHERE i.customer_id = :cid
                  AND i.org_id = :org_id
                  AND i.status = 'paid'
                  AND i.deleted_at IS NULL
                  AND i.id != :inv_id
                GROUP BY i.id, i.due_date
                HAVING MAX(p.received_date) <= :as_of
            ) h
        """),
        {"cid": str(customer.id), "org_id": str(org_id), "inv_id": str(invoice_id), "as_of": as_of},
    ).fetchone()

    total_historical = int(hist_stats.total_prior) if hist_stats and hist_stats.total_prior else 0
    late_prior = int(hist_stats.late_prior) if hist_stats and hist_stats.late_prior else 0
    avg_days_late = float(hist_stats.avg_days_late) if hist_stats and hist_stats.avg_days_late else 0.0

    # If the customer has prior history, compute empirical rate; otherwise use risk-tier prior
    if total_historical > 0:
        late_payment_rate = min(1.0, max(0.0, late_prior / total_historical))
    else:
        # Default prior by customer risk tier
        priors = {0: 0.15, 1: 0.35, 2: 0.70}
        late_payment_rate = priors.get(customer_risk_encoded, 0.35)
        avg_days_late = {0: 0.0, 1: 3.0, 2: 12.0}.get(customer_risk_encoded, 3.0)

    # Current outstanding on this invoice
    outstanding_row = db.execute(
        text("""
            SELECT i.total_amount - COALESCE(SUM(pa.allocated_amount), 0) AS outstanding
            FROM invoices i
            LEFT JOIN payment_allocations pa ON pa.invoice_id = i.id
            WHERE i.id = :inv_id
            GROUP BY i.id, i.total_amount
        """),
        {"inv_id": str(invoice_id)},
    ).fetchone()
    outstanding = float(outstanding_row.outstanding) if outstanding_row else total_amt

    return {
        "invoice_id": str(invoice_id),
        "issue_to_due_days": issue_to_due,
        "total_amount": total_amt,
        "log_amount": log_amt,
        "outstanding": outstanding,
        "outstanding_ratio": outstanding / total_amt if total_amt > 0 else 0.0,
        "customer_risk_tier_encoded": customer_risk_encoded,
        "payment_terms_days": customer.payment_terms_days or 30,
        "late_payment_rate": late_payment_rate,
        "avg_days_late": avg_days_late,
        "total_historical_invoices": total_historical,
        "credit_limit": credit_lim,
        "credit_utilization": credit_util,
    }


def build_feature_matrix(org_id: UUID, db: Session) -> list[dict[str, Any]]:
    """Extract features for all non-paid invoices in an org (used for batch inference)."""
    invoices = db.execute(
        select(Invoice).where(
            Invoice.org_id == org_id,
            Invoice.deleted_at == None,
            Invoice.status.not_in(["draft", "cancelled"]),
        )
    ).scalars().all()
    return [extract_features(inv.id, org_id, db) for inv in invoices]
