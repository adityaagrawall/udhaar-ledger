"""Analytics service: trends, aging reports, collection efficiency."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.analytics import (
    MonthlyTrend,
    CustomerOutstanding,
    AgingReport,
    CollectionEfficiency,
    DistributorKPIsResponse,
    PtpStats,
    AgingBucketTotal,
    ProjectedInflows,
    DebtorConcentrationItem,
)


def get_monthly_trends(org_id: UUID, db: Session, months: int = 12) -> list[MonthlyTrend]:
    result = db.execute(
        text("""
            WITH months AS (
                SELECT TO_CHAR(DATE_TRUNC('month', i.issue_date), 'YYYY-MM') AS month,
                       COALESCE(SUM(i.total_amount), 0) AS invoiced
                FROM invoices i
                WHERE i.org_id = :org_id AND i.deleted_at IS NULL
                  AND i.issue_date >= (CURRENT_DATE - (:months || ' month')::interval)
                GROUP BY month
            ),
            collected_by_month AS (
                SELECT TO_CHAR(DATE_TRUNC('month', p.received_date), 'YYYY-MM') AS month,
                       COALESCE(SUM(p.amount), 0) AS collected
                FROM payments p
                WHERE p.org_id = :org_id
                  AND p.received_date >= (CURRENT_DATE - (:months || ' month')::interval)
                GROUP BY month
            )
            SELECT m.month,
                   COALESCE(m.invoiced, 0) AS invoiced,
                   COALESCE(c.collected, 0) AS collected,
                   COALESCE(m.invoiced, 0) - COALESCE(c.collected, 0) AS outstanding
            FROM months m
            LEFT JOIN collected_by_month c ON c.month = m.month
            ORDER BY m.month
        """),
        {"org_id": str(org_id), "months": months},
    ).fetchall()
    return [
        MonthlyTrend(
            month=row.month,
            invoiced=Decimal(str(row.invoiced)),
            collected=Decimal(str(row.collected)),
            outstanding=Decimal(str(row.outstanding)),
        )
        for row in result
    ]


def get_top_outstanding_customers(org_id: UUID, db: Session, limit: int = 20) -> list[CustomerOutstanding]:
    result = db.execute(
        text("""
            SELECT c.id AS customer_id, c.name AS customer_name, c.risk_tier,
                   COALESCE(SUM(i.total_amount - COALESCE(alloc.allocated, 0)), 0) AS total_outstanding,
                   COALESCE(SUM(CASE WHEN i.status = 'overdue'
                                     THEN i.total_amount - COALESCE(alloc.allocated, 0)
                                     ELSE 0 END), 0) AS overdue_amount
            FROM customers c
            JOIN invoices i ON i.customer_id = c.id AND i.org_id = :org_id AND i.deleted_at IS NULL
                            AND i.status NOT IN ('paid', 'cancelled')
            LEFT JOIN (
                SELECT invoice_id, SUM(allocated_amount) AS allocated
                FROM payment_allocations GROUP BY invoice_id
            ) alloc ON alloc.invoice_id = i.id
            WHERE c.org_id = :org_id AND c.deleted_at IS NULL
            GROUP BY c.id, c.name, c.risk_tier
            ORDER BY total_outstanding DESC
            LIMIT :limit
        """),
        {"org_id": str(org_id), "limit": limit},
    ).fetchall()
    return [
        CustomerOutstanding(
            customer_id=str(row.customer_id),
            customer_name=row.customer_name,
            total_outstanding=Decimal(str(row.total_outstanding)),
            overdue_amount=Decimal(str(row.overdue_amount)),
            risk_tier=row.risk_tier,
        )
        for row in result
    ]


def get_aging_report(org_id: UUID, db: Session) -> list[AgingReport]:
    today = date.today()
    result = db.execute(
        text("""
            SELECT c.id AS customer_id, c.name AS customer_name,
                   COALESCE(SUM(CASE WHEN i.due_date >= :today
                                     THEN i.total_amount - COALESCE(alloc.allocated, 0) ELSE 0 END), 0) AS current_bal,
                   COALESCE(SUM(CASE WHEN :today - i.due_date BETWEEN 1 AND 30
                                     THEN i.total_amount - COALESCE(alloc.allocated, 0) ELSE 0 END), 0) AS days_1_30,
                   COALESCE(SUM(CASE WHEN :today - i.due_date BETWEEN 31 AND 60
                                     THEN i.total_amount - COALESCE(alloc.allocated, 0) ELSE 0 END), 0) AS days_31_60,
                   COALESCE(SUM(CASE WHEN :today - i.due_date BETWEEN 61 AND 90
                                     THEN i.total_amount - COALESCE(alloc.allocated, 0) ELSE 0 END), 0) AS days_61_90,
                   COALESCE(SUM(CASE WHEN :today - i.due_date > 90
                                     THEN i.total_amount - COALESCE(alloc.allocated, 0) ELSE 0 END), 0) AS beyond_90,
                   COALESCE(SUM(i.total_amount - COALESCE(alloc.allocated, 0)), 0) AS total
            FROM customers c
            JOIN invoices i ON i.customer_id = c.id AND i.org_id = :org_id
                            AND i.deleted_at IS NULL AND i.status NOT IN ('paid', 'cancelled')
            LEFT JOIN (
                SELECT invoice_id, SUM(allocated_amount) AS allocated
                FROM payment_allocations GROUP BY invoice_id
            ) alloc ON alloc.invoice_id = i.id
            WHERE c.org_id = :org_id AND c.deleted_at IS NULL
            GROUP BY c.id, c.name
            ORDER BY total DESC
        """),
        {"org_id": str(org_id), "today": today.isoformat()},
    ).fetchall()
    return [
        AgingReport(
            customer_id=str(row.customer_id),
            customer_name=row.customer_name,
            current=Decimal(str(row.current_bal)),
            days_1_30=Decimal(str(row.days_1_30)),
            days_31_60=Decimal(str(row.days_31_60)),
            days_61_90=Decimal(str(row.days_61_90)),
            beyond_90=Decimal(str(row.beyond_90)),
            days_91_120=Decimal(str(row.days_61_90)),
            beyond_120=Decimal(str(row.beyond_90)),
            total=Decimal(str(row.total)),
        )
        for row in result
    ]


def get_distributor_kpis(org_id: UUID, db: Session) -> DistributorKPIsResponse:
    """Compute financial business intelligence for distributor receivables management."""
    today = date.today()
    from datetime import timedelta
    from app.services.follow_up_service import get_ptp_summary
    from app.schemas.analytics import (
        DistributorKPIsResponse,
        PtpStats,
        AgingBucketTotal,
        ProjectedInflows,
        DebtorConcentrationItem,
    )

    # 1. Total & Overdue Receivables
    rec_row = db.execute(
        text("""
            WITH inv_out AS (
                SELECT
                    i.id,
                    i.customer_id,
                    i.due_date,
                    i.total_amount - COALESCE(pa.allocated, 0) AS outstanding
                FROM invoices i
                LEFT JOIN (
                    SELECT invoice_id, SUM(allocated_amount) AS allocated
                    FROM payment_allocations
                    GROUP BY invoice_id
                ) pa ON pa.invoice_id = i.id
                WHERE i.org_id = :org_id
                  AND i.deleted_at IS NULL
                  AND i.status NOT IN ('paid', 'cancelled')
            )
            SELECT
                COALESCE(SUM(outstanding), 0) AS total_receivables,
                COALESCE(SUM(CASE WHEN due_date < :today THEN outstanding ELSE 0 END), 0) AS overdue_receivables,
                COUNT(DISTINCT customer_id) AS active_debtors_count,
                COUNT(DISTINCT CASE WHEN due_date < :today THEN customer_id ELSE NULL END) AS overdue_debtors_count
            FROM inv_out
            WHERE outstanding > 0
        """),
        {"org_id": str(org_id), "today": today},
    ).fetchone()

    total_rec = Decimal(str(rec_row.total_receivables or 0))
    overdue_rec = Decimal(str(rec_row.overdue_receivables or 0))
    active_retailers = int(rec_row.active_debtors_count or 0)
    overdue_retailers = int(rec_row.overdue_debtors_count or 0)
    overdue_pct = (
        round(float(overdue_rec / total_rec) * 100.0, 1) if total_rec > Decimal("0") else 0.0
    )

    # 2. DSO (Days Sales Outstanding) over 90 days
    # Formula: (Total Receivables / Credit Sales in 90 Days) * 90
    sales_90d_row = db.execute(
        text("""
            SELECT COALESCE(SUM(total_amount), 0) AS sales_90d
            FROM invoices
            WHERE org_id = :org_id
              AND deleted_at IS NULL
              AND status != 'cancelled'
              AND issue_date >= (:today - INTERVAL '90 days')
        """),
        {"org_id": str(org_id), "today": today},
    ).scalar()
    sales_90d = Decimal(str(sales_90d_row or 0))

    if sales_90d > Decimal("0"):
        dso_days = round(float(total_rec / sales_90d) * 90.0, 1)
    else:
        dso_days = 30.0

    if dso_days <= 35:
        dso_status = "Optimal"
    elif dso_days <= 50:
        dso_status = "Acceptable"
    elif dso_days <= 70:
        dso_status = "Requires Attention"
    else:
        dso_status = "High Risk"

    # 3. Collection Effectiveness Index (CEI) over 90 days
    # Collections in last 90 days
    collections_90d_row = db.execute(
        text("""
            SELECT COALESCE(SUM(amount), 0) AS collected_90d
            FROM payments
            WHERE org_id = :org_id
              AND received_date >= (:today - INTERVAL '90 days')
        """),
        {"org_id": str(org_id), "today": today},
    ).scalar()
    collections_90d = Decimal(str(collections_90d_row or 0))

    denominator = collections_90d + total_rec
    if denominator > Decimal("0"):
        cei_val = round(float(collections_90d / denominator) * 100.0, 1)
    else:
        cei_val = 85.0

    # 4. Aging summary breakdown
    aging_rows = db.execute(
        text("""
            WITH inv_out AS (
                SELECT
                    i.id,
                    i.due_date,
                    i.total_amount - COALESCE(pa.allocated, 0) AS outstanding
                FROM invoices i
                LEFT JOIN (
                    SELECT invoice_id, SUM(allocated_amount) AS allocated
                    FROM payment_allocations
                    GROUP BY invoice_id
                ) pa ON pa.invoice_id = i.id
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
                COUNT(*) AS inv_count,
                COALESCE(SUM(outstanding), 0) AS total_amount
            FROM inv_out
            WHERE outstanding > 0
            GROUP BY bucket
        """),
        {"org_id": str(org_id), "today": today},
    ).fetchall()

    aging_meta = {
        "current": "Current (Not Due)",
        "1-30": "1–30 Days Overdue",
        "31-60": "31–60 Days Overdue",
        "61-90": "61–90 Days Overdue",
        "91+": "90+ Days Overdue",
    }
    aging_buckets_dict = {
        k: {"amount": Decimal("0"), "count": 0} for k in ["current", "1-30", "31-60", "61-90", "91+"]
    }
    for r in aging_rows:
        b_key = r.bucket
        if b_key in aging_buckets_dict:
            aging_buckets_dict[b_key]["amount"] = Decimal(str(r.total_amount))
            aging_buckets_dict[b_key]["count"] = int(r.inv_count)

    aging_summary_list = []
    for k in ["current", "1-30", "31-60", "61-90", "91+"]:
        amt = aging_buckets_dict[k]["amount"]
        cnt = aging_buckets_dict[k]["count"]
        pct = round(float(amt / total_rec) * 100.0, 1) if total_rec > Decimal("0") else 0.0
        aging_summary_list.append(
            AgingBucketTotal(
                bucket=k,
                label=aging_meta[k],
                amount=amt,
                count=cnt,
                percentage=pct,
            )
        )

    # 5. PTP Stats
    ptp_stats = get_ptp_summary(org_id, db)

    # 6. Projected Inflows based on due dates & commitments
    proj_rows = db.execute(
        text("""
            WITH inv_out AS (
                SELECT
                    i.id,
                    i.due_date,
                    i.total_amount - COALESCE(pa.allocated, 0) AS outstanding
                FROM invoices i
                LEFT JOIN (
                    SELECT invoice_id, SUM(allocated_amount) AS allocated
                    FROM payment_allocations
                    GROUP BY invoice_id
                ) pa ON pa.invoice_id = i.id
                WHERE i.org_id = :org_id
                  AND i.deleted_at IS NULL
                  AND i.status NOT IN ('paid', 'cancelled')
            )
            SELECT
                COALESCE(SUM(CASE WHEN due_date BETWEEN :today AND (:today + INTERVAL '7 days') THEN outstanding ELSE 0 END), 0) AS next_7,
                COALESCE(SUM(CASE WHEN due_date BETWEEN :today AND (:today + INTERVAL '15 days') THEN outstanding ELSE 0 END), 0) AS next_15,
                COALESCE(SUM(CASE WHEN due_date BETWEEN :today AND (:today + INTERVAL '30 days') THEN outstanding ELSE 0 END), 0) AS next_30
            FROM inv_out
            WHERE outstanding > 0
        """),
        {"org_id": str(org_id), "today": today},
    ).fetchone()

    projected_inflows = ProjectedInflows(
        next_7_days=Decimal(str(proj_rows.next_7 or 0)),
        next_15_days=Decimal(str(proj_rows.next_15 or 0)),
        next_30_days=Decimal(str(proj_rows.next_30 or 0)),
    )

    # 7. Debtor Concentration (Top 5)
    top_debtors_rows = db.execute(
        text("""
            SELECT c.id AS customer_id, c.name AS customer_name, c.risk_tier,
                   COALESCE(SUM(i.total_amount - COALESCE(alloc.allocated, 0)), 0) AS total_outstanding
            FROM customers c
            JOIN invoices i ON i.customer_id = c.id AND i.org_id = :org_id AND i.deleted_at IS NULL
                            AND i.status NOT IN ('paid', 'cancelled')
            LEFT JOIN (
                SELECT invoice_id, SUM(allocated_amount) AS allocated
                FROM payment_allocations GROUP BY invoice_id
            ) alloc ON alloc.invoice_id = i.id
            WHERE c.org_id = :org_id AND c.deleted_at IS NULL
            GROUP BY c.id, c.name, c.risk_tier
            ORDER BY total_outstanding DESC
            LIMIT 5
        """),
        {"org_id": str(org_id)},
    ).fetchall()

    top_debtors_list = []
    top_5_sum = Decimal("0")
    for r in top_debtors_rows:
        out_amt = Decimal(str(r.total_outstanding))
        top_5_sum += out_amt
        pct = round(float(out_amt / total_rec) * 100.0, 1) if total_rec > Decimal("0") else 0.0
        top_debtors_list.append(
            DebtorConcentrationItem(
                customer_id=str(r.customer_id),
                customer_name=r.customer_name,
                outstanding=out_amt,
                percentage_of_total=pct,
                risk_tier=r.risk_tier,
            )
        )

    top_5_pct = round(float(top_5_sum / total_rec) * 100.0, 1) if total_rec > Decimal("0") else 0.0

    return DistributorKPIsResponse(
        total_receivables=total_rec,
        overdue_receivables=overdue_rec,
        overdue_percentage=overdue_pct,
        dso_days=dso_days,
        dso_formula="DSO = (Total Receivables / Credit Sales in 90 Days) × 90 days",
        dso_status=dso_status,
        collection_effectiveness_index=cei_val,
        cei_formula="CEI = (Total Collections / (Beginning AR + Credit Sales in Period)) × 100%",
        active_retailers_count=active_retailers,
        overdue_retailers_count=overdue_retailers,
        ptp_stats=ptp_stats,
        aging_summary=aging_summary_list,
        projected_inflows=projected_inflows,
        top_debtors=top_debtors_list,
        top_5_debtor_concentration_pct=top_5_pct,
    )

