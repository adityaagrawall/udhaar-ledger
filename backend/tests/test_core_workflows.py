"""
Core workflow tests for Udhaar Ledger Phase 2:
- FIFO Payment allocation suggestions
- Payment recording with unallocated advance tracking
- UTR reference number deduplication (HTTP 409)
- Promise-to-Pay (PTP) tracking, broken detection, and fulfillment
- Customer 360 Statement of Account (SOA) ledger
- Distributor Business Intelligence KPIs (DSO, CEI, Aging, Inflow projections)
"""

from datetime import date, timedelta
from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient

from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.follow_up import FollowUp, FollowUpStatus


def test_fifo_allocation_suggestion(client: TestClient, db, auth_headers, test_org, test_customer):
    today = date.today()

    # Create 3 invoices with different due dates
    inv1 = Invoice(
        org_id=test_org.id,
        customer_id=test_customer.id,
        invoice_number=f"FIFO-{uuid.uuid4().hex[:6]}",
        issue_date=today - timedelta(days=40),
        due_date=today - timedelta(days=20),
        total_amount=Decimal("10000.00"),
        status=InvoiceStatus.overdue,
    )
    inv2 = Invoice(
        org_id=test_org.id,
        customer_id=test_customer.id,
        invoice_number=f"FIFO-{uuid.uuid4().hex[:6]}",
        issue_date=today - timedelta(days=20),
        due_date=today - timedelta(days=5),
        total_amount=Decimal("20000.00"),
        status=InvoiceStatus.overdue,
    )
    inv3 = Invoice(
        org_id=test_org.id,
        customer_id=test_customer.id,
        invoice_number=f"FIFO-{uuid.uuid4().hex[:6]}",
        issue_date=today - timedelta(days=5),
        due_date=today + timedelta(days=15),
        total_amount=Decimal("15000.00"),
        status=InvoiceStatus.sent,
    )
    db.add_all([inv1, inv2, inv3])
    db.flush()

    # Request FIFO allocation suggestion for ₹25,000 (should cover inv1 completely and ₹15,000 of inv2)
    resp = client.get(
        f"/api/v1/payments/suggest-allocation?customer_id={test_customer.id}&amount=25000.00",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["customer_id"] == str(test_customer.id)
    assert Decimal(str(data["total_allocated"])) == Decimal("25000.00")
    assert Decimal(str(data["unallocated_amount"])) == Decimal("0.00")
    assert data["invoices_covered"] == 2

    allocs = data["allocations"]
    assert len(allocs) >= 2
    # First invoice (oldest due date) should be allocated full ₹10,000
    assert allocs[0]["invoice_number"] == inv1.invoice_number
    assert Decimal(str(allocs[0]["suggested_allocated_amount"])) == Decimal("10000.00")

    # Second invoice should be allocated ₹15,000
    assert allocs[1]["invoice_number"] == inv2.invoice_number
    assert Decimal(str(allocs[1]["suggested_allocated_amount"])) == Decimal("15000.00")


def test_utr_duplicate_rejected(client: TestClient, db, auth_headers, test_customer):
    unique_utr = f"UTR-{uuid.uuid4().hex[:8].upper()}"

    # First payment
    payload1 = {
        "customer_id": str(test_customer.id),
        "received_date": date.today().isoformat(),
        "amount": "5000.00",
        "reference_no": unique_utr,
        "payment_mode": "neft",
        "notes": "First payment",
        "allocations": [],
    }
    resp1 = client.post(
        "/api/v1/payments",
        json=payload1,
        headers=auth_headers,
    )
    assert resp1.status_code == 201, resp1.text

    # Duplicate payment with same UTR should be rejected with 409 Conflict
    resp2 = client.post(
        "/api/v1/payments",
        json=payload1,
        headers=auth_headers,
    )
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]


