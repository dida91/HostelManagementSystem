"""Mess feedback analysis.

The student's original rating and comment are never modified; this produces a
separate derived record.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts import extraction as prompts
from app.ai.providers.base import LLMProvider
from app.ai.schemas.extraction import MessFeedbackAnalysis
from app.ai.telemetry.tracing import ai_span
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.enums import AIErrorCategory, AIOperationStatus
from app.models.mess import MessFeedbackAI

log = get_logger("ai.sentiment")

OPERATION = "mess.feedback.analyse"


class MessFeedbackService:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider
        self._settings = get_settings().ai

    async def analyse(
        self,
        *,
        session: AsyncSession,
        feedback_id: uuid.UUID,
        meal_type: str,
        meal_date: date,
        rating: int,
        comment: str,
        user_id: uuid.UUID | None = None,
    ) -> MessFeedbackAI:
        model = self._settings.gemini_fast_model
        record = MessFeedbackAI(
            feedback_id=feedback_id,
            status=AIOperationStatus.PENDING,
            provider="gemini",
            model=model,
            prompt_version=prompts.VERSION,
        )

        async with ai_span(
            operation=OPERATION,
            model=model,
            session=session,
            user_id=user_id,
            prompt_version=prompts.VERSION,
        ) as span:
            try:
                result = await self._provider.generate_structured(
                    prompt=prompts.build_user_prompt(
                        meal_type=meal_type,
                        meal_date=meal_date.isoformat(),
                        rating=rating,
                        comment=comment,
                    ),
                    schema=MessFeedbackAnalysis,
                    system=prompts.SYSTEM,
                    model=model,
                    temperature=0.0,
                )
            except Exception as exc:
                category = getattr(exc, "category", AIErrorCategory.UNKNOWN)
                span.error_category = category
                record.status = AIOperationStatus.FAILED
                record.error_category = category
                session.add(record)
                await session.flush()
                raise

            span.record_usage(result.usage.input_tokens, result.usage.output_tokens)
            data = result.data
            record.status = AIOperationStatus.SUCCESS
            record.sentiment = data.sentiment
            record.topics = data.topics
            record.issues = data.issues
            record.summary = data.summary
            record.input_tokens = result.usage.input_tokens
            record.output_tokens = result.usage.output_tokens

        session.add(record)
        await session.flush()
        return record
