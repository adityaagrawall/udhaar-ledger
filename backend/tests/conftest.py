"""Pytest fixtures for Udhaar Ledger tests."""
import os

# Tests mint local HS256 tokens; production accepts Clerk tokens only.
os.environ["ALLOW_LOCAL_JWT"] = "true"
os.environ["DEMO_ENABLED"] = "false"
import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password, create_access_token
from app.models.base import Base
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.models.customer import Customer, RiskTier
from app.models.invoice import Invoice, InvoiceStatus
from app.main import app

TEST_DB_URL = "postgresql+psycopg2://collectiq:collectiq@localhost:5432/collectiq_test"
test_engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db():
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def test_org(db: Session) -> Organization:
    org = Organization(
        name="Test Organics Ltd",
        slug=f"test-org-{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db.add(org)
    db.flush()
    return org


@pytest.fixture
def other_org(db: Session) -> Organization:
    org = Organization(
        name="Other Corp Ltd",
        slug=f"other-org-{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db.add(org)
    db.flush()
    return org


@pytest.fixture
def test_user(db: Session, test_org: Organization) -> User:
    user = User(
        org_id=test_org.id,
        email="testadmin@collectiq.com",
        hashed_password=hash_password("test-only-password"),
        full_name="Test Admin",
        role=UserRole.admin.value,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def test_customer(db: Session, test_org: Organization) -> Customer:
    cust = Customer(
        org_id=test_org.id,
        name="Agrawal Traders",
        email="agrawal@example.com",
        phone="+919876543210",
        credit_limit=Decimal("500000.00"),
        payment_terms_days=30,
        risk_tier=RiskTier.low.value,
        is_active=True,
    )
    db.add(cust)
    db.flush()
    return cust


@pytest.fixture
def client(db: Session, test_user: User):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    token = create_access_token({
        "sub": str(test_user.id),
        "org_id": str(test_user.org_id),
        "role": test_user.role,
    })
    return {"Authorization": f"Bearer {token}"}
