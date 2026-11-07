import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ImportJobStatus(str, PyEnum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ImportJob(Base, TimestampMixin):
    __tablename__ = "import_jobs"
    __table_args__ = (
        Index("ix_import_jobs_org", "org_id"),
        Index("ix_import_jobs_file_hash", "org_id", "file_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256 hex
    status: Mapped[str] = mapped_column(
        Enum(ImportJobStatus, name="import_job_status"),
        default=ImportJobStatus.pending,
        nullable=False,
    )
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    mapping_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    imported_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Relationships
    uploader = relationship("User", foreign_keys=[imported_by])
