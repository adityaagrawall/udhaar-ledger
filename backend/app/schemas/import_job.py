from datetime import date
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel


class ImportPreviewRequest(BaseModel):
    mapping_config: dict[str, str] = {}  # our_field -> csv_column


class ImportRowError(BaseModel):
    row_index: int
    field: Optional[str] = None
    message: str
    row_data: Optional[dict] = None


class ImportPreviewResponse(BaseModel):
    preview_token: str
    filename: str
    total_rows: int
    valid_rows: int
    error_rows: int
    duplicate_rows: int
    errors: list[ImportRowError]
    sample_data: list[dict]  # First 10 valid rows
    column_mapping: dict[str, str]


class ImportCommitRequest(BaseModel):
    preview_token: str


class ImportJobResponse(BaseModel):
    id: UUID
    filename: str
    status: str
    total_rows: int
    valid_rows: int
    error_rows: int
    skipped_rows: int
    errors: Optional[list] = None
    created_at: Any

    model_config = {"from_attributes": True}


class ImportJobListResponse(BaseModel):
    items: list[ImportJobResponse]
    total: int
