from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db, get_org_id
from app.models.import_job import ImportJob
from app.models.user import User
from app.schemas.import_job import ImportCommitRequest, ImportJobListResponse, ImportJobResponse, ImportPreviewResponse
from app.services.import_service import commit_import, preview_import

router = APIRouter()


@router.post("/preview", response_model=ImportPreviewResponse)
async def preview_import_route(
    file: UploadFile = File(...),
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    # Check file size
    content = await file.read()
    max_bytes = settings.UPLOAD_MAX_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum {settings.UPLOAD_MAX_MB}MB")

    filename = file.filename or "upload.csv"
    if not filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only CSV and XLSX files are supported")

    try:
        result = preview_import(content, filename, {}, UUID(org_id), db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/commit", response_model=ImportJobResponse)
def commit_import_route(
    body: ImportCommitRequest,
    org_id: str = Depends(get_org_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        job = commit_import(body.preview_token, UUID(org_id), current_user.id, db)
        return job
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/jobs", response_model=ImportJobListResponse)
def list_import_jobs(
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    jobs = (
        db.query(ImportJob)
        .filter(ImportJob.org_id == UUID(org_id))
        .order_by(ImportJob.created_at.desc())
        .limit(50)
        .all()
    )
    return ImportJobListResponse(items=jobs, total=len(jobs))
