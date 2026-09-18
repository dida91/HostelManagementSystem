from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey
from app.models.enums import StudentStatus, UserRole

if TYPE_CHECKING:
    from app.models.hostel import BedAssignment


class User(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    student: Mapped[Student | None] = relationship(back_populates="user", uselist=False)

    __table_args__ = (Index("ix_users_role_active", "role", "is_active"),)


class RefreshToken(UUIDPrimaryKey, Timestamps, Base):
    """Refresh tokens are stored hashed and rotate on every use."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set when this token was replaced, enabling reuse detection.
    replaced_by_jti: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(INET)


class Student(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "students"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    student_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    college: Mapped[str | None] = mapped_column(String(160))
    program: Mapped[str | None] = mapped_column(String(160))
    guardian_name: Mapped[str | None] = mapped_column(String(160))
    guardian_phone: Mapped[str | None] = mapped_column(String(32))
    guardian_relation: Mapped[str | None] = mapped_column(String(64))
    emergency_contact: Mapped[str | None] = mapped_column(String(32))
    permanent_address: Mapped[str | None] = mapped_column(Text)
    admission_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[StudentStatus] = mapped_column(
        Enum(StudentStatus, name="student_status"), default=StudentStatus.ACTIVE, nullable=False
    )

    user: Mapped[User] = relationship(back_populates="student")
    assignments: Mapped[list[BedAssignment]] = relationship(
        back_populates="student", order_by="BedAssignment.from_date.desc()"
    )

    __table_args__ = (Index("ix_students_status", "status"),)


class AuditLog(UUIDPrimaryKey, Base):
    """Append-only record of privileged mutations, including AI overrides."""

    __tablename__ = "audit_logs"

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    request_id: Mapped[str | None] = mapped_column(String(64))
    ip_address: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_created", "created_at"),
    )
