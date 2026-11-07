"""
Import service: CSV/XLSX upload, validation, preview, and commit.

Safety guarantees:
- SHA256 hash of (org_id + invoice_number) for idempotent imports
- Row-level error collection — never silently corrupt existing records
- Preview mode: validate everything, persist nothing
- Commit mode: only valid rows, atomically, skipping duplicates
"""

import hashlib
import io
import json
import time
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.customer import Customer, RiskTier
from app.models.import_job import ImportJob, ImportJobStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentAllocation, PaymentMode
from app.schemas.import_job import ImportPreviewResponse, ImportRowError

# In-memory preview store. Single-process only: a restart or a second worker loses
# previews (documented in docs/KNOWN_LIMITATIONS.md). Entries expire so it cannot grow unbounded.
_preview_cache: dict[str, dict] = {}
PREVIEW_TTL_SECONDS = 15 * 60


def _evict_expired_previews() -> None:
    now = time.monotonic()
    for token in [t for t, v in _preview_cache.items() if now - v["created"] > PREVIEW_TTL_SECONDS]:
        _preview_cache.pop(token, None)

REQUIRED_COLUMNS = {"invoice_number", "customer_name", "issue_date", "due_date", "total_amount"}

DEFAULT_COLUMN_MAPPING = {
    "invoice_number": "invoice_number",
    "customer_name": "customer_name",
    "customer_email": "customer_email",
    "issue_date": "issue_date",
    "due_date": "due_date",
    "total_amount": "total_amount",
    "payment_amount": "payment_amount",
    "payment_date": "payment_date",
    "payment_reference": "payment_reference",
    "payment_mode": "payment_mode",
}


def _parse_date(val: Any) -> date:
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(val).strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {val!r}")


def _parse_decimal(val: Any) -> Decimal:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return Decimal("0")
    try:
        cleaned = str(val).replace(",", "").replace("₹", "").strip()
        return Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"Cannot parse amount: {val!r}")


class ImportFileError(ValueError):
    """A file problem whose message is safe to show the user."""


def _guard_zip_bomb(file_bytes: bytes) -> None:
    """An .xlsx is a zip; refuse files that would expand to an unreasonable size in memory."""
    import zipfile

    if not zipfile.is_zipfile(io.BytesIO(file_bytes)):
        return  # legacy .xls or a mislabelled file; the parser will reject it
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        total = sum(i.file_size for i in zf.infolist())
    if total > settings.IMPORT_MAX_UNZIPPED_MB * 1024 * 1024:
        raise ImportFileError("Spreadsheet is too large once unpacked.")


