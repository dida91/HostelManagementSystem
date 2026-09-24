"""Sends queued email/SMS deliveries (the notification outbox). Runs in the worker.

Rows are CLAIMED before anything is sent (status -> SENDING, using
FOR UPDATE SKIP LOCKED), so two workers, or a worker and the periodic sweep,
never pick up the same message. A claim older than CLAIM_TIMEOUT is assumed to
belong to a worker that died mid-send and is taken over: delivery is
at-least-once, never silently dropped.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.base import DeliveryFailed, EmailSender, SmsSender
from app.models.enums import DeliveryStatus, NotificationChannel
from app.models.notification import NotificationDelivery

log = get_logger("services.delivery")

MAX_ATTEMPTS = 4
RETRY_BACKOFF = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30))
CLAIM_TIMEOUT = timedelta(minutes=10)


@dataclass(slots=True)
class DispatchResult:
    sent: int = 0
    retrying: int = 0
    failed: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"sent": self.sent, "retrying": self.retrying, "failed": self.failed}


class DeliveryDispatcher:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        email: EmailSender | None,
        sms: SmsSender | None,
    ) -> None:
        self._sessions = sessions
        self._email = email
        self._sms = sms

    async def dispatch(self, *, batch_size: int = 50) -> DispatchResult:
        result = DispatchResult()
        for delivery_id in await self._claim(batch_size):
            status = await self._deliver(delivery_id)
            if status is DeliveryStatus.SENT:
                result.sent += 1
            elif status is DeliveryStatus.PENDING:
                result.retrying += 1
            elif status is DeliveryStatus.FAILED:
                result.failed += 1
        if result.sent or result.retrying or result.failed:
            log.info("deliveries_dispatched", **result.as_dict())
        return result

    async def _claim(self, batch_size: int) -> list[uuid.UUID]:
        now = datetime.now(UTC)
        due = (
            select(NotificationDelivery.id)
            .where(
                or_(
                    and_(
                        NotificationDelivery.status == DeliveryStatus.PENDING,
                        NotificationDelivery.next_attempt_at <= now,
                    ),
                    and_(
                        NotificationDelivery.status == DeliveryStatus.SENDING,
                        NotificationDelivery.claimed_at < now - CLAIM_TIMEOUT,
                    ),
                )
            )
            .order_by(NotificationDelivery.next_attempt_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        async with self._sessions() as session:
            ids = (
                (
                    await session.execute(
                        update(NotificationDelivery)
                        .where(NotificationDelivery.id.in_(due))
                        .values(status=DeliveryStatus.SENDING, claimed_at=now)
                        .returning(NotificationDelivery.id)
                        .execution_options(synchronize_session=False)
                    )
                )
                .scalars()
                .all()
            )
            await session.commit()
        return list(ids)

    async def _deliver(self, delivery_id: uuid.UUID) -> DeliveryStatus | None:
        async with self._sessions() as session:
            delivery = await session.get(
                NotificationDelivery,
                delivery_id,
                options=[selectinload(NotificationDelivery.notification)],
            )
            if delivery is None or delivery.status is not DeliveryStatus.SENDING:
                return None

            try:
                provider_id = await self._send(delivery)
            except DeliveryFailed as exc:
                self._record_failure(delivery, str(exc), permanent=exc.permanent)
            except Exception as exc:  # noqa: BLE001 - unexpected, so retried like a transient error
                log.error(
                    "delivery_unexpected_error",
                    delivery_id=str(delivery.id),
                    error_type=type(exc).__name__,
                )
                self._record_failure(
                    delivery, f"Unexpected error ({type(exc).__name__}).", permanent=False
                )
            else:
                delivery.status = DeliveryStatus.SENT
                delivery.sent_at = datetime.now(UTC)
                delivery.provider_message_id = provider_id[:200] if provider_id else None
                delivery.last_error = None

            delivery.attempts += 1
            delivery.claimed_at = None
            status = delivery.status
            await session.commit()
            return status

    async def _send(self, delivery: NotificationDelivery) -> str | None:
        if delivery.channel is NotificationChannel.EMAIL:
            if self._email is None:
                raise DeliveryFailed("Email is not configured on this worker.")
            return await asyncio.to_thread(
                self._email.send,
                to=delivery.destination,
                subject=delivery.notification.title,
                text=delivery.content,
            )
        if self._sms is None:
            raise DeliveryFailed("SMS is not configured on this worker.")
        return await self._sms.send(to=delivery.destination, text=delivery.content)

    @staticmethod
    def _record_failure(delivery: NotificationDelivery, error: str, *, permanent: bool) -> None:
        attempt = delivery.attempts + 1
        delivery.last_error = error[:500]
        if permanent or attempt >= MAX_ATTEMPTS:
            delivery.status = DeliveryStatus.FAILED
            log.warning(
                "delivery_failed",
                delivery_id=str(delivery.id),
                channel=delivery.channel.value,
                attempts=attempt,
                permanent=permanent,
            )
        else:
            delivery.status = DeliveryStatus.PENDING
            delivery.next_attempt_at = (
                datetime.now(UTC) + RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF)) - 1]
            )


def build_dispatcher(sessions: async_sessionmaker[AsyncSession]) -> DeliveryDispatcher:
    """A dispatcher wired to whichever channels this deployment has configured."""
    settings = get_settings().notify
    email: EmailSender | None = None
    sms: SmsSender | None = None
    if settings.email_enabled:
        from app.integrations.email import SmtpEmailSender

        email = SmtpEmailSender(settings)
    if settings.sms_enabled:
        from app.integrations.sms import SparrowSmsSender

        sms = SparrowSmsSender(settings)
    return DeliveryDispatcher(sessions, email=email, sms=sms)
