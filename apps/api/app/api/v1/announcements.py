"""Hostel announcements and notices."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep, require_roles
from app.models.enums import UserRole
from app.models.mess import Announcement
from app.schemas.hostel import AnnouncementCreate, AnnouncementOut

router = APIRouter(prefix="/announcements", tags=["announcements"])
WardenOnly = Depends(require_roles(UserRole.WARDEN, UserRole.SUPER_ADMIN))


@router.get("", response_model=list[AnnouncementOut])
async def list_announcements(
    session: SessionDep, include_expired: bool = Query(default=False)
) -> list[AnnouncementOut]:
    now = datetime.now(UTC)
    stmt = select(Announcement)
    if not include_expired:
        stmt = stmt.where(
            Announcement.publish_at <= now,
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
    announcement = Announcement(
        title=payload.title,
        body=payload.body,
        audience=payload.audience,
        publish_at=payload.publish_at or datetime.now(UTC),
        expires_at=payload.expires_at,
        created_by_user_id=user.id,
    )
    session.add(announcement)
    await session.flush()
    return announcement
