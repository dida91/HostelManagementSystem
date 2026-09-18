from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    AssignmentStatus,
    LeaveStatus,
    LeaveType,
    MealType,
    RoomStatus,
    RoomType,
    Sentiment,
)
from app.schemas.common import ORMModel


# --- leave ---
class LeaveCreate(BaseModel):
    leave_type: LeaveType
    from_date: date
    to_date: date
    reason: str = Field(min_length=5, max_length=2000)
    destination: str | None = Field(default=None, max_length=200)
    guardian_consent: bool = False


class LeaveDecision(BaseModel):
    status: LeaveStatus
    decision_note: str | None = Field(default=None, max_length=1000)


class LeaveOut(ORMModel):
    id: uuid.UUID
    student_id: uuid.UUID
    leave_type: LeaveType
    from_date: date
    to_date: date
    reason: str
    destination: str | None
    status: LeaveStatus
    guardian_consent: bool
    decided_at: datetime | None
    decision_note: str | None
    created_at: datetime


# --- mess ---
class MessFeedbackCreate(BaseModel):
    meal_date: date
    meal_type: MealType
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class MessFeedbackAIOut(ORMModel):
    sentiment: Sentiment | None
    topics: list[str] | None
    issues: list[str] | None
    summary: str | None
    model: str


class MessFeedbackOut(ORMModel):
    id: uuid.UUID
    meal_date: date
    meal_type: MealType
    rating: int
    comment: str | None
    created_at: datetime
    analysis: MessFeedbackAIOut | None = None


class MenuOut(ORMModel):
    day_of_week: int
    meal_type: MealType
    items: str
    serving_time: str | None


# --- rooms / allocation ---
class RoomOut(ORMModel):
    id: uuid.UUID
    floor: int
    room_number: str
    capacity: int
    room_type: RoomType
    status: RoomStatus
    monthly_rate_npr: int | None
    occupied: int = 0


class AllocationCreate(BaseModel):
    student_id: uuid.UUID
    bed_id: uuid.UUID
    from_date: date


class AssignmentOut(ORMModel):
    id: uuid.UUID
    student_id: uuid.UUID
    bed_id: uuid.UUID
    from_date: date
    to_date: date | None
    status: AssignmentStatus


# --- announcements ---
class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=3)
    audience: str = "ALL"
    publish_at: datetime | None = None
    expires_at: datetime | None = None


class AnnouncementOut(ORMModel):
    id: uuid.UUID
    title: str
    body: str
    audience: str
    publish_at: datetime
    expires_at: datetime | None