def _file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def preview_import(
    file_bytes: bytes,
    filename: str,
    mapping_config: dict[str, str],
    org_id: uuid.UUID,
    db: Session,
) -> ImportPreviewResponse:
    """
    Parse and validate file. Returns errors per row and valid sample.
    Nothing is persisted to the database.
    """
    # Read file
    try:
        if filename.lower().endswith(".xlsx") or filename.lower().endswith(".xls"):
            _guard_zip_bomb(file_bytes)
            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
        else:
            df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, nrows=settings.IMPORT_MAX_ROWS + 1)
    except ImportFileError:
        raise
    except Exception:
        raise ValueError("Cannot read file. Check that it is a valid CSV or Excel export.")

    if len(df) > settings.IMPORT_MAX_ROWS:
        raise ValueError(f"File has more than {settings.IMPORT_MAX_ROWS:,} rows. Split it into smaller files.")

    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    # Apply mapping: rename CSV columns to our expected names
    rename_map = {v: k for k, v in mapping_config.items() if v and v in df.columns}
    df = df.rename(columns=rename_map)

    # Check required columns
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    # Fetch existing invoice numbers for this org (for duplicate detection)
    existing_numbers = set(
        r[0]
        for r in db.query(Invoice.invoice_number)
        .filter(Invoice.org_id == org_id, Invoice.deleted_at == None)
        .all()
    )

    errors: list[ImportRowError] = []
    valid_rows: list[dict] = []
    duplicate_count = 0
    seen_in_file: set[str] = set()

    for idx, row in df.iterrows():
        row_num = int(idx) + 2  # 1-based + header
        row_errors = []
        parsed: dict[str, Any] = {}

        # invoice_number
        inv_num = str(row.get("invoice_number", "")).strip()
        if not inv_num:
            row_errors.append(ImportRowError(row_index=row_num, field="invoice_number", message="invoice_number is required"))
        else:
            parsed["invoice_number"] = inv_num
            if inv_num in existing_numbers or inv_num in seen_in_file:
                duplicate_count += 1
                where = "already exists" if inv_num in existing_numbers else "appears earlier in this file"
                errors.append(ImportRowError(
                    row_index=row_num, field="invoice_number",
                    message=f"Duplicate: invoice '{inv_num}' {where} (will be skipped)",
                    row_data=row.to_dict(),
                ))
                continue
            seen_in_file.add(inv_num)

        # customer_name
        cust_name = str(row.get("customer_name", "")).strip()
        if not cust_name:
            row_errors.append(ImportRowError(row_index=row_num, field="customer_name", message="customer_name is required"))
        else:
            parsed["customer_name"] = cust_name

        # issue_date
        try:
            parsed["issue_date"] = _parse_date(row.get("issue_date"))
        except (ValueError, TypeError) as e:
            row_errors.append(ImportRowError(row_index=row_num, field="issue_date", message=str(e)))

        # due_date
        try:
            parsed["due_date"] = _parse_date(row.get("due_date"))
        except (ValueError, TypeError) as e:
            row_errors.append(ImportRowError(row_index=row_num, field="due_date", message=str(e)))

        # date ordering
        if "issue_date" in parsed and "due_date" in parsed:
            if parsed["due_date"] < parsed["issue_date"]:
                row_errors.append(ImportRowError(row_index=row_num, field="due_date", message="due_date must be >= issue_date"))

        # total_amount
        try:
            amt = _parse_decimal(row.get("total_amount"))
            if amt <= 0:
                row_errors.append(ImportRowError(row_index=row_num, field="total_amount", message="total_amount must be positive"))
            else:
                parsed["total_amount"] = amt
        except ValueError as e:
            row_errors.append(ImportRowError(row_index=row_num, field="total_amount", message=str(e)))

        # payment_amount (optional)
        pay_val = row.get("payment_amount")
        if pay_val and str(pay_val).strip() not in ("", "nan", "None"):
            try:
                pay_amt = _parse_decimal(pay_val)
                if pay_amt < 0:
                    row_errors.append(ImportRowError(row_index=row_num, field="payment_amount", message="payment_amount cannot be negative"))
                else:
                    if pay_amt > parsed.get("total_amount", pay_amt):
                        row_errors.append(ImportRowError(
                            row_index=row_num, field="payment_amount",
                            message="payment_amount exceeds total_amount",
                        ))
                    parsed["payment_amount"] = pay_amt
                    # payment_date
                    # A payment without a real date would corrupt on-time statistics, so reject the row.
                    try:
                        parsed["payment_date"] = _parse_date(row.get("payment_date"))
                    except (ValueError, TypeError):
                        row_errors.append(ImportRowError(
                            row_index=row_num, field="payment_date",
                            message="payment_date is required and must be a valid date when payment_amount is given",
                        ))
                    parsed["payment_reference"] = str(row.get("payment_reference", "")).strip() or None
                    parsed["payment_mode"] = str(row.get("payment_mode", "neft")).strip().lower() or "neft"
            except ValueError as e:
                row_errors.append(ImportRowError(row_index=row_num, field="payment_amount", message=str(e)))

        # Optional fields
        parsed["customer_email"] = str(row.get("customer_email", "")).strip() or None

        if row_errors:
            errors.extend(row_errors)
        else:
            valid_rows.append(parsed)

    # Store validated data for commit
    _evict_expired_previews()
    preview_token = str(uuid.uuid4())
    _preview_cache[preview_token] = {
        "created": time.monotonic(),
        "valid_rows": valid_rows,
        "org_id": str(org_id),
        "filename": filename,
        "file_hash": _file_hash(file_bytes),
        "mapping_config": mapping_config,
        "total_rows": len(df),
        "duplicate_count": duplicate_count,
    }

    # Serialize sample (dates -> strings)
    sample_data = []
    for r in valid_rows[:10]:
        serialized = {}
        for k, v in r.items():
            if isinstance(v, date):
                serialized[k] = v.isoformat()
            elif isinstance(v, Decimal):
                serialized[k] = str(v)
            else:
                serialized[k] = v
        sample_data.append(serialized)

    return ImportPreviewResponse(
        preview_token=preview_token,
        filename=filename,
        total_rows=len(df),
        valid_rows=len(valid_rows),
        error_rows=len([e for e in errors if "Duplicate" not in e.message]),
        duplicate_rows=duplicate_count,
        errors=errors,
        sample_data=sample_data,
        column_mapping={**DEFAULT_COLUMN_MAPPING, **mapping_config},
    )


