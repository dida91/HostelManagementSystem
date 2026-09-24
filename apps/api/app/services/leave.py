"""Leave housekeeping."""

from __future__ import annotations

from datetime import date

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LeaveStatus
from app.models.leave import LeaveRequest


class LeaveService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def complete_finished(self, *, today: date) -> int:
        """Approved leave whose last day has passed becomes COMPLETED, so the
        warden's list of current leave only shows who is actually away."""
        result = await self._session.execute(
            update(LeaveRequest)
            .where(LeaveRequest.status == LeaveStatus.APPROVED, LeaveRequest.to_date < today)
            .values(status=LeaveStatus.COMPLETED)
        )
        return int(result.rowcount or 0)  # type: ignore[attr-defined]
