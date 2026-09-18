from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    ComplaintCategory,
    ComplaintPriority,
    ComplaintStatus,
    Department,
    Sentiment,
)
from app.schemas.common import ORMModel


class ComplaintCreate(BaseModel):
    text: str = Field(
        min_length=10, max_length=4000, description="The complaint in the student's own words."
    )


class ComplaintAIOut(ORMModel):
    status: str
    category: ComplaintCategory | None = None
    priority: ComplaintPriority | None = None
    sentiment: Sentiment | None = None
    location: str | None = None
    summary: str | None = None
    suggested_department: Department | None = None
    confidence: float | None = None
    model: str
    prompt_version: str
    created_at: datetime


class ComplaintOut(ORMModel):
    id: uuid.UUID
    raw_text: str
    status: ComplaintStatus
    category: ComplaintCategory | None = None
    priority: ComplaintPriority | None = None
    department: Department | None = None
    location: str | None = None
    summary: str | None = None
    overridden_fields: list[str] | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class ComplaintDetailOut(ComplaintOut):
    ai_analysis: ComplaintAIOut | None = None


class ComplaintOverride(BaseModel):
    """Admin override. Every field optional; only supplied fields change,
    and each one is recorded as an override."""

    category: ComplaintCategory | None = None
    priority: ComplaintPriority | None = None
    department: Department | None = None
    location: str | None = Field(default=None, max_length=120)
    summary: str | None = Field(default=None, max_length=1000)
    status: ComplaintStatus | None = None
    note: str | None = Field(default=None, max_length=1000)


class AssistantAsk(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: uuid.UUID | None = None


class AssistantReply(BaseModel):
    text: str
    tool_calls: list[dict] = []
    citations: list[dict] = []
    iterations: int
    conversation_id: uuid.UUID | None = None


class RagAsk(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)


class RagReply(BaseModel):
    answer: str
    grounded: bool
    citations: list[dict]
