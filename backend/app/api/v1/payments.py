from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user, require_role
from app.schemas.payment import (
    FifoAllocationSuggestionResponse,
    PaymentCreate,
    PaymentOut,
    PaymentListResponse,
)
import app.services.payment_service as svc

router = APIRouter()


@router.get("/suggest-allocation", response_model=FifoAllocationSuggestionResponse)
def suggest_allocation(
    customer_id: UUID = Query(...),
    amount: Decimal = Query(..., gt=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.suggest_fifo_allocation(customer_id, amount, current_user.org_id, db)


@router.get("", response_model=PaymentListResponse)
def list_payments(
    customer_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.list_payments(current_user.org_id, db, customer_id, page, page_size)


@router.post("", response_model=PaymentOut, status_code=201)
def create_payment(
    payload: PaymentCreate,
    current_user=Depends(require_role(["admin", "manager"])),
    db: Session = Depends(get_db),
):
    return svc.create_payment(payload, current_user.org_id, db)


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(
    payment_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.get_payment(payment_id, current_user.org_id, db)
