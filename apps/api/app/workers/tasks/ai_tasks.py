"""Background AI tasks.

Complaint analysis runs here rather than inline so a slow or failing model never
blocks a student from filing a complaint.
"""

from __future__ import annotations

import uuid

from app.ai.providers.registry import ai_is_available, get_llm_provider
from app.ai.services.classification import ComplaintAnalysisService
from app.core.db import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.complaint import Complaint
from app.workers.celery_app import celery_app
from app.workers.runtime import run_async

log = get_logger("workers.ai")


async def _analyse(complaint_id: uuid.UUID) -> str:
    async with AsyncSessionLocal() as session:
        complaint = await session.get(Complaint, complaint_id)
        if complaint is None:
            return "not_found"

        service = ComplaintAnalysisService(get_llm_provider())
        analysis = await service.analyse(
            session=session, complaint_id=complaint.id, complaint_text=complaint.raw_text
        )

        from app.services.complaints import ComplaintService

        await ComplaintService(session).apply_ai_analysis(complaint=complaint, analysis=analysis)
        await session.commit()
        return analysis.status.value


@celery_app.task(
    name="ai.analyse_complaint",
    bind=True,
    max_retries=2,  # bounded: no infinite retry loop
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
def analyse_complaint_task(self, complaint_id: str) -> str:  # type: ignore[no-untyped-def]
    if not ai_is_available():
        # Not an error: the system is designed to keep working without AI.
        log.warning("ai_unavailable_skipping_analysis", complaint_id=complaint_id)
        return "skipped_ai_unavailable"

    log.info("analysing_complaint", complaint_id=complaint_id)
    return run_async(_analyse(uuid.UUID(complaint_id)))


@celery_app.task(
    name="ai.analyse_mess_feedback",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def analyse_mess_feedback_task(self, feedback_id: str) -> str:  # type: ignore[no-untyped-def]
    if not ai_is_available():
        return "skipped_ai_unavailable"

    async def _run() -> str:
        from app.ai.services.sentiment import MessFeedbackService
        from app.models.mess import MessFeedback

        async with AsyncSessionLocal() as session:
            fb = await session.get(MessFeedback, uuid.UUID(feedback_id))
            if fb is None or not fb.comment:
                return "skipped_no_comment"
            service = MessFeedbackService(get_llm_provider())
            record = await service.analyse(
                session=session,
                feedback_id=fb.id,
                meal_type=fb.meal_type.value,
                meal_date=fb.meal_date,
                rating=fb.rating,
                comment=fb.comment,
            )
            await session.commit()
            return record.status.value

    return run_async(_run())
