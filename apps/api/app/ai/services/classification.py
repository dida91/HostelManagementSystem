"""Complaint analysis service.

Depends on LLMProvider only. Every call is wrapped in ai_span, and both success
and failure are persisted as a ComplaintAIAnalysis row so a failed analysis is
visible rather than silent.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts import complaint as prompts
from app.ai.providers.base import LLMProvider
from app.ai.schemas.complaint import ComplaintAnalysis
from app.ai.telemetry.tracing import ai_span
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.complaint import ComplaintAIAnalysis
from app.models.enums import AIErrorCategory, AIOperationStatus

log = get_logger("ai.classification")

OPERATION = "complaint.analyse"


class ComplaintAnalysisService:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider
        self._settings = get_settings().ai

    async def analyse(
        self,
        *,
        session: AsyncSession,
        complaint_id: uuid.UUID,
        complaint_text: str,
        user_id: uuid.UUID | None = None,
    ) -> ComplaintAIAnalysis:
        """Analyse one complaint and persist the result.

        Uses the fast model: triage is high-volume and the task is simple
        classification, so the larger model is not justified here.
        """
        model = self._settings.gemini_fast_model
        record = ComplaintAIAnalysis(
            complaint_id=complaint_id,
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
                    prompt=prompts.build_user_prompt(complaint_text),
                    schema=ComplaintAnalysis,
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
                log.warning(
                    "complaint_analysis_failed",
                    complaint_id=str(complaint_id),
                    category=category.value,
                )
                raise

            span.record_usage(result.usage.input_tokens, result.usage.output_tokens)
            span.retry_count = result.retry_count

            data = result.data
            record.status = AIOperationStatus.SUCCESS
            record.category = data.category
            record.priority = data.priority
            record.sentiment = data.sentiment
            record.location = data.location
            record.summary = data.summary
            record.suggested_department = data.suggested_department
            record.confidence = data.confidence
            record.raw_response = result.raw
            record.input_tokens = result.usage.input_tokens
            record.output_tokens = result.usage.output_tokens
            record.retry_count = result.retry_count

        session.add(record)
        await session.flush()
        return record
