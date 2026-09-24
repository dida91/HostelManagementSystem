"""Resident lifecycle: profile edits, deactivation and password resets.

Every change here is audited: these records describe young women living in
the hostel, and who changed what must always be answerable.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import hostel_today
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.enums import AssignmentStatus, BedStatus, StudentStatus
from app.models.hostel import Bed, BedAssignment
from app.models.user import Student, User
from app.services.audit import record_audit
from app.services.auth import AuthService
from app.services.notifications import NotificationService, password_changed_message
from app.services.rooms import assignment_end_date

log = get_logger("services.students")

USER_FIELDS = {"full_name", "email", "phone"}
DEACTIVATED_STATUSES = {StudentStatus.ALUMNI, StudentStatus.SUSPENDED}


class StudentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_with_user(self, student_id: uuid.UUID) -> tuple[Student, User]:
        row = (
            await self._session.execute(
                select(Student, User)
                .join(User, User.id == Student.user_id)
                .where(Student.id == student_id)
            )
        ).first()
        if row is None:
            raise NotFoundError("Student not found.")
        return row[0], row[1]

    async def update_profile(
        self, student: Student, user: User, changes: dict[str, Any], *, actor: User
    ) -> None:
        if "email" in changes and changes["email"] is not None:
            changes["email"] = changes["email"].lower().strip()
        before: dict[str, Any] = {}
        after: dict[str, Any] = {}
        for key, value in changes.items():
            target = user if key in USER_FIELDS else student
            if getattr(target, key) != value:
                before[key], after[key] = getattr(target, key), value
        if not after:
            return
        try:
            # Applied inside the savepoint, so a duplicate email or phone rolls
            # back only this change, not the request's whole transaction.
            async with self._session.begin_nested():
                for key, value in after.items():
                    setattr(user if key in USER_FIELDS else student, key, value)
                await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "That email or phone number is already used by another account."
            ) from exc
        record_audit(
            self._session,
            actor_id=actor.id,
            action="student.update",
            entity_type="student",
            entity_id=student.id,
            before=before,
            after=after,
        )

    async def deactivate(
        self,
        student: Student,
        user: User,
        *,
        status: StudentStatus,
        reason: str,
        vacate_bed: bool,
        leaving_date: date | None,
        actor: User,
    ) -> uuid.UUID | None:
        """Move a resident to ALUMNI or SUSPENDED: sign-in is disabled at once,
        every session is revoked, and (always, for ALUMNI) the bed is vacated.

        Returns the id of the bed assignment that was ended, if any. The
        student's records -- fees, complaints, leave -- are kept intact.
        """
        if status not in DEACTIVATED_STATUSES:
            raise ValidationFailedError("A student can be deactivated as ALUMNI or SUSPENDED.")
        if student.status is status and not user.is_active:
            raise ConflictError(f"This student is already {status.value.lower()}.")
        if status is StudentStatus.ALUMNI:
            vacate_bed = True  # a former resident cannot keep a bed

        before = {"status": student.status, "is_active": user.is_active}
        student.status = status
        user.is_active = False
        await AuthService(self._session).revoke_all_sessions(user.id)

        ended: uuid.UUID | None = None
        if vacate_bed:
            assignment = (
                await self._session.execute(
                    select(BedAssignment)
                    .where(
                        BedAssignment.student_id == student.id,
                        BedAssignment.status == AssignmentStatus.ACTIVE,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if assignment is not None:
                assignment.status = AssignmentStatus.ENDED
                assignment.to_date = assignment_end_date(
                    leaving_date, hostel_today(), assignment.from_date
                )
                assignment.note = reason
                bed = await self._session.get(Bed, assignment.bed_id)
                if bed is not None:
                    bed.status = BedStatus.VACANT
                ended = assignment.id

        await self._session.flush()
        record_audit(
            self._session,
            actor_id=actor.id,
            action="student.deactivate",
            entity_type="student",
            entity_id=student.id,
            before=before,
            after={
                "status": status,
                "is_active": False,
                "reason": reason,
                "ended_assignment_id": ended,
            },
        )
        log.info(
            "student_deactivated",
            student_id=str(student.id),
            status=status.value,
            vacated=ended is not None,
        )
        return ended

    async def reactivate(self, student: Student, user: User, *, actor: User) -> None:
        if student.status is StudentStatus.ACTIVE and user.is_active:
            raise ConflictError("This student is already active.")
        before = {"status": student.status, "is_active": user.is_active}
        student.status = StudentStatus.ACTIVE
        user.is_active = True
        await self._session.flush()
        record_audit(
            self._session,
            actor_id=actor.id,
            action="student.reactivate",
            entity_type="student",
            entity_id=student.id,
            before=before,
            after={"status": StudentStatus.ACTIVE, "is_active": True},
        )

    async def reset_password(
        self, student: Student, user: User, *, new_password: str, actor: User
    ) -> None:
        """Set a new password chosen by the warden. Every existing session is
        signed out, and the resident is told it happened."""
        user.password_hash = hash_password(new_password)
        await AuthService(self._session).revoke_all_sessions(user.id)
        await self._session.flush()
        # The password itself is never written to the audit log.
        record_audit(
            self._session,
            actor_id=actor.id,
            action="student.password_reset",
            entity_type="student",
            entity_id=student.id,
        )
        await NotificationService(self._session).notify(
            [user.id], password_changed_message(by_staff=True)
        )
