"""Mess menu and feedback.

The student's original rating and comment are never replaced by AI output;
derived analysis lives in a separate table.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey
from app.models.enums import AIErrorCategory, AIOperationStatus, MealType, Sentiment


class MessMenu(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "mess_menus"

    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Sunday
    meal_type: Mapped[MealType] = mapped_column(Enum(MealType, name="meal_type"), nullable=False)
    items: Mapped[str] = mapped_column(Text, nullable=False)
    serving_time: Mapped[str | None] = mapped_column(String(40))

    __table_args__ = (
        UniqueConstraint("day_of_week", "meal_type", name="uq_menu_day_meal"),
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_menu_dow_range"),
    )


class MessFeedback(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "mess_feedback"

    student_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    meal_date: Mapped[date] = mapped_column(Date, nullable=False)
    meal_type: Mapped[MealType] = mapped_column(Enum(MealType, name="meal_type"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    analysis: Mapped[MessFeedbackAI | None] = relationship(
        back_populates="feedback", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("student_id", "meal_date", "meal_type", name="uq_feedback_per_meal"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating_range"),
        Index("ix_feedback_date_meal", "meal_date", "meal_type"),
    )


class MessFeedbackAI(UUIDPrimaryKey, Base):
    __tablename__ = "mess_feedback_ai"

    feedback_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("mess_feedback.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    status: Mapped[AIOperationStatus] = mapped_column(
        Enum(AIOperationStatus, name="ai_operation_status"), nullable=False
    )
    error_category: Mapped[AIErrorCategory | None] = mapped_column(
        Enum(AIErrorCategory, name="ai_error_category")
    )
    sentiment: Mapped[Sentiment | None] = mapped_column(Enum(Sentiment, name="sentiment"))
    topics: Mapped[list | None] = mapped_column(JSONB)
    issues: Mapped[list | None] = mapped_column(JSONB)
    summary: Mapped[str | None] = mapped_column(Text)

    provider: Mapped[str] = mapped_column(String(32), default="gemini", nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    feedback: Mapped[MessFeedback] = relationship(back_populates="analysis")


class Announcement(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "announcements"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str] = mapped_column(String(20), default="ALL", nullable=False)
    publish_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (Index("ix_announcements_window", "publish_at", "expires_at"),)
