"""The signed-in user's notification inbox, and delivery status for the warden."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update

from app.api.deps import CurrentUser, SessionDep, require_roles
from app.core.errors import NotFoundError
from app.models.enums import DeliveryStatus, UserRole
from app.models.notification import Notification, NotificationDelivery
from app.schemas.common import Page
from app.schemas.notification import (
    DeliveryOut,
    NotificationOut,
    NotificationPage,
    ReadAllResult,
    RetryResult,
)
from app.services.audit import record_audit
from app.services.notifications import DISPATCH_TASK
from app.workers.enqueue import enqueue_after_commit

router = APIRouter(prefix="/notifications", tags=["notifications"])
WardenOnly = Depends(require_roles(UserRole.WARDEN, UserRole.SUPER_ADMIN))


@router.get("", response_model=NotificationPage)
async def list_notifications(
    user: CurrentUser,
    session: SessionDep,
    unread_only: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> NotificationPage:
    """Your notifications, newest first, with the unread count for a badge."""
    mine = Notification.user_id == user.id
    stmt = select(Notification).where(mine)
    count_stmt = select(func.count(Notification.id)).where(mine)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
        count_stmt = count_stmt.where(Notification.read_at.is_(None))

    total = (await session.execute(count_stmt)).scalar_one()
    unread = (
        await session.execute(
            select(func.count(Notification.id)).where(mine, Notification.read_at.is_(None))
        )
    ).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return NotificationPage(
        items=[NotificationOut.model_validate(r) for r in rows],
        total=int(total),
        unread=int(unread),
        limit=limit,
        offset=offset,
    )


@router.post("/read-all", response_model=ReadAllResult)
async def mark_all_read(user: CurrentUser, session: SessionDep) -> ReadAllResult:
    result = await session.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    return ReadAllResult(updated=int(result.rowcount or 0))  # type: ignore[attr-defined]


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(
    notification_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Notification:
    notification = await session.get(Notification, notification_id)
    # Someone else's notification is indistinguishable from a missing one.
    if notification is None or notification.user_id != user.id:
        raise NotFoundError("Notification not found.")
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        await session.flush()
    return notification


@router.get("/deliveries", response_model=Page[DeliveryOut], dependencies=[WardenOnly])
async def list_deliveries(
    session: SessionDep,
    status_filter: DeliveryStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[DeliveryOut]:
    """Email/SMS delivery log: what went out, what is retrying, what failed
    and why. Use it to confirm SMTP/SMS settings work."""
    stmt = select(NotificationDelivery)
    count_stmt = select(func.count(NotificationDelivery.id))
    if status_filter is not None:
        stmt = stmt.where(NotificationDelivery.status == status_filter)
        count_stmt = count_stmt.where(NotificationDelivery.status == status_filter)
    total = (await session.execute(count_stmt)).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(NotificationDelivery.created_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return Page(
        items=[DeliveryOut.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.post("/deliveries/retry-failed", response_model=RetryResult, dependencies=[WardenOnly])
async def retry_failed(user: CurrentUser, session: SessionDep) -> RetryResult:
    """Re-queue every FAILED delivery, e.g. after fixing SMTP credentials."""
    result = await session.execute(
        update(NotificationDelivery)
        .where(NotificationDelivery.status == DeliveryStatus.FAILED)
        .values(
            status=DeliveryStatus.PENDING,
            attempts=0,
            next_attempt_at=datetime.now(UTC),
            last_error=None,
        )
    )
    requeued = int(result.rowcount or 0)  # type: ignore[attr-defined]
    if requeued:
        record_audit(
            session,
            actor_id=user.id,
            action="deliveries.retry_failed",
            entity_type="notification_delivery",
            entity_id=None,
            after={"requeued": requeued},
        )
        enqueue_after_commit(session, DISPATCH_TASK)
    return RetryResult(requeued=requeued)
