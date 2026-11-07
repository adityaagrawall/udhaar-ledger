"""Tests for authentication and multi-tenant authorization boundaries."""
from datetime import date
from decimal import Decimal
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.organization import Organization
from app.models.user import User


def test_login_returns_token(client: TestClient, test_user: User):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "test-only-password"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_invalid_password_rejected(client: TestClient, test_user: User):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "WrongPassword!"},
    )
    assert resp.status_code == 401


def test_unauthenticated_request_401(client: TestClient):
    resp = client.get("/api/v1/invoices")
    assert resp.status_code == 401


def test_cross_org_invoice_access_403(
    client: TestClient,
    db: Session,
    other_org: Organization,
    auth_headers: dict,
):
    """A user in Org A cannot access an invoice belonging to Org B."""
    # Create customer & invoice in other_org
    other_cust = Customer(
        org_id=other_org.id,
        name="Other Org Customer",
        is_active=True,
    )
    db.add(other_cust)
    db.flush()

    other_inv = Invoice(
        org_id=other_org.id,
        customer_id=other_cust.id,
        invoice_number="INV-OTHER-999",
        issue_date=date(2024, 1, 1),
        due_date=date(2024, 1, 31),
        total_amount=Decimal("10000.00"),
        status=InvoiceStatus.sent.value,
    )
    db.add(other_inv)
    db.flush()

    # User in test_org requests the other invoice
    resp = client.get(f"/api/v1/invoices/{other_inv.id}", headers=auth_headers)
    # Must return 404 (not found in user's tenant) - never leak cross-tenant existence
    assert resp.status_code == 404