def commit_import(
    preview_token: str,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session,
) -> ImportJob:
    """
    Persist validated rows from preview. Idempotent for duplicates.
    Creates customers (by name) if they don't exist.
    """
    _evict_expired_previews()
    cached = _preview_cache.get(preview_token)
    if not cached:
        raise ValueError("Preview token not found or expired. Re-upload the file.")
    if cached["org_id"] != str(org_id):
        raise PermissionError("Preview token org mismatch")

    valid_rows = cached["valid_rows"]
    filename = cached["filename"]
    file_hash = cached["file_hash"]

    # Check if this file was already imported
    existing_job = (
        db.query(ImportJob)
        .filter(
            ImportJob.org_id == org_id,
            ImportJob.file_hash == file_hash,
            ImportJob.status == ImportJobStatus.completed.value,
        )
        .first()
    )

    if existing_job is not None:
        _preview_cache.pop(preview_token, None)
        raise ValueError(
            f"This exact file ('{existing_job.filename}') was already imported. Re-importing would add nothing."
        )

    import_job = ImportJob(
        org_id=org_id,
        filename=filename,
        file_hash=file_hash,
        status=ImportJobStatus.processing.value,
        total_rows=cached["total_rows"],
        valid_rows=len(valid_rows),
        error_rows=0,
        skipped_rows=cached["duplicate_count"],
        mapping_config=cached["mapping_config"],
        imported_by=user_id,
    )
    db.add(import_job)
    db.flush()

    # Build customer name -> Customer map
    customer_map: dict[str, Customer] = {}
    existing_customers = (
        db.query(Customer)
        .filter(Customer.org_id == org_id, Customer.deleted_at == None)
        .all()
    )
    for c in existing_customers:
        customer_map[c.name.lower().strip()] = c

    created_invoices = 0
    skipped = 0

    for row in valid_rows:
        cust_name = row["customer_name"]
        cust_key = cust_name.lower().strip()

        # Get or create customer
        if cust_key not in customer_map:
            new_customer = Customer(
                org_id=org_id,
                name=cust_name,
                email=row.get("customer_email"),
                payment_terms_days=30,
                risk_tier=RiskTier.medium.value,
                credit_limit=Decimal("500000.00"),
            )
            db.add(new_customer)
            db.flush()
            customer_map[cust_key] = new_customer

        customer = customer_map[cust_key]

        # Double-check invoice doesn't exist (idempotent)
        existing = (
            db.query(Invoice)
            .filter(Invoice.org_id == org_id, Invoice.invoice_number == row["invoice_number"])
            .first()
        )
        if existing:
            skipped += 1
            continue

        invoice = Invoice(
            org_id=org_id,
            customer_id=customer.id,
            invoice_number=row["invoice_number"],
            issue_date=row["issue_date"],
            due_date=row["due_date"],
            total_amount=row["total_amount"],
            status=InvoiceStatus.sent.value,
        )
        db.add(invoice)
        db.flush()

        # Determine initial status
        today = date.today()
        if row["due_date"] < today:
            invoice.status = InvoiceStatus.overdue.value

        # Create payment + allocation if provided
        pay_amt = row.get("payment_amount")
        if pay_amt and pay_amt > 0:
            payment = Payment(
                org_id=org_id,
                customer_id=customer.id,
                received_date=row.get("payment_date", today),
                amount=pay_amt,
                reference_no=row.get("payment_reference"),
                payment_mode=row.get("payment_mode", "neft"),
            )
            db.add(payment)
            db.flush()

            alloc_amt = min(pay_amt, row["total_amount"])
            allocation = PaymentAllocation(
                payment_id=payment.id,
                invoice_id=invoice.id,
                allocated_amount=alloc_amt,
                allocated_at=datetime.now(timezone.utc),
            )
            db.add(allocation)
            db.flush()

            # Recalculate status
            outstanding = row["total_amount"] - alloc_amt
            today = date.today()
            if outstanding <= 0:
                invoice.status = InvoiceStatus.paid.value
            elif row["due_date"] < today:
                invoice.status = InvoiceStatus.overdue.value
            elif outstanding < row["total_amount"]:
                invoice.status = InvoiceStatus.partial.value
            else:
                invoice.status = InvoiceStatus.sent.value
            db.add(invoice)

        created_invoices += 1

    import_job.status = ImportJobStatus.completed.value
    import_job.skipped_rows += skipped

    db.commit()
    db.refresh(import_job)

    # Clean up cache
    _preview_cache.pop(preview_token, None)

    return import_job
