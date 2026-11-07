"""Reminder drafting, preview, approval, and dispatch endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.models.follow_up import FollowUp, FollowUpStatus
from app.models.organization import Organization
from app.schemas.analytics import ReminderDraftRequest, ReminderDraftResponse
from app.services.reminder_service import draft_reminder

router = APIRouter()


@router.post("/draft", response_model=ReminderDraftResponse)
def create_reminder_draft(
    payload: ReminderDraftRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = db.get(Organization, current_user.org_id)
    org_name = org.name if org else "Udhaar Ledger Merchant"

    try:
        return draft_reminder(
            db=db,
            follow_up_id=payload.follow_up_id,
            channel=payload.channel,
            language=payload.language,
            org_id=str(current_user.org_id),
            org_name=org_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/approve/{follow_up_id}")
def approve_reminder(
    follow_up_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    fu = db.query(FollowUp).filter(
        FollowUp.id == follow_up_id,
        FollowUp.org_id == current_user.org_id,
    ).first()
    if not fu:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    fu.reminder_approved = True
    fu.status = FollowUpStatus.contacted.value
    db.commit()
    return {"status": "approved", "follow_up_id": str(fu.id)}
