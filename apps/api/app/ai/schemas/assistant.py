"""Schemas for the RAG answer path."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Citation(BaseModel):
    source_tag: str = Field(description="The [S#] tag of the source used.")
    quote: str | None = Field(default=None, max_length=400)


class GroundedAnswer(BaseModel):
    """An answer that must be supported by the supplied context."""

    answer: str = Field(description="The answer, in the same language as the question.")
    grounded: bool = Field(
        description=(
            "True only if the supplied context actually supports the answer. "
            "False if the context is insufficient -- in that case say so in `answer`."
        )
    )
    citations: list[Citation] = Field(
        default_factory=list, description="Source tags actually used. Empty if grounded is false."
    )
