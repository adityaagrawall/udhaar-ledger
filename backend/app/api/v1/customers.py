"""Customer CRUD endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user, require_role
from app.schemas.customer import CustomerCreate, CustomerUpdate, CustomerOut, CustomerListResponse
import app.services.customer_service as svc

router = APIRouter()


@router.get("", response_model=CustomerListResponse)
def list_customers(
    search: str | None = Query(None),
    risk_tier: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.list_customers(current_user.org_id, db, search, risk_tier, page, page_size)


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(
    payload: CustomerCreate,
    current_user=Depends(require_role(["admin", "manager"])),
    db: Session = Depends(get_db),
):
    return svc.create_customer(payload, current_user.org_id, db)


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.get_customer(customer_id, current_user.org_id, db)


@router.get("/{customer_id}/ledger", response_model=svc.CustomerLedgerResponse)
def get_customer_ledger(
    customer_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.get_customer_ledger(customer_id, current_user.org_id, db)


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: UUID,
    payload: CustomerUpdate,
    current_user=Depends(require_role(["admin", "manager"])),
    db: Session = Depends(get_db),
):
    return svc.update_customer(customer_id, current_user.org_id, payload, db)


@router.delete("/{customer_id}", status_code=204)
def delete_customer(
    customer_id: UUID,
    current_user=Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    svc.delete_customer(customer_id, current_user.org_id, db)
