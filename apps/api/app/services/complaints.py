"""Complaint business logic.

The AI result seeds the effective triage fields, but an admin override always
wins and is recorded. The model's own prediction is preserved untouched in
complaint_ai_analyses so model-vs-human agreement stays measurable.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError
from app.core.logging import get_logger, request_id_ctx
from app.models.complaint import Complaint, ComplaintAIAnalysis, ComplaintEvent
from app.models.enums import AIOperationStatus, ComplaintStatus, UserRole
from app.models.user import AuditLog, User

log = get_logger("services.complaints")


class ComplaintService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, student_id: uuid.UUID, text: str) -> Complaint:
        complaint = Complaint(
            student_id=student_id, raw_text=text.strip(), status=ComplaintStatus.SUBMITTED
        )
        self._session.add(complaint)
        await self._session.flush()
        self._session.add(
            ComplaintEvent(complaint_id=complaint.id, to_status=ComplaintStatus.SUBMITTED)
        )
        await self._session.flush()
        return complaint

    async def get_for_user(
        self, *, complaint_id: uuid.UUID, user: User, student_id: uuid.UUID | None
    ) -> Complaint:
        """Ownership enforced here in the service/repository layer so no router
        can forget it -- and so the AI tool path inherits the same rule."""
        stmt = (
            select(Complaint)
            .options(selectinload(Complaint.analyses))
            .where(Complaint.id == complaint_id)
        )
        complaint = (await self._session.execute(stmt)).scalar_one_or_none()
        if complaint is None:
            raise NotFoundError("Complaint not found.")

        if user.role is UserRole.STUDENT:
            if student_id is None or complaint.student_id != student_id:
                # 404 rather than 403: a student must not learn that another
                # student's complaint exists.
                raise NotFoundError("Complaint not found.")
        return complaint

    async def apply_ai_analysis(
        self, *, complaint: Complaint, analysis: ComplaintAIAnalysis
    ) -> None:
        """Seed effective fields from AI, but never overwrite an admin override."""
        if analysis.status is not AIOperationStatus.SUCCESS:
            return
        overridden = set(complaint.overridden_fields or [])
        if "category" not in overridden and complaint.category is None:
            complaint.category = analysis.category
        if "priority" not in overridden and complaint.priority is None:
            complaint.priority = analysis.priority
        if "department" not in overridden and complaint.department is None:
            complaint.department = analysis.suggested_department
        if "location" not in overridden and complaint.location is None:
            complaint.location = analysis.location
        if "summary" not in overridden and complaint.summary is None:
            complaint.summary = analysis.summary
        if complaint.status is ComplaintStatus.SUBMITTED:
            complaint.status = ComplaintStatus.TRIAGED
        await self._session.flush()

    async def override(
        self,
        *,
        complaint: Complaint,
        actor: User,
        changes: dict[str, object],
        note: str | None = None,
    ) -> Complaint:
        before = {
            "category": complaint.category.value if complaint.category else None,
            "priority": complaint.priority.value if complaint.priority else None,
            "department": complaint.department.value if complaint.department else None,
            "location": complaint.location,
            "summary": complaint.summary,
            "status": complaint.status.value,
        }
        overridden = set(complaint.overridden_fields or [])
        old_status = complaint.status

        for field, value in changes.items():
            if value is None:
                continue
            setattr(complaint, field, value)
            overridden.add(field)

        complaint.overridden_fields = sorted(overridden)
        if complaint.status is ComplaintStatus.RESOLVED and complaint.resolved_at is None:
            complaint.resolved_at = datetime.now(UTC)

        if complaint.status != old_status:
            self._session.add(
                ComplaintEvent(
                    complaint_id=complaint.id,
                    actor_user_id=actor.id,
                    from_status=old_status,
                    to_status=complaint.status,
                    note=note,
                )
            )

        after = {
            k: (
                getattr(complaint, k).value
                if hasattr(getattr(complaint, k), "value")
                else getattr(complaint, k)
            )
            for k in before
        }
        self._session.add(
            AuditLog(
                actor_user_id=actor.id,
                action="complaint.override",
                entity_type="complaint",
                entity_id=str(complaint.id),
                before=before,
                after=after,
                request_id=request_id_ctx.get(),
            )
        )
        await self._session.flush()
        log.info(
            "complaint_overridden",
            complaint_id=str(complaint.id),
            actor=str(actor.id),
            fields=sorted(changes),
        )
        return complaint
