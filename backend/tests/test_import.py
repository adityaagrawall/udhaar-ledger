"""Tests for CSV/XLSX import pipeline, validation, and idempotency."""
import io
import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.organization import Organization
from app.models.user import User
from app.services.import_service import preview_import, commit_import


def _make_csv_bytes(rows: list[dict]) -> bytes:
    import csv
    output = io.StringIO()
    if not rows:
        return b""
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def test_valid_csv_preview_succeeds(db: Session, test_org: Organization):
    csv_bytes = _make_csv_bytes([
        {
            "invoice_number": "INV-TEST-001",
            "customer_name": "Bharat Traders",
            "issue_date": "2024-03-01",
            "due_date": "2024-03-31",
            "total_amount": "45000.00",
        },
        {
            "invoice_number": "INV-TEST-002",
            "customer_name": "Kaveri Enterprises",
            "issue_date": "2024-03-05",
            "due_date": "2024-04-05",
            "total_amount": "82000.00",
        },
    ])

    preview = preview_import(csv_bytes, "test.csv", {}, test_org.id, db)
    assert preview.total_rows == 2
    assert preview.valid_rows == 2
    assert preview.error_rows == 0
    assert len(preview.sample_data) == 2


def test_invalid_amount_rejected(db: Session, test_org: Organization):
    csv_bytes = _make_csv_bytes([
        {
            "invoice_number": "INV-BAD-AMT",
            "customer_name": "Test Customer",
            "issue_date": "2024-03-01",
            "due_date": "2024-03-31",
            "total_amount": "-500.00",  # Negative amount rejected
        }
    ])

    preview = preview_import(csv_bytes, "bad_amount.csv", {}, test_org.id, db)
    assert preview.valid_rows == 0
    assert preview.error_rows == 1
    assert "positive" in preview.errors[0].message


def test_missing_required_column_rejected(db: Session, test_org: Organization):
    csv_bytes = _make_csv_bytes([
        {
            "invoice_number": "INV-NO-AMT",
            "customer_name": "Test Customer",
            "issue_date": "2024-03-01",
            "due_date": "2024-03-31",
            # total_amount missing!
        }
    ])

    with pytest.raises(ValueError, match="Missing required columns"):
        preview_import(csv_bytes, "missing_col.csv", {}, test_org.id, db)


def test_commit_creates_customers_and_invoices(db: Session, test_org: Organization, test_user: User):
    from datetime import timedelta
    today = date.today()
    issue_date = today.isoformat()
    future_due = (today + timedelta(days=30)).isoformat()

    csv_bytes = _make_csv_bytes([
        {
            "invoice_number": "INV-COMMIT-01",
            "customer_name": "New Auto Customer Pvt Ltd",
            "issue_date": issue_date,
            "due_date": future_due,
            "total_amount": "60000.00",
            "payment_amount": "20000.00",
            "payment_date": issue_date,
            "payment_reference": "UTR-TEST-1234",
        }
    ])

    preview = preview_import(csv_bytes, "commit_test.csv", {}, test_org.id, db)
    assert preview.valid_rows == 1

    job = commit_import(preview.preview_token, test_org.id, test_user.id, db)
    assert job.status == "completed"
    assert job.valid_rows == 1

    # Verify customer was auto-created
    cust = db.query(Customer).filter(
        Customer.org_id == test_org.id,
        Customer.name == "New Auto Customer Pvt Ltd",
    ).first()
    assert cust is not None

    # Verify invoice was created with partial status (not yet past due)
    inv = db.query(Invoice).filter(
        Invoice.org_id == test_org.id,
        Invoice.invoice_number == "INV-COMMIT-01",
    ).first()
    assert inv is not None
    assert inv.status == "partial"


def test_reimport_same_file_idempotent(db: Session, test_org: Organization, test_user: User):
    csv_bytes = _make_csv_bytes([
        {
            "invoice_number": "INV-IDEMP-01",
            "customer_name": "Idempotent Corp",
            "issue_date": "2024-04-01",
            "due_date": "2024-04-30",
            "total_amount": "99000.00",
        }
    ])

    preview1 = preview_import(csv_bytes, "idemp.csv", {}, test_org.id, db)
    job1 = commit_import(preview1.preview_token, test_org.id, test_user.id, db)
    assert job1.status == "completed"

    # Second preview of same invoice number must detect duplicate
    preview2 = preview_import(csv_bytes, "idemp.csv", {}, test_org.id, db)
    assert preview2.duplicate_rows == 1
    assert any("Duplicate" in err.message for err in preview2.errors)

    # Re-committing the identical file is rejected outright and creates nothing
    with pytest.raises(ValueError, match="already imported"):
        commit_import(preview2.preview_token, test_org.id, test_user.id, db)

    count = db.query(Invoice).filter(
        Invoice.org_id == test_org.id,
        Invoice.invoice_number == "INV-IDEMP-01",
    ).count()
    assert count == 1  # exactly 1 record, never duplicated
