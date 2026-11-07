import uuid
from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import Boolean, ForeignKey, String, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class UserRole(str, PyEnum):
    admin = "admin"
    manager = "manager"
    viewer = "viewer"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Users who sign in through Clerk get an unusable random hash here.
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    clerk_user_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.viewer, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="users")
