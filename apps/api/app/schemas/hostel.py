from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import (
    AssignmentStatus,
    BedStatus,
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
    # Who asked: staff need this to decide. Students only ever see their own.
    student_code: str | None = None
    student_name: str | None = None
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


class MenuUpsert(BaseModel):
    items: str = Field(min_length=1, max_length=1000)
    serving_time: str | None = Field(default=None, max_length=40)


# --- blocks / rooms / beds / allocation ---
class BlockCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    floors: int = Field(default=1, ge=1, le=50)


class BlockUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    floors: int | None = Field(default=None, ge=1, le=50)


class BlockOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None
    floors: int
    room_count: int = 0


class RoomOut(ORMModel):
    id: uuid.UUID
    block_id: uuid.UUID
    block_name: str | None = None
    floor: int
    room_number: str
    capacity: int
    room_type: RoomType
    status: RoomStatus
    monthly_rate_npr: int | None
    bed_count: int = 0
    occupied: int = 0


class RoomCreate(BaseModel):
    block_id: uuid.UUID
    floor: int = Field(ge=0, le=50)
    room_number: str = Field(min_length=1, max_length=20)
    room_type: RoomType
    capacity: int = Field(ge=1, le=12, description="Number of beds; beds A, B, C... are created.")
    monthly_rate_npr: int | None = Field(default=None, ge=0, le=1_000_000)
    status: RoomStatus = RoomStatus.AVAILABLE


class RoomUpdate(BaseModel):
    floor: int | None = Field(default=None, ge=0, le=50)
    room_number: str | None = Field(default=None, min_length=1, max_length=20)
    room_type: RoomType | None = None
    capacity: int | None = Field(default=None, ge=1, le=12)
    monthly_rate_npr: int | None = Field(default=None, ge=0, le=1_000_000)
    status: RoomStatus | None = None


class BedOccupantOut(BaseModel):
    assignment_id: uuid.UUID
    student_id: uuid.UUID
    student_code: str
    full_name: str
    from_date: date


class BedOut(BaseModel):
    id: uuid.UUID
    bed_label: str
    status: BedStatus
    occupant: BedOccupantOut | None = None


class RoomDetailOut(RoomOut):
    beds: list[BedOut] = []


class BedUpdate(BaseModel):
    status: BedStatus


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
Audience = Literal["ALL", "STUDENTS", "STAFF"]


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=3, max_length=10_000)
    audience: Audience = "ALL"
    publish_at: datetime | None = None
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _window(self) -> AnnouncementCreate:
        if self.publish_at and self.expires_at and self.expires_at <= self.publish_at:
            raise ValueError("expires_at must be after publish_at")
        return self


class AnnouncementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    body: str | None = Field(default=None, min_length=3, max_length=10_000)
    audience: Audience | None = None
    publish_at: datetime | None = None
    expires_at: datetime | None = None


class AnnouncementOut(ORMModel):
    id: uuid.UUID
    title: str
    body: str
    audience: str
    publish_at: datetime
    expires_at: datetime | None
    notified_at: datetime | None = None
    created_at: datetime
