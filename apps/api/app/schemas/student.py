from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.models.enums import StudentStatus


class StudentCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str
    initial_password: str = Field(min_length=10, max_length=128)
    student_code: str = Field(min_length=2, max_length=32)
    phone: str | None = Field(default=None, max_length=32)
    college: str | None = Field(default=None, max_length=160)
    program: str | None = Field(default=None, max_length=160)
    guardian_name: str | None = Field(default=None, max_length=160)
    guardian_phone: str | None = Field(default=None, max_length=32)
    emergency_contact: str | None = Field(default=None, max_length=32)
    permanent_address: str | None = None
    admission_date: date | None = None
    date_of_birth: date | None = None


class StudentUpdate(BaseModel):
    """Profile edit. Only supplied fields change. Status is changed through
    deactivate/reactivate, which carry the side effects (sign-in, bed)."""

    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    college: str | None = Field(default=None, max_length=160)
    program: str | None = Field(default=None, max_length=160)
    guardian_name: str | None = Field(default=None, max_length=160)
    guardian_phone: str | None = Field(default=None, max_length=32)
    guardian_relation: str | None = Field(default=None, max_length=64)
    emergency_contact: str | None = Field(default=None, max_length=32)
    permanent_address: str | None = Field(default=None, max_length=2000)
    admission_date: date | None = None
    date_of_birth: date | None = None


class StudentDeactivate(BaseModel):
    status: StudentStatus
    reason: str = Field(min_length=3, max_length=500)
    # Ignored for ALUMNI, whose bed is always vacated.
    vacate_bed: bool = True
    leaving_date: date | None = None

    @field_validator("status")
    @classmethod
    def _deactivated_status(cls, v: StudentStatus) -> StudentStatus:
        if v not in {StudentStatus.ALUMNI, StudentStatus.SUSPENDED}:
            raise ValueError("status must be ALUMNI or SUSPENDED")
        return v


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=10, max_length=128)


class StudentOut(BaseModel):
    id: uuid.UUID
    student_code: str
    full_name: str
    email: str
    phone: str | None = None
    college: str | None = None
    program: str | None = None
    status: StudentStatus
    is_active: bool = True
    guardian_name: str | None = None
    guardian_phone: str | None = None
    guardian_relation: str | None = None
    emergency_contact: str | None = None
    permanent_address: str | None = None
    admission_date: date | None = None
    date_of_birth: date | None = None
    room: str | None = None


class DeactivationOut(BaseModel):
    student: StudentOut
    ended_assignment_id: uuid.UUID | None = None
