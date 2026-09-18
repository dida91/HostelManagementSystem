"""Analytics computed entirely in SQL.

Every number here is produced by PostgreSQL. The AI layer may narrate these
results but never generates them -- see docs/adr/0003.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.complaint import Complaint
from app.models.enums import (
    AssignmentStatus,
    ComplaintStatus,
    LedgerEntryType,
)
from app.models.finance import StudentLedgerEntry
from app.models.hostel import Bed, BedAssignment
from app.models.mess import MessFeedback


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def occupancy(self) -> dict[str, Any]:
        total = (await self._session.execute(select(func.count(Bed.id)))).scalar_one()
        occupied = (
            await self._session.execute(
                select(func.count(BedAssignment.id)).where(
                    BedAssignment.status == AssignmentStatus.ACTIVE
                )
            )
        ).scalar_one()
        total, occupied = int(total), int(occupied)
        return {
            "total_beds": total,
            "occupied_beds": occupied,
            "vacant_beds": total - occupied,
            "occupancy_rate_percent": round(100 * occupied / total, 1) if total else 0.0,
        }

    async def complaints(self, *, days: int = 30) -> dict[str, Any]:
        since = datetime.now(UTC) - timedelta(days=days)
        prev_since = since - timedelta(days=days)

        by_category: dict[Any, int] = {
            row[0]: row[1]
            for row in (
                await self._session.execute(
                    select(Complaint.category, func.count(Complaint.id))
                    .where(Complaint.created_at >= since)
                    .group_by(Complaint.category)
                )
            ).all()
        }
        by_status: dict[Any, int] = {
            row[0]: row[1]
            for row in (
                await self._session.execute(
                    select(Complaint.status, func.count(Complaint.id))
                    .where(Complaint.created_at >= since)
                    .group_by(Complaint.status)
                )
            ).all()
        }
        current = (
            await self._session.execute(
                select(func.count(Complaint.id)).where(Complaint.created_at >= since)
            )
        ).scalar_one()
        previous = (
            await self._session.execute(
                select(func.count(Complaint.id)).where(
                    Complaint.created_at >= prev_since, Complaint.created_at < since
                )
            )
        ).scalar_one()

        # Median resolution time, computed by the database.
        median_hours = (
            await self._session.execute(
                select(
                    func.percentile_cont(0.5).within_group(
                        func.extract("epoch", Complaint.resolved_at - Complaint.created_at) / 3600.0
                    )
                ).where(Complaint.resolved_at.is_not(None), Complaint.created_at >= since)
            )
        ).scalar_one()

        change = (
            round(100 * (int(current) - int(previous)) / int(previous), 1) if previous else None
        )
        return {
            "window_days": days,
            "total": int(current),
            "previous_period_total": int(previous),
            "change_percent": change,
            "by_category": {(k.value if k else "uncategorised"): v for k, v in by_category.items()},
            "by_status": {(k.value if k else "unknown"): v for k, v in by_status.items()},
            "open": sum(
                v
                for k, v in by_status.items()
                if k
                in {ComplaintStatus.SUBMITTED, ComplaintStatus.TRIAGED, ComplaintStatus.IN_PROGRESS}
            ),
            "median_resolution_hours": round(float(median_hours), 1) if median_hours else None,
        }

    async def fees(self) -> dict[str, Any]:
        debit = (
            await self._session.execute(
                select(func.coalesce(func.sum(StudentLedgerEntry.amount_npr), 0)).where(
                    StudentLedgerEntry.entry_type == LedgerEntryType.DEBIT
                )
            )
        ).scalar_one()
        credit = (
            await self._session.execute(
                select(func.coalesce(func.sum(StudentLedgerEntry.amount_npr), 0)).where(
                    StudentLedgerEntry.entry_type == LedgerEntryType.CREDIT
                )
            )
        ).scalar_one()
        charged, collected = Decimal(debit), Decimal(credit)
        return {
            "currency": "NPR",
            "total_charged": str(charged),
            "total_collected": str(collected),
            "total_outstanding": str(charged - collected),
            "collection_rate_percent": (
                round(float(100 * collected / charged), 1) if charged else 0.0
            ),
        }

    async def mess(self, *, days: int = 30) -> dict[str, Any]:
        since = date.today() - timedelta(days=days)
        avg = (
            await self._session.execute(
                select(func.avg(MessFeedback.rating)).where(MessFeedback.meal_date >= since)
            )
        ).scalar_one()
        count = (
            await self._session.execute(
                select(func.count(MessFeedback.id)).where(MessFeedback.meal_date >= since)
            )
        ).scalar_one()
        by_meal: dict[Any, Any] = {
            row[0]: row[1]
            for row in (
                await self._session.execute(
                    select(MessFeedback.meal_type, func.avg(MessFeedback.rating))
                    .where(MessFeedback.meal_date >= since)
                    .group_by(MessFeedback.meal_type)
                )
            ).all()
        }
        return {
            "window_days": days,
            "responses": int(count),
            "average_rating": round(float(avg), 2) if avg else None,
            "average_by_meal": {
                k.value: round(float(v), 2) for k, v in by_meal.items() if v is not None
            },
        }

    async def overview(self, *, days: int = 30) -> dict[str, Any]:
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "occupancy": await self.occupancy(),
            "complaints": await self.complaints(days=days),
            "fees": await self.fees(),
            "mess": await self.mess(days=days),
        }
