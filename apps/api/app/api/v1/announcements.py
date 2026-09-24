"""Hostel announcements and notices."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep, require_roles
from app.core.errors import NotFoundError, ValidationFailedError
from app.models.enums import UserRole
from app.models.mess import Announcement
from app.schemas.hostel import AnnouncementCreate, AnnouncementOut, AnnouncementUpdate
from app.services.announcements import AnnouncementService, visible_audiences
from app.services.audit import record_audit

router = APIRouter(prefix="/announcements", tags=["announcements"])
WardenOnly = Depends(require_roles(UserRole.WARDEN, UserRole.SUPER_ADMIN))


@router.get("", response_model=list[AnnouncementOut])
async def list_announcements(
    user: CurrentUser, session: SessionDep, include_expired: bool = Query(default=False)
) -> list[AnnouncementOut]:
    """Current announcements for the caller's audience.

    Students see notices for everyone and for students, and never see one
    before its publish time. Staff with include_expired=true also see
    scheduled and expired notices, to manage them.
    """
    now = datetime.now(UTC)
    stmt = select(Announcement).where(Announcement.audience.in_(visible_audiences(user.role)))
    if user.role is UserRole.STUDENT or not include_expired:
        stmt = stmt.where(Announcement.publish_at <= now)
    if not include_expired:
        stmt = stmt.where(
            (Announcement.expires_at.is_(None)) | (Announcement.expires_at >= now),
        )
    rows = (
        (await session.execute(stmt.order_by(Announcement.publish_at.desc()).limit(50)))
        .scalars()
        .all()
    )
    return [AnnouncementOut.model_validate(r) for r in rows]


@router.post(
    "",
    response_model=AnnouncementOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[WardenOnly],
)
async def create_announcement(
    payload: AnnouncementCreate, user: CurrentUser, session: SessionDep
) -> Announcement:
    """Publish a notice. Its audience is notified now, or -- for a future
    publish_at -- by the scheduler when that time arrives."""
    now = datetime.now(UTC)
    announcement = Announcement(
        title=payload.title,
        body=payload.body,
        audience=payload.audience,
        publish_at=payload.publish_at or now,
        expires_at=payload.expires_at,
        created_by_user_id=user.id,
    )
    session.add(announcement)
    await session.flush()
    await AnnouncementService(session).notify_if_due(announcement, now=now)
    return announcement


@router.patch("/{announcement_id}", response_model=AnnouncementOut, dependencies=[WardenOnly])
async def update_announcement(
    announcement_id: uuid.UUID,
    payload: AnnouncementUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> Announcement:
    """Edit a notice. Residents already notified are not notified again."""
    announcement = await session.get(Announcement, announcement_id)
    if announcement is None:
        raise NotFoundError("Announcement not found.")

    changes = payload.model_dump(exclude_unset=True)
    # expires_at may be cleared with an explicit null; nothing else may.
    changes = {k: v for k, v in changes.items() if v is not None or k == "expires_at"}
    publish_at = changes.get("publish_at", announcement.publish_at)
    expires_at = changes.get("expires_at", announcement.expires_at)
    if expires_at is not None and expires_at <= publish_at:
        raise ValidationFailedError("expires_at must be after publish_at.")

    before = {k: getattr(announcement, k) for k in changes}
    for key, value in changes.items():
        setattr(announcement, key, value)
    await session.flush()
    record_audit(
        session,
        actor_id=user.id,
        action="announcement.update",
        entity_type="announcement",
        entity_id=announcement.id,
        before=before,
        after=changes,
    )
    await AnnouncementService(session).notify_if_due(announcement, now=datetime.now(UTC))
    return announcement


@router.delete(
    "/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[WardenOnly]
)
async def delete_announcement(
    announcement_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> None:
    announcement = await session.get(Announcement, announcement_id)
    if announcement is None:
        raise NotFoundError("Announcement not found.")
    record_audit(
        session,
        actor_id=user.id,
        action="announcement.delete",
        entity_type="announcement",
        entity_id=announcement.id,
        before={
            "title": announcement.title,
            "body": announcement.body,
            "audience": announcement.audience,
            "publish_at": announcement.publish_at,
        },
    )
    await session.delete(announcement)
    await session.flush()
