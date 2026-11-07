"""Export endpoints for CSV downloads."""
import csv
import io
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.services.invoice_service import list_invoices
from app.services.collection_service import get_collection_queue
from app.services.analytics_service import get_aging_report

router = APIRouter()


def _sanitize_csv_cell(val):
    if isinstance(val, str) and val.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + val
    return val


@router.get("/invoices")
def export_invoices_csv(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, _ = list_invoices(db, current_user.org_id, page=1, per_page=10000)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Invoice Number",
        "Customer Name",
        "Issue Date",
        "Due Date",
        "Total Amount (INR)",
        "Outstanding Balance (INR)",
        "Days Overdue",
        "Status",
    ])

    for inv in items:
        writer.writerow([
            _sanitize_csv_cell(inv["invoice_number"]),
            _sanitize_csv_cell(inv["customer_name"] or ""),
            inv["issue_date"].isoformat() if inv["issue_date"] else "",
            inv["due_date"].isoformat() if inv["due_date"] else "",
            float(inv["total_amount"]),
            float(inv["outstanding_balance"]),
            inv["days_overdue"],
            inv["status"],
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=collectiq_invoices_{date.today().isoformat()}.csv"},
    )


@router.get("/queue")
def export_queue_csv(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    queue_data = get_collection_queue(db, current_user.org_id, page=1, per_page=10000)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Priority Score",
        "Invoice Number",
        "Customer Name",
        "Risk Tier",
        "Outstanding Balance (INR)",
        "Due Date",
        "Days Overdue",
        "Reasons",
    ])

    for item in queue_data.items:
        writer.writerow([
            item.priority_score,
            _sanitize_csv_cell(item.invoice_number),
            _sanitize_csv_cell(item.customer_name),
            item.risk_tier,
            float(item.outstanding_balance),
            item.due_date,
            item.days_overdue,
            _sanitize_csv_cell("; ".join(item.priority_reasons)),
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=collectiq_collections_queue_{date.today().isoformat()}.csv"},
    )
