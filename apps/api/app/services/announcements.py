"""Announcements: who can see them, and notifying their audience.

An announcement is notified once, when it becomes visible -- immediately if it
is published now, or by the scheduled job once a future publish_at passes.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from app.models.mess import Announcement
from app.services.notifications import NotificationService, announcement_message

STAFF_ROLES = (UserRole.STAFF, UserRole.WARDEN, UserRole.SUPER_ADMIN)
AUDIENCE_ROLES: dict[str, tuple[UserRole, ...]] = {
    "ALL": (UserRole.STUDENT, *STAFF_ROLES),
    "STUDENTS": (UserRole.STUDENT,),
    "STAFF": STAFF_ROLES,
}


def visible_audiences(role: UserRole) -> tuple[str, ...]:
    """Students never see staff-only notices; staff see everything."""
    if role is UserRole.STUDENT:
        return ("ALL", "STUDENTS")
    return tuple(AUDIENCE_ROLES)


class AnnouncementService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def notify_if_due(self, announcement: Announcement, *, now: datetime) -> bool:
        if announcement.notified_at is not None or announcement.publish_at > now:
            return False
        if announcement.expires_at is not None and announcement.expires_at <= now:
            return False
        await NotificationService(self._session).notify_roles(
            AUDIENCE_ROLES.get(announcement.audience, AUDIENCE_ROLES["ALL"]),
            announcement_message(announcement.title, announcement.body),
            exclude=announcement.created_by_user_id,
            dedupe_key=f"announcement:{announcement.id}",
        )
        announcement.notified_at = now
        await self._session.flush()
        return True

    async def publish_due(self, *, now: datetime) -> int:
        """Notify every announcement whose publish time has arrived."""
        due = (
            (
                await self._session.execute(
                    select(Announcement)
                    .where(
                        Announcement.notified_at.is_(None),
                        Announcement.publish_at <= now,
                        or_(Announcement.expires_at.is_(None), Announcement.expires_at > now),
                    )
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        count = 0
        for announcement in due:
            if await self.notify_if_due(announcement, now=now):
                count += 1
        return count
