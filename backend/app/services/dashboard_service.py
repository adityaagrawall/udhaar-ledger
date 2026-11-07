"""
Dashboard service: aggregates KPIs from database without hardcoding.

All figures are calculated from actual invoice/payment records.
Formulas are documented inline.
"""

import math
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceStatus
from app.models.follow_up import FollowUp, FollowUpStatus
from app.schemas.dashboard import AgingBucket, AgingReport, CollectionTrendPoint, DashboardSummary


def _get_aging_data(db: Session, org_id: UUID, as_of: date) -> list[dict]:
    """
    Aging buckets using correlated subquery for outstanding balance.
    Buckets: Current (≥0 days), 1-30, 31-60, 61-90, 90+ days overdue.
    """
    result = db.execute(
        text("""
            WITH invoice_outstanding AS (
                SELECT
                    i.id,
                    i.due_date,
                    i.total_amount - COALESCE(
                        (SELECT SUM(pa.allocated_amount)
                         FROM payment_allocations pa
                         WHERE pa.invoice_id = i.id),
                        0
                    ) AS outstanding
                FROM invoices i
                WHERE i.org_id = :org_id
                  AND i.deleted_at IS NULL
                  AND i.status NOT IN ('paid', 'cancelled')
            )
            SELECT
                CASE
                    WHEN :today - due_date <= 0 THEN 'current'
                    WHEN :today - due_date BETWEEN 1 AND 30 THEN '1-30'
                    WHEN :today - due_date BETWEEN 31 AND 60 THEN '31-60'
                    WHEN :today - due_date BETWEEN 61 AND 90 THEN '61-90'
                    ELSE '91+'
                END AS bucket,
                COUNT(*) AS invoice_count,
                COALESCE(SUM(outstanding), 0) AS total_outstanding
            FROM invoice_outstanding
            WHERE outstanding > 0
            GROUP BY bucket
            ORDER BY bucket
        """),
        {"org_id": str(org_id), "today": as_of},
    ).fetchall()
    return [{"bucket": r[0], "invoice_count": r[1], "total_outstanding": Decimal(str(r[2]))} for r in result]


BUCKET_ORDER = ["current", "1-30", "31-60", "61-90", "91+"]
BUCKET_META = {
    "current": ("Not Yet Due", 0, 0),
    "1-30": ("1–30 Days", 1, 30),
    "31-60": ("31–60 Days", 31, 60),
    "61-90": ("61–90 Days", 61, 90),
    "91+": ("91+ Days", 91, None),
}


