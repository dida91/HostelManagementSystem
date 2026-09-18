"""Structured output schemas for complaint analysis.

These are passed to Gemini as `response_schema` AND used to revalidate the
response. Enum-typed fields mean the model cannot invent a category that the
database would later reject.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import ComplaintCategory, ComplaintPriority, Department, Sentiment


class ComplaintAnalysis(BaseModel):
    """AI triage of a single student complaint. Advisory only -- an admin may
    override every field."""

    category: ComplaintCategory = Field(
        description="The single best-fitting category for this complaint."
    )
    priority: ComplaintPriority = Field(
        description=(
            "URGENT only for safety, security, harassment or health risks. "
            "HIGH for loss of an essential service (water, electricity). "
            "MEDIUM for degraded comfort. LOW for minor or cosmetic issues."
        )
    )
    sentiment: Sentiment = Field(description="Emotional tone of the student's message.")
    location: str | None = Field(
        default=None,
        description=(
            "Specific location mentioned, e.g. 'second floor bathroom' or 'room 201'. "
            "Null if the student did not state one. Never guess."
        ),
    )
    summary: str = Field(
        description="One neutral sentence, max 200 characters, describing the issue.",
        max_length=400,
    )
    suggested_department: Department | None = Field(
        default=None, description="Department best placed to resolve this."
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Your confidence in this categorisation, 0.0 to 1.0.",
    )
