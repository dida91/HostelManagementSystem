"""Structured output schemas for mess feedback and generic extraction."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import Sentiment


class MessFeedbackAnalysis(BaseModel):
    """Derived analysis of a student's mess feedback. The original rating and
    comment are preserved separately and never replaced by this."""

    sentiment: Sentiment = Field(
        description="MIXED when the comment contains both praise and criticism."
    )
    topics: list[str] = Field(
        default_factory=list,
        description="Food items or aspects mentioned, lowercase, e.g. ['rice','dal'].",
        max_length=12,
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Specific problems stated, e.g. ['dal too salty']. Empty if none.",
        max_length=12,
    )
    summary: str = Field(description="One short neutral sentence.", max_length=300)


class DocumentTopics(BaseModel):
    """Topics extracted from a hostel document, used to enrich chunk metadata."""

    topics: list[str] = Field(default_factory=list, max_length=20)
    document_summary: str = Field(max_length=1000)
