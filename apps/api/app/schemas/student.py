from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, Field

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


class StudentOut(BaseModel):
    id: uuid.UUID
    student_code: str
    full_name: str
    email: str
    phone: str | None = None
    college: str | None = None
    program: str | None = None
    status: StudentStatus
    guardian_name: str | None = None
    guardian_phone: str | None = None
    admission_date: date | None = None
