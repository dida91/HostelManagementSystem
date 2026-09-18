"""Analytics. Figures come from SQL; the AI layer only narrates them."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.ai.providers.registry import ai_is_available, get_llm_provider
from app.ai.services.summarization import AnalyticsNarrationService
from app.api.deps import CurrentUser, SessionDep, rate_limit, require_roles
from app.core.errors import AIUnavailableError
from app.models.enums import UserRole
from app.services.analytics import AnalyticsService

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_roles(UserRole.STAFF, UserRole.WARDEN, UserRole.SUPER_ADMIN))],
)


class InsightRequest(BaseModel):
    question: str = "Summarise this month for the warden."
    days: int = 30


class InsightResponse(BaseModel):
    narrative: str
    metrics: dict
    disclaimer: str = (
        "Figures are computed from the hostel database. The narrative is AI-generated "
        "commentary on those figures."
    )


@router.get("/overview")
async def overview(session: SessionDep, days: int = Query(default=30, ge=1, le=365)) -> dict:
    return await AnalyticsService(session).overview(days=days)


@router.get("/occupancy")
async def occupancy(session: SessionDep) -> dict:
    return await AnalyticsService(session).occupancy()


@router.get("/complaints")
async def complaints(session: SessionDep, days: int = Query(default=30, ge=1, le=365)) -> dict:
    return await AnalyticsService(session).complaints(days=days)


@router.get("/fees")
async def fees(session: SessionDep) -> dict:
    return await AnalyticsService(session).fees()


@router.post(
    "/insights",
    response_model=InsightResponse,
    dependencies=[Depends(rate_limit("ai"))],
)
async def insights(
    payload: InsightRequest, user: CurrentUser, session: SessionDep
) -> InsightResponse:
    """Narrate the computed metrics.

    The metrics are calculated first and passed to the model as authoritative
    input; the model is instructed to use them exactly and never to derive a
    figure of its own.
    """
    metrics = await AnalyticsService(session).overview(days=payload.days)
    if not ai_is_available():
        raise AIUnavailableError("AI commentary is unavailable. The figures above are unaffected.")

    narrative = await AnalyticsNarrationService(get_llm_provider()).narrate(
        session=session, metrics=metrics, question=payload.question, user_id=user.id
    )
    return InsightResponse(narrative=narrative, metrics=metrics)