def test_ptp_lifecycle_and_auto_broken(client: TestClient, db, auth_headers, test_org, test_customer):
    today = date.today()

    inv = Invoice(
        org_id=test_org.id,
        customer_id=test_customer.id,
        invoice_number=f"PTP-{uuid.uuid4().hex[:6]}",
        issue_date=today - timedelta(days=30),
        due_date=today - timedelta(days=10),
        total_amount=Decimal("12000.00"),
        status=InvoiceStatus.overdue,
    )
    db.add(inv)
    db.flush()

    # Create follow-up with past promised_date (yesterday)
    yesterday = today - timedelta(days=1)
    fu_payload = {
        "invoice_id": str(inv.id),
        "customer_id": str(test_customer.id),
        "channel": "call",
        "notes": "Retailer promised RTGS by yesterday",
        "promised_date": yesterday.isoformat(),
        "promised_amount": "12000.00",
    }
    fu_resp = client.post(
        "/api/v1/follow-ups",
        json=fu_payload,
        headers=auth_headers,
    )
    assert fu_resp.status_code == 201, fu_resp.text
    fu_data = fu_resp.json()
    assert fu_data["promise_status"] == "pending"
    assert fu_data["status"] == "promised"

    # Trigger PTP sync
    sync_resp = client.post(
        "/api/v1/follow-ups/sync-ptp",
        headers=auth_headers,
    )
    assert sync_resp.status_code == 200

    # Fetch PTP summary
    summary_resp = client.get(
        "/api/v1/follow-ups/ptp-summary",
        headers=auth_headers,
    )
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["broken_count"] >= 1
    assert Decimal(str(summary["broken_amount"])) >= Decimal("12000.00")


def test_ptp_fulfillment_on_payment(client: TestClient, db, auth_headers, test_org, test_customer):
    today = date.today()

    inv = Invoice(
        org_id=test_org.id,
        customer_id=test_customer.id,
        invoice_number=f"PTP-FUL-{uuid.uuid4().hex[:6]}",
        issue_date=today - timedelta(days=20),
        due_date=today - timedelta(days=5),
        total_amount=Decimal("8000.00"),
        status=InvoiceStatus.overdue,
    )
    db.add(inv)
    db.flush()

    # Follow-up with future promise
    tomorrow = today + timedelta(days=1)
    client.post(
        "/api/v1/follow-ups",
        json={
            "invoice_id": str(inv.id),
            "customer_id": str(test_customer.id),
            "channel": "whatsapp",
            "notes": "Retailer promised payment tomorrow",
            "promised_date": tomorrow.isoformat(),
            "promised_amount": "8000.00",
        },
        headers=auth_headers,
    )

    # Pay the invoice in full
    pay_resp = client.post(
        "/api/v1/payments",
        json={
            "customer_id": str(test_customer.id),
            "received_date": today.isoformat(),
            "amount": "8000.00",
            "reference_no": f"FUL-{uuid.uuid4().hex[:6]}",
            "payment_mode": "upi",
            "allocations": [{"invoice_id": str(inv.id), "allocated_amount": "8000.00"}],
        },
        headers=auth_headers,
    )
    assert pay_resp.status_code == 201

    # Verify follow-up promise is fulfilled
    db.expire_all()
    updated_fu = db.query(FollowUp).filter(FollowUp.invoice_id == inv.id).first()
    assert updated_fu.promise_status == "fulfilled"
    assert updated_fu.status == FollowUpStatus.resolved


def test_customer_ledger_statement_of_account(client: TestClient, db, auth_headers, test_customer):
    resp = client.get(
        f"/api/v1/customers/{test_customer.id}/ledger",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    ledger_data = resp.json()

    assert "customer" in ledger_data
    assert "credit_summary" in ledger_data
    assert "aging_summary" in ledger_data
    assert "ledger" in ledger_data
    assert "open_invoices" in ledger_data
    assert "promises" in ledger_data

    summary = ledger_data["credit_summary"]
    assert "credit_limit" in summary
    assert "total_outstanding" in summary
    assert "available_credit" in summary
    assert "utilization_pct" in summary
    assert "health_status" in summary
    assert summary["health_status"] in ["HEALTHY", "MONITOR", "WARNING", "CRITICAL"]


def test_distributor_kpis_endpoint(client: TestClient, db, auth_headers):
    resp = client.get(
        "/api/v1/analytics/distributor-kpis",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    kpis = resp.json()

    assert "total_receivables" in kpis
    assert "overdue_receivables" in kpis
    assert "dso_days" in kpis
    assert "dso_formula" in kpis
    assert "collection_effectiveness_index" in kpis
    assert "ptp_stats" in kpis
    assert "aging_summary" in kpis
    assert "projected_inflows" in kpis
    assert "top_debtors" in kpis
    assert "top_5_debtor_concentration_pct" in kpis
