from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from app.ai.providers.registry import ai_is_available
from app.api.deps import SessionDep
from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(session: SessionDep) -> dict[str, Any]:
    """Readiness reports each dependency separately.

    AI is reported but does not gate readiness: the hostel system must keep
    accepting complaints and leave requests when Gemini is unreachable.
    """
    checks: dict[str, Any] = {}
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(get_settings().redis_url)
        await client.ping()
        await client.aclose()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    checks["ai_configured"] = ai_is_available()
    checks["status"] = "ok" if checks["database"] == "ok" else "degraded"
    return checks
