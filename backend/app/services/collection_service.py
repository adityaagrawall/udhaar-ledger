"""
Collection priority queue service.

Priority score is deterministic and explainable. Formula:
  - Days overdue: up to 40 points (0.5 pts/day, capped at 40)
  - Outstanding amount: up to 30 points (log10 scale * 5)
  - Customer risk tier: high=20, medium=10, low=5
  - No recent follow-up (>7 days or none): +10

Each invoice returns its score AND the reasons list for display.
"""

import math
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, text, or_
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.follow_up import FollowUp, FollowUpStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import PaymentAllocation
from app.schemas.analytics import CollectionQueueItem, CollectionQueueResponse


def _get_outstanding(db: Session, invoice_id: UUID) -> Decimal:
    allocated = (
        db.query(func.coalesce(func.sum(PaymentAllocation.allocated_amount), Decimal("0")))
        .filter(PaymentAllocation.invoice_id == invoice_id)
        .scalar()
    )
    inv_total = db.query(Invoice.total_amount).filter(Invoice.id == invoice_id).scalar()
    return Decimal(str(inv_total or 0)) - Decimal(str(allocated or 0))


def calculate_priority_score(
    invoice: Invoice,
    customer: Customer,
    last_follow_up_date: Optional[date],
    outstanding_balance: Optional[Decimal] = None,
    has_broken_promise: bool = False,
    promise_status: Optional[str] = None,
) -> tuple[float, list[str]]:
    score = 0.0
    reasons = []
    today = date.today()

    # 1. Days overdue (0–40 pts)
    days_overdue = max(0, (today - invoice.due_date).days)
    overdue_score = min(40.0, days_overdue * 0.5)
    score += overdue_score
    if days_overdue > 0:
        reasons.append(f"{days_overdue} days overdue")
    if days_overdue > 60:
        reasons.append("Critically overdue — escalation recommended")
    elif days_overdue > 30:
        reasons.append("Significantly overdue")

    # 2. Amount (0–30 pts, log10 scale of actual outstanding balance)
    if outstanding_balance is not None:
        outstanding_float = float(outstanding_balance)
    else:
        outstanding_float = float(invoice.total_amount)
    amount_score = min(30.0, math.log10(max(1.0, outstanding_float)) * 5)
    score += amount_score
    if outstanding_float >= 500_000:
        reasons.append(f"Large outstanding balance (₹{outstanding_float:,.0f})")

    # 3. Customer risk tier (0–20 pts)
    tier_scores = {"high": 20.0, "medium": 10.0, "low": 5.0}
    tier_score = tier_scores.get(customer.risk_tier, 10.0)
    score += tier_score
    if customer.risk_tier == "high":
        reasons.append("High-risk customer profile")
    elif customer.risk_tier == "medium":
        reasons.append("Medium-risk customer")

    # 4. Broken Promise-to-Pay penalty (+15 pts)
    if has_broken_promise:
        score += 15.0
        reasons.append("Broken Promise-to-Pay")
    elif promise_status == "pending":
        reasons.append("Active Promise-to-Pay")

    # 5. Follow-up recency (0–10 pts)
    seven_days_ago = today - timedelta(days=7)
    if last_follow_up_date is None or last_follow_up_date < seven_days_ago:
        score += 10.0
        if last_follow_up_date is None:
            reasons.append("No follow-up attempted yet")
        else:
            days_since = (today - last_follow_up_date).days
            reasons.append(f"Last follow-up {days_since} days ago")

    return round(score, 2), reasons


def get_collection_queue(
    db: Session,
    org_id: UUID,
    page: int = 1,
    per_page: int = 50,
    risk_tier: Optional[str] = None,
    min_days_overdue: int = 0,
    search: Optional[str] = None,
    promise_filter: Optional[str] = None,
) -> CollectionQueueResponse:
    today = date.today()

    # Base query: overdue or close-to-due invoices
    query = (
        db.query(Invoice, Customer)
        .join(Customer, Customer.id == Invoice.customer_id)
        .filter(
            Invoice.org_id == org_id,
            Invoice.deleted_at == None,
            Invoice.status.notin_(["paid", "cancelled"]),
        )
    )
    if risk_tier:
        query = query.filter(Customer.risk_tier == risk_tier)
    if min_days_overdue > 0:
        cutoff = today - timedelta(days=min_days_overdue)
        query = query.filter(Invoice.due_date <= cutoff)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Invoice.invoice_number.ilike(term),
                Customer.name.ilike(term),
            )
        )

    all_pairs = query.all()

    # Score and sort all items
    scored_items = []
    for invoice, customer in all_pairs:
        outstanding = _get_outstanding(db, invoice.id)
        if outstanding <= 0:
            continue

        # Latest follow-up for this invoice
        latest_fu = (
            db.query(FollowUp)
            .filter(FollowUp.invoice_id == invoice.id)
            .order_by(FollowUp.created_at.desc())
            .first()
        )

        last_fu_date = latest_fu.created_at.date() if latest_fu else None
        has_broken = False
        promise_date_str = None
        promise_status_str = None

        if latest_fu:
            if latest_fu.promised_date:
                promise_date_str = latest_fu.promised_date.isoformat()
            promise_status_str = latest_fu.promise_status

            if latest_fu.promise_status == "broken":
                has_broken = True
            elif latest_fu.promised_date and latest_fu.promised_date < today and latest_fu.promise_status != "fulfilled":
                has_broken = True

        # Apply promise filter if requested
        if promise_filter == "broken" and not has_broken:
            continue
        if promise_filter == "promised" and not (latest_fu and latest_fu.promised_date):
            continue

        score, reasons = calculate_priority_score(
            invoice,
            customer,
            last_fu_date,
            outstanding_balance=outstanding,
            has_broken_promise=has_broken,
            promise_status=promise_status_str,
        )

        # Open follow-up
        open_fu = (
            db.query(FollowUp)
            .filter(
                FollowUp.invoice_id == invoice.id,
                FollowUp.status == FollowUpStatus.pending.value,
            )
            .first()
        )

        days_overdue = max(0, (today - invoice.due_date).days)
        scored_items.append((score, CollectionQueueItem(
            invoice_id=str(invoice.id),
            invoice_number=invoice.invoice_number,
            customer_id=str(customer.id),
            customer_name=customer.name,
            customer_phone=customer.phone,
            outstanding_balance=outstanding,
            total_amount=invoice.total_amount,
            due_date=invoice.due_date.isoformat(),
            days_overdue=days_overdue,
            priority_score=score,
            priority_reasons=reasons,
            risk_tier=customer.risk_tier,
            last_follow_up_status=latest_fu.status if latest_fu else None,
            last_follow_up_date=last_fu_date.isoformat() if last_fu_date else None,
            open_follow_up_id=str(open_fu.id) if open_fu else None,
            has_broken_promise=has_broken,
            promised_date=promise_date_str,
            promise_status=promise_status_str,
        )))

    scored_items.sort(key=lambda x: x[0], reverse=True)
    total = len(scored_items)

    start = (page - 1) * per_page
    end = start + per_page
    page_items = [item for _, item in scored_items[start:end]]

    return CollectionQueueResponse(
        items=page_items,
        total=total,
        page=page,
        per_page=per_page,
    )
