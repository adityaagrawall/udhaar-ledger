"""Customer service."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.follow_up import FollowUp
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerOut,
    CustomerListResponse,
    CustomerCreditSummary,
    CustomerAgingSummary,
    CustomerLedgerEntry,
    CustomerOpenInvoiceItem,
    CustomerPtpItem,
    CustomerLedgerResponse,
)
from app.services.invoice_service import _get_outstanding_balance


def create_customer(payload: CustomerCreate, org_id: UUID, db: Session) -> CustomerOut:
    customer = Customer(org_id=org_id, **payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return CustomerOut.model_validate(customer)


def get_customer(customer_id: UUID, org_id: UUID, db: Session) -> CustomerOut:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.org_id == org_id, Customer.deleted_at == None)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    out = CustomerOut.model_validate(customer)
    # Calculate real balances
    rows = db.execute(
        text("""
            SELECT 
                COUNT(DISTINCT i.id) AS inv_count,
                COALESCE(SUM(i.total_amount - COALESCE(pa.allocated, 0)), 0) AS total_out,
                COALESCE(SUM(CASE WHEN i.due_date < CURRENT_DATE THEN i.total_amount - COALESCE(pa.allocated, 0) ELSE 0 END), 0) AS total_ovd
            FROM invoices i
            LEFT JOIN (
                SELECT invoice_id, SUM(allocated_amount) AS allocated
                FROM payment_allocations
                GROUP BY invoice_id
            ) pa ON pa.invoice_id = i.id
            WHERE i.customer_id = :customer_id
              AND i.org_id = :org_id
              AND i.deleted_at IS NULL
              AND i.status NOT IN ('paid', 'cancelled')
        """),
        {"customer_id": str(customer_id), "org_id": str(org_id)},
    ).fetchone()
    if rows:
        out.invoice_count = rows.inv_count
        out.total_outstanding = Decimal(str(rows.total_out))
        out.total_overdue = Decimal(str(rows.total_ovd))
    return out


def list_customers(
    org_id: UUID,
    db: Session,
    search: str | None = None,
    risk_tier: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> CustomerListResponse:
    stmt = select(Customer).where(Customer.org_id == org_id, Customer.deleted_at == None)
    if search:
        stmt = stmt.where(Customer.name.ilike(f"%{search.strip()}%"))
    if risk_tier:
        stmt = stmt.where(Customer.risk_tier == risk_tier)
    stmt = stmt.order_by(Customer.name.asc())
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    customers = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()

    # Pre-aggregate real-time balances for this page of customers
    balances_map = {}
    cust_ids = [c.id for c in customers]
    if cust_ids:
        rows = db.execute(
            text("""
                SELECT 
                    i.customer_id,
                    COUNT(DISTINCT i.id) AS inv_count,
                    COALESCE(SUM(i.total_amount - COALESCE(pa.allocated, 0)), 0) AS total_out,
                    COALESCE(SUM(CASE WHEN i.due_date < CURRENT_DATE THEN i.total_amount - COALESCE(pa.allocated, 0) ELSE 0 END), 0) AS total_ovd
                FROM invoices i
                LEFT JOIN (
                    SELECT invoice_id, SUM(allocated_amount) AS allocated
                    FROM payment_allocations
                    GROUP BY invoice_id
                ) pa ON pa.invoice_id = i.id
                WHERE i.customer_id IN :cust_ids
                  AND i.org_id = :org_id
                  AND i.deleted_at IS NULL
                  AND i.status NOT IN ('paid', 'cancelled')
                GROUP BY i.customer_id
            """),
            {"cust_ids": tuple(cust_ids), "org_id": str(org_id)},
        ).fetchall()
        for r in rows:
            balances_map[r.customer_id] = {
                "count": r.inv_count,
                "outstanding": Decimal(str(r.total_out)),
                "overdue": Decimal(str(r.total_ovd)),
            }

    items = []
    for c in customers:
        c_out = CustomerOut.model_validate(c)
        stats = balances_map.get(c.id, {})
        c_out.invoice_count = stats.get("count", 0)
        c_out.total_outstanding = stats.get("outstanding", Decimal("0"))
        c_out.total_overdue = stats.get("overdue", Decimal("0"))
        items.append(c_out)

    return CustomerListResponse(
        items=items,
        total=total,
        page=page,
        per_page=page_size,
        page_size=page_size,
    )


def update_customer(customer_id: UUID, org_id: UUID, payload: CustomerUpdate, db: Session) -> CustomerOut:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.org_id == org_id, Customer.deleted_at == None)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(customer, field, val)
    db.commit()
    db.refresh(customer)
    return CustomerOut.model_validate(customer)


def delete_customer(customer_id: UUID, org_id: UUID, db: Session) -> None:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.org_id == org_id, Customer.deleted_at == None)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    from datetime import timezone
    customer.deleted_at = datetime.now(timezone.utc)
    customer.is_active = False
    db.commit()


def get_customer_ledger(customer_id: UUID, org_id: UUID, db: Session) -> CustomerLedgerResponse:
    today = date.today()
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.org_id == org_id, Customer.deleted_at == None)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Invoices
    invoices = (
        db.query(Invoice)
        .filter(Invoice.customer_id == customer_id, Invoice.org_id == org_id, Invoice.deleted_at == None)
        .order_by(Invoice.issue_date.asc())
        .all()
    )

    # Payments
    payments = (
        db.query(Payment)
        .filter(Payment.customer_id == customer_id, Payment.org_id == org_id)
        .order_by(Payment.received_date.asc())
        .all()
    )

    # Follow-ups / Promises
    follow_ups = (
        db.query(FollowUp)
        .filter(FollowUp.customer_id == customer_id, FollowUp.org_id == org_id)
        .order_by(FollowUp.created_at.desc())
        .all()
    )

    total_outstanding = Decimal("0")
    total_overdue = Decimal("0")
    overdue_count = 0
    lifetime_invoiced = Decimal("0")
    current_aging = Decimal("0")
    days_1_30 = Decimal("0")
    days_31_60 = Decimal("0")
    days_61_90 = Decimal("0")
    beyond_90 = Decimal("0")

    open_invoices_list = []
    inv_map = {inv.id: inv.invoice_number for inv in invoices}

    for inv in invoices:
        if inv.status != "cancelled":
            lifetime_invoiced += inv.total_amount

        bal = _get_outstanding_balance(db, inv.id)
        paid = inv.total_amount - bal

        if bal > Decimal("0") and inv.status != "cancelled":
            total_outstanding += bal
            days_over = max(0, (today - inv.due_date).days)
            if days_over > 0:
                total_overdue += bal
                overdue_count += 1
                if days_over <= 30:
                    days_1_30 += bal
                elif days_over <= 60:
                    days_31_60 += bal
                elif days_over <= 90:
                    days_61_90 += bal
                else:
                    beyond_90 += bal
            else:
                current_aging += bal

            open_invoices_list.append(
                CustomerOpenInvoiceItem(
                    id=inv.id,
                    invoice_number=inv.invoice_number,
                    issue_date=inv.issue_date,
                    due_date=inv.due_date,
                    days_overdue=days_over,
                    total_amount=inv.total_amount,
                    paid_amount=paid,
                    outstanding_balance=bal,
                    status=inv.status,
                )
            )

    open_invoices_list.sort(key=lambda x: x.due_date)

    lifetime_collected = sum((p.amount for p in payments), Decimal("0"))
    available_credit = max(Decimal("0"), customer.credit_limit - total_outstanding)
    utilization_pct = (
        round(float(total_outstanding / customer.credit_limit) * 100, 1)
        if customer.credit_limit > Decimal("0")
        else 0.0
    )

    if utilization_pct > 120 or (customer.credit_limit > 0 and total_overdue > customer.credit_limit * Decimal("0.5")):
        health_status = "CRITICAL"
    elif utilization_pct > 100 or total_overdue > Decimal("0"):
        health_status = "WARNING"
    elif utilization_pct > 75:
        health_status = "MONITOR"
    else:
        health_status = "HEALTHY"

    credit_summary = CustomerCreditSummary(
        credit_limit=customer.credit_limit,
        total_outstanding=total_outstanding,
        available_credit=available_credit,
        utilization_pct=utilization_pct,
        total_overdue=total_overdue,
        overdue_invoices_count=overdue_count,
        lifetime_invoiced=lifetime_invoiced,
        lifetime_collected=lifetime_collected,
        health_status=health_status,
    )

    aging_summary = CustomerAgingSummary(
        current=current_aging,
        days_1_30=days_1_30,
        days_31_60=days_31_60,
        days_61_90=days_61_90,
        beyond_90=beyond_90,
    )

    # Build chronological Statement of Account (SOA) ledger
    raw_entries = []
    for inv in invoices:
        if inv.status != "cancelled":
            raw_entries.append({
                "id": str(inv.id),
                "type": "INVOICE",
                "date": inv.issue_date,
                "reference": f"Inv #{inv.invoice_number}",
                "debit": inv.total_amount,
                "credit": None,
                "status": inv.status.upper(),
                "notes": inv.notes,
                "sort_key": (inv.issue_date, 0),
            })

    for pay in payments:
        raw_entries.append({
            "id": str(pay.id),
            "type": "PAYMENT",
            "date": pay.received_date,
            "reference": f"Pay: {pay.reference_no or pay.payment_mode.upper()}",
            "debit": None,
            "credit": pay.amount,
            "status": pay.payment_mode.upper(),
            "notes": pay.notes,
            "sort_key": (pay.received_date, 1),
        })

    raw_entries.sort(key=lambda x: x["sort_key"])
    running_balance = Decimal("0")
    ledger_entries = []

    for entry in raw_entries:
        if entry["debit"]:
            running_balance += entry["debit"]
        if entry["credit"]:
            running_balance -= entry["credit"]

        ledger_entries.append(
            CustomerLedgerEntry(
                id=entry["id"],
                entry_type=entry["type"],
                date=entry["date"],
                reference=entry["reference"],
                debit=entry["debit"],
                credit=entry["credit"],
                running_balance=running_balance,
                status=entry["status"],
                notes=entry["notes"],
            )
        )

    ledger_entries.reverse()

    promises_list = []
    for fu in follow_ups:
        if fu.promised_date is not None or fu.promise_status is not None:
            promises_list.append(
                CustomerPtpItem(
                    id=fu.id,
                    invoice_id=fu.invoice_id,
                    invoice_number=inv_map.get(fu.invoice_id, "—"),
                    promised_amount=fu.promised_amount,
                    promised_date=fu.promised_date,
                    promise_status=fu.promise_status or ("broken" if fu.promised_date and fu.promised_date < today else "pending"),
                    channel=fu.channel,
                    notes=fu.notes,
                    created_at=fu.created_at,
                )
            )

    cust_out = CustomerOut.model_validate(customer)
    cust_out.total_outstanding = total_outstanding
    cust_out.total_overdue = total_overdue
    cust_out.invoice_count = len(open_invoices_list)

    return CustomerLedgerResponse(
        customer=cust_out,
        credit_summary=credit_summary,
        aging_summary=aging_summary,
        ledger=ledger_entries,
        open_invoices=open_invoices_list,
        promises=promises_list,
    )