def get_dashboard_summary(db: Session, org_id: UUID) -> DashboardSummary:
    today = date.today()
    this_month_start = today.replace(day=1)
    next_week = today + timedelta(days=7)

    # Total outstanding (non-paid, non-cancelled)
    total_outstanding_row = db.execute(
        text("""
            SELECT COALESCE(
                SUM(i.total_amount) - COALESCE(
                    (SELECT SUM(pa2.allocated_amount)
                     FROM payment_allocations pa2
                     JOIN invoices i2 ON i2.id = pa2.invoice_id
                     WHERE i2.org_id = :org_id
                       AND i2.deleted_at IS NULL
                       AND i2.status NOT IN ('paid','cancelled')),
                    0
                ),
                0
            )
            FROM invoices i
            WHERE i.org_id = :org_id
              AND i.deleted_at IS NULL
              AND i.status NOT IN ('paid','cancelled')
        """),
        {"org_id": str(org_id)},
    ).scalar()
    total_outstanding = Decimal(str(total_outstanding_row or "0"))

    # Total overdue outstanding
    overdue_rows = db.execute(
        text("""
            WITH io AS (
                SELECT i.id, i.due_date,
                    i.total_amount - COALESCE(
                        (SELECT SUM(pa.allocated_amount) FROM payment_allocations pa WHERE pa.invoice_id = i.id), 0
                    ) AS outstanding
                FROM invoices i
                WHERE i.org_id = :org_id AND i.deleted_at IS NULL AND i.status NOT IN ('paid','cancelled')
            )
            SELECT COUNT(*), COALESCE(SUM(outstanding), 0)
            FROM io
            WHERE due_date < :today AND outstanding > 0
        """),
        {"org_id": str(org_id), "today": today},
    ).fetchone()
    overdue_count = int(overdue_rows[0] or 0)
    total_overdue = Decimal(str(overdue_rows[1] or "0"))

    # Collected this month
    collected_this_month = db.execute(
        text("""
            SELECT COALESCE(SUM(pa.allocated_amount), 0)
            FROM payment_allocations pa
            JOIN payments p ON p.id = pa.payment_id
            WHERE p.org_id = :org_id
              AND p.received_date >= :month_start
        """),
        {"org_id": str(org_id), "month_start": this_month_start},
    ).scalar()
    collected_this_month = Decimal(str(collected_this_month or "0"))

    # Total invoiced (all time, non-cancelled)
    total_invoiced = db.execute(
        text("""
            SELECT COALESCE(SUM(total_amount), 0) FROM invoices
            WHERE org_id = :org_id AND deleted_at IS NULL AND status != 'cancelled'
        """),
        {"org_id": str(org_id)},
    ).scalar()
    total_invoiced = Decimal(str(total_invoiced or "0"))

    # Collection rate = total collected / total invoiced
    total_collected = db.execute(
        text("""
            SELECT COALESCE(SUM(pa.allocated_amount), 0)
            FROM payment_allocations pa
            JOIN payments p ON p.id = pa.payment_id
            WHERE p.org_id = :org_id
        """),
        {"org_id": str(org_id)},
    ).scalar()
    total_collected = Decimal(str(total_collected or "0"))
    collection_rate = float(total_collected / total_invoiced * 100) if total_invoiced > 0 else 0.0

    # Pending follow-ups
    pending_follow_ups = (
        db.query(func.count(FollowUp.id))
        .filter(FollowUp.org_id == org_id, FollowUp.status == FollowUpStatus.pending.value)
        .scalar()
    ) or 0

    # Invoices due this week
    due_this_week = (
        db.query(func.count(Invoice.id))
        .filter(
            Invoice.org_id == org_id,
            Invoice.deleted_at == None,
            Invoice.due_date >= today,
            Invoice.due_date <= next_week,
            Invoice.status.notin_(["paid", "cancelled"]),
        )
        .scalar()
    ) or 0

    # High-risk outstanding
    high_risk_outstanding = db.execute(
        text("""
            WITH io AS (
                SELECT i.id, c.risk_tier,
                    i.total_amount - COALESCE(
                        (SELECT SUM(pa.allocated_amount) FROM payment_allocations pa WHERE pa.invoice_id = i.id), 0
                    ) AS outstanding
                FROM invoices i
                JOIN customers c ON c.id = i.customer_id
                WHERE i.org_id = :org_id AND i.deleted_at IS NULL AND i.status NOT IN ('paid','cancelled')
            )
            SELECT COALESCE(SUM(outstanding), 0) FROM io WHERE risk_tier = 'high' AND outstanding > 0
        """),
        {"org_id": str(org_id)},
    ).scalar()
    high_risk_outstanding = Decimal(str(high_risk_outstanding or "0"))

    # Aging buckets
    raw_buckets = _get_aging_data(db, org_id, today)
    bucket_map = {r["bucket"]: r for r in raw_buckets}
    total_outstanding_for_pct = sum(r["total_outstanding"] for r in raw_buckets) or Decimal("1")

    aging_buckets = []
    for key in BUCKET_ORDER:
        label, days_min, days_max = BUCKET_META[key]
        data = bucket_map.get(key, {"invoice_count": 0, "total_outstanding": Decimal("0")})
        pct = float(data["total_outstanding"] / total_outstanding_for_pct * 100)
        aging_buckets.append(AgingBucket(
            label=label,
            days_min=days_min,
            days_max=days_max,
            amount=data["total_outstanding"],
            invoice_count=data["invoice_count"],
            percentage=round(pct, 1),
        ))

    return DashboardSummary(
        total_outstanding=total_outstanding,
        total_overdue=total_overdue,
        overdue_count=overdue_count,
        collected_this_month=collected_this_month,
        collection_rate_pct=round(collection_rate, 1),
        aging_buckets=aging_buckets,
        pending_follow_ups=pending_follow_ups,
        invoices_due_this_week=due_this_week,
        high_risk_outstanding=high_risk_outstanding,
        is_synthetic=True,
    )


def get_collection_trend(db: Session, org_id: UUID, months: int = 6) -> list[CollectionTrendPoint]:
    """
    Monthly collection trend for the last N months.
    Collection rate = collected / invoiced for each month.
    """
    rows = db.execute(
        text("""
            SELECT
                TO_CHAR(i.issue_date, 'YYYY-MM') AS month,
                COALESCE(SUM(i.total_amount), 0) AS invoiced,
                COALESCE(SUM(
                    (SELECT COALESCE(SUM(pa.allocated_amount), 0)
                     FROM payment_allocations pa
                     WHERE pa.invoice_id = i.id)
                ), 0) AS collected
            FROM invoices i
            WHERE i.org_id = :org_id
              AND i.deleted_at IS NULL
              AND i.status != 'cancelled'
              AND i.issue_date >= CURRENT_DATE - (:months || ' month')::interval
            GROUP BY month
            ORDER BY month DESC
            LIMIT :months
        """),
        {"org_id": str(org_id), "months": months},
    ).fetchall()

    points = []
    for row in reversed(rows):
        month, invoiced, collected = row[0], Decimal(str(row[1])), Decimal(str(row[2]))
        overdue = invoiced - collected if invoiced > collected else Decimal("0")
        rate = float(collected / invoiced * 100) if invoiced > 0 else 0.0
        points.append(CollectionTrendPoint(
            month=month,
            invoiced=invoiced,
            collected=collected,
            overdue=overdue,
            collection_rate_pct=round(rate, 1),
        ))
    return points
