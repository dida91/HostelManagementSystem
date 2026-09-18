"""Complaints and their AI analyses.

Separation of concerns that matters here:
  * `complaints` holds the IMMUTABLE original text plus the EFFECTIVE
    (admin-owned) triage fields.
  * `complaint_ai_analyses` holds what the model proposed, never mutated.

Keeping both means an admin override never destroys the model's prediction, so
model-vs-human disagreement remains measurable for evaluation.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey
from app.models.enums import (
    AIErrorCategory,
    AIOperationStatus,
    ComplaintCategory,
    ComplaintPriority,
    ComplaintStatus,
    Department,
    Sentiment,
)


class Complaint(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "complaints"

    student_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Never modified after creation -- the student's own words.
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="WEB", nullable=False)

    status: Mapped[ComplaintStatus] = mapped_column(
        Enum(ComplaintStatus, name="complaint_status"),
        default=ComplaintStatus.SUBMITTED,
        nullable=False,
    )
    # Effective triage values. Seeded from AI, authoritative once an admin edits.
    category: Mapped[ComplaintCategory | None] = mapped_column(
        Enum(ComplaintCategory, name="complaint_category")
    )
    priority: Mapped[ComplaintPriority | None] = mapped_column(
        Enum(ComplaintPriority, name="complaint_priority")
    )
    department: Mapped[Department | None] = mapped_column(Enum(Department, name="department"))
    location: Mapped[str | None] = mapped_column(String(120))
    summary: Mapped[str | None] = mapped_column(Text)

    # Field names an admin has explicitly overridden, e.g. ["priority"].
    overridden_fields: Mapped[list | None] = mapped_column(JSONB)
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)

    analyses: Mapped[list[ComplaintAIAnalysis]] = relationship(
        back_populates="complaint", order_by="ComplaintAIAnalysis.created_at.desc()"
    )
    events: Mapped[list[ComplaintEvent]] = relationship(back_populates="complaint")

    __table_args__ = (
        Index("ix_complaints_status_priority", "status", "priority"),
        Index("ix_complaints_created", "created_at"),
    )


class ComplaintAIAnalysis(UUIDPrimaryKey, Base):
    """One row per analysis attempt, successful or not."""

    __tablename__ = "complaint_ai_analyses"

    complaint_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[AIOperationStatus] = mapped_column(
        Enum(AIOperationStatus, name="ai_operation_status"), nullable=False
    )
    error_category: Mapped[AIErrorCategory | None] = mapped_column(
        Enum(AIErrorCategory, name="ai_error_category")
    )

    # What the model proposed.
    category: Mapped[ComplaintCategory | None] = mapped_column(
        Enum(ComplaintCategory, name="complaint_category")
    )
    priority: Mapped[ComplaintPriority | None] = mapped_column(
        Enum(ComplaintPriority, name="complaint_priority")
    )
    sentiment: Mapped[Sentiment | None] = mapped_column(Enum(Sentiment, name="sentiment"))
    location: Mapped[str | None] = mapped_column(String(120))
    summary: Mapped[str | None] = mapped_column(Text)
    suggested_department: Mapped[Department | None] = mapped_column(
        Enum(Department, name="department")
    )
    confidence: Mapped[float | None] = mapped_column(Float)

    # Provenance -- required to reproduce or re-evaluate any past decision.
    provider: Mapped[str] = mapped_column(String(32), default="gemini", nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    raw_response: Mapped[dict | None] = mapped_column(JSONB)

    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    complaint: Mapped[Complaint] = relationship(back_populates="analyses")

    __table_args__ = (Index("ix_analyses_model_version", "model", "prompt_version"),)


class ComplaintEvent(UUIDPrimaryKey, Base):
    """Status transition trail."""

    __tablename__ = "complaint_events"

    complaint_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    from_status: Mapped[ComplaintStatus | None] = mapped_column(
        Enum(ComplaintStatus, name="complaint_status")
    )
    to_status: Mapped[ComplaintStatus] = mapped_column(
        Enum(ComplaintStatus, name="complaint_status"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    complaint: Mapped[Complaint] = relationship(back_populates="events")
