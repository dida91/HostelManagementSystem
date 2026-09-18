"""AI observability.

Every provider call is wrapped in `ai_span`, which writes exactly one
`ai_operations` row and emits one structured log line. Nothing here logs
prompts, responses, API keys or personal data unless AI_LOG_PAYLOADS is
explicitly enabled (and that is rejected outright in production).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger, request_id_ctx
from app.models.ai import AIOperation
from app.models.enums import AIErrorCategory, AIOperationStatus

log = get_logger("ai.telemetry")

# USD per 1M (input, output) tokens for the PAID tier. Approximate, used only
# for internal cost reporting -- never surfaced as a billing figure.
#
# Embeddings are free on the Gemini API free tier. When
# GEMINI_EMBEDDING_FREE_TIER is true (the default) embedding cost is reported as
# zero, so the dashboard does not show spend that is not actually being charged.
# Unknown models return None rather than a guessed figure: a wrong cost is worse
# than an absent one. Update these when a model's published price is confirmed.
_PRICING: dict[str, tuple[float, float]] = {
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-embedding-001": (0.15, 0.0),
    "gemini-embedding-2": (0.20, 0.0),
}

_EMBEDDING_PREFIXES = ("gemini-embedding-", "text-embedding-")


def estimate_cost_usd(
    model: str, input_tokens: int | None, output_tokens: int | None
) -> Decimal | None:
    if model.startswith(_EMBEDDING_PREFIXES) and get_settings().ai.gemini_embedding_free_tier:
        return Decimal("0.000000")

    key = next((k for k in _PRICING if model.startswith(k)), None)
    if key is None or (input_tokens is None and output_tokens is None):
        return None
    in_rate, out_rate = _PRICING[key]
    cost = ((input_tokens or 0) / 1_000_000) * in_rate + (
        (output_tokens or 0) / 1_000_000
    ) * out_rate
    return Decimal(f"{cost:.6f}")


@dataclass
class AISpan:
    """Mutable handle the caller fills in as the operation progresses."""

    operation: str
    model: str
    prompt_version: str | None = None
    user_id: uuid.UUID | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    retry_count: int = 0
    tool_calls: int = 0
    status: AIOperationStatus = AIOperationStatus.PENDING
    error_category: AIErrorCategory | None = None
    error_detail: str | None = None
    operation_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def record_usage(self, input_tokens: int | None, output_tokens: int | None) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


@asynccontextmanager
async def ai_span(
    *,
    operation: str,
    model: str,
    session: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
    prompt_version: str | None = None,
) -> AsyncIterator[AISpan]:
    """Wrap one AI operation, persisting telemetry whether it succeeds or fails.

    Telemetry failures never mask the underlying operation: if the metrics row
    cannot be written we log and move on rather than turning an observability
    problem into a user-facing error.
    """
    span = AISpan(operation=operation, model=model, prompt_version=prompt_version, user_id=user_id)
    started = time.perf_counter()
    try:
        yield span
        if span.status is AIOperationStatus.PENDING:
            span.status = AIOperationStatus.SUCCESS
    except Exception as exc:
        span.status = AIOperationStatus.FAILED
        if span.error_category is None:
            span.error_category = AIErrorCategory.UNKNOWN
        span.error_detail = f"{type(exc).__name__}: {exc}"[:2000]
        raise
    finally:
        latency_ms = int((time.perf_counter() - started) * 1000)
        cost = estimate_cost_usd(model, span.input_tokens, span.output_tokens)

        log.info(
            "ai_operation",
            operation=operation,
            model=model,
            prompt_version=prompt_version,
            status=span.status.value,
            error_category=span.error_category.value if span.error_category else None,
            latency_ms=latency_ms,
            input_tokens=span.input_tokens,
            output_tokens=span.output_tokens,
            estimated_cost_usd=float(cost) if cost is not None else None,
            retry_count=span.retry_count,
            tool_calls=span.tool_calls,
            user_id=str(span.user_id) if span.user_id else None,
        )

        if session is not None:
            try:
                session.add(
                    AIOperation(
                        id=span.operation_id,
                        request_id=request_id_ctx.get(),
                        user_id=span.user_id,
                        operation=operation,
                        provider="gemini",
                        model=model,
                        prompt_version=prompt_version,
                        status=span.status,
                        error_category=span.error_category,
                        error_detail=span.error_detail,
                        latency_ms=latency_ms,
                        input_tokens=span.input_tokens,
                        output_tokens=span.output_tokens,
                        estimated_cost_usd=cost,
                        retry_count=span.retry_count,
                        tool_calls=span.tool_calls,
                    )
                )
                await session.flush()
            except Exception as exc:  # pragma: no cover - observability must not break the request
                log.error("ai_telemetry_persist_failed", error=str(exc))


def payload_logging_enabled() -> bool:
    return get_settings().ai.ai_log_payloads
