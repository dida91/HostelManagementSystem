from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey
from app.models.enums import LeaveStatus, LeaveType


class LeaveRequest(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "leave_requests"

    student_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    leave_type: Mapped[LeaveType] = mapped_column(
        Enum(LeaveType, name="leave_type"), nullable=False
    )
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    destination: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[LeaveStatus] = mapped_column(
        Enum(LeaveStatus, name="leave_status"), default=LeaveStatus.PENDING, nullable=False
    )
    guardian_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approver_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)

    documents: Mapped[list[LeaveDocument]] = relationship(
        back_populates="leave_request", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_leave_student_status", "student_id", "status"),
        Index("ix_leave_dates", "from_date", "to_date"),
    )


class LeaveDocument(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "leave_documents"

    leave_request_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("leave_requests.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)

    leave_request: Mapped[LeaveRequest] = relationship(back_populates="documents")
