"""Narration of trusted, pre-computed analytics.

Deliberate constraint: this service accepts ALREADY-CALCULATED figures and asks
the model only to explain them. Python and SQL compute; the model interprets. It
is never asked to derive a number, because a fluent wrong number is worse than
no narration at all.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.base import LLMProvider
from app.ai.telemetry.tracing import ai_span
from app.core.config import get_settings

OPERATION = "analytics.narrate"
VERSION = "analytics.narrate.v1"

SYSTEM = """You write short administrative briefings for hostel management.

You are given metrics that have ALREADY been calculated from the hostel database.

Rules:
- Use the supplied numbers EXACTLY as given. Never recalculate, round differently,
  or estimate.
- Never introduce a statistic that is not in the supplied data.
- If the data is insufficient to explain a trend, say so plainly.
- Be concise and practical: 3-5 sentences, aimed at a hostel warden.
"""


class AnalyticsNarrationService:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider
        self._settings = get_settings().ai

    async def narrate(
        self,
        *,
        session: AsyncSession,
        metrics: dict[str, Any],
        question: str,
        user_id: uuid.UUID | None = None,
    ) -> str:
        model = self._settings.gemini_fast_model
        prompt = (
            f"Computed metrics (authoritative):\n{json.dumps(metrics, indent=2, default=str)}\n\n"
            f"Question: {question}\n\nWrite the briefing."
        )
        async with ai_span(
            operation=OPERATION,
            model=model,
            session=session,
            user_id=user_id,
            prompt_version=VERSION,
        ) as span:
            result = await self._provider.generate_text(
                prompt=prompt, system=SYSTEM, model=model, temperature=0.3, max_output_tokens=400
            )
            span.record_usage(result.usage.input_tokens, result.usage.output_tokens)
        return result.text
