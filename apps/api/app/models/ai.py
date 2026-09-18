"""AI observability and assistant conversations.

Every Gemini call -- from any service, any worker -- writes exactly one
`ai_operations` row. That table is the single place to answer "what did the AI
cost, how often did it fail, and how slow was it".
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey
from app.models.enums import AIErrorCategory, AIOperationStatus, MessageRole


class AIOperation(UUIDPrimaryKey, Base):
    __tablename__ = "ai_operations"

    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    operation: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), default="gemini", nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(40))

    status: Mapped[AIOperationStatus] = mapped_column(
        Enum(AIOperationStatus, name="ai_operation_status"), nullable=False
    )
    error_category: Mapped[AIErrorCategory | None] = mapped_column(
        Enum(AIErrorCategory, name="ai_error_category")
    )
    # Operator-facing detail. Never returned to an end user.
    error_detail: Mapped[str | None] = mapped_column(Text)

    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_ai_ops_operation_status", "operation", "status"),
        Index("ix_ai_ops_created", "created_at"),
    )


class AssistantConversation(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "assistant_conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(200))

    messages: Mapped[list[AssistantMessage]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AssistantMessage.created_at",
    )


class AssistantMessage(UUIDPrimaryKey, Base):
    __tablename__ = "assistant_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("assistant_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="message_role"), nullable=False
    )
    content: Mapped[str | None] = mapped_column(Text)
    # Tool invocations made during this turn, with their arguments and results.
    tool_calls: Mapped[list | None] = mapped_column(JSONB)
    citations: Mapped[list | None] = mapped_column(JSONB)
    ai_operation_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ai_operations.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped[AssistantConversation] = relationship(back_populates="messages")


class RagQuery(UUIDPrimaryKey, Base):
    """Retrieval trace: makes any past answer reconstructible and auditable."""

    __tablename__ = "rag_queries"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_chunk_ids: Mapped[list | None] = mapped_column(JSONB)
    dense_hits: Mapped[int | None] = mapped_column(Integer)
    lexical_hits: Mapped[int | None] = mapped_column(Integer)
    answer: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSONB)
    grounded: Mapped[bool | None] = mapped_column()
    retrieval_ms: Mapped[int | None] = mapped_column(Integer)
    generation_ms: Mapped[int | None] = mapped_column(Integer)
    ai_operation_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ai_operations.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
