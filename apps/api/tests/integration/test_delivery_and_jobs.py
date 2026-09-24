"""The email/SMS outbox dispatcher, the worker event-loop runtime, and the
scheduled jobs' building blocks."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal, after_commit
from app.core.security import hash_password
from app.integrations.base import DeliveryFailed
from app.models.enums import (
    DeliveryStatus,
    LeaveStatus,
    LeaveType,
    NotificationCategory,
    NotificationChannel,
    UserRole,
)
from app.models.leave import LeaveRequest
from app.models.notification import Notification, NotificationDelivery
from app.models.user import RefreshToken, Student, User
from app.services.auth import AuthService
from app.services.delivery import MAX_ATTEMPTS, DeliveryDispatcher
from app.services.leave import LeaveService


class RecordingEmail:
    """Test double: records sends; fails for chosen addresses."""

    def __init__(self, fail: dict[str, DeliveryFailed] | None = None) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self.fail = fail or {}

    def send(self, *, to: str, subject: str, text: str) -> str | None:
        if to in self.fail:
            raise self.fail[to]
        self.sent.append((to, subject, text))
        return f"<{uuid.uuid4().hex}@test>"


class RecordingSms:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send(self, *, to: str, text: str) -> str | None:
        self.sent.append((to, text))
        return None


async def _queued(channel: NotificationChannel, destination: str, content: str) -> uuid.UUID:
    """Commit one notification with one PENDING delivery; return the delivery id."""
    async with AsyncSessionLocal() as s:
        user_id = (await s.execute(select(User.id).limit(1))).scalar_one()
        n = Notification(
            user_id=user_id,
            category=NotificationCategory.ANNOUNCEMENT,
            title="Water supply tomorrow",
            body=content,
        )
        s.add(n)
        await s.flush()
        d = NotificationDelivery(
            notification_id=n.id, channel=channel, destination=destination, content=content
        )
        s.add(d)
        await s.commit()
        return d.id


async def _delivery(delivery_id: uuid.UUID) -> NotificationDelivery:
    async with AsyncSessionLocal() as s:
        d = await s.get(NotificationDelivery, delivery_id)
        assert d is not None
        return d


@pytest.mark.asyncio
async def test_dispatch_sends_each_channel_and_records_it() -> None:
    address = f"{uuid.uuid4().hex[:8]}@test.local"
    email_id = await _queued(NotificationChannel.EMAIL, address, "Water is off 10am-2pm.")
    sms_id = await _queued(NotificationChannel.SMS, "9800000001", "Kutumba: water off 10-2.")
    email, sms = RecordingEmail(), RecordingSms()

    await DeliveryDispatcher(AsyncSessionLocal, email=email, sms=sms).dispatch()

    assert (address, "Water supply tomorrow", "Water is off 10am-2pm.") in email.sent
    assert ("9800000001", "Kutumba: water off 10-2.") in sms.sent
    for delivery_id in (email_id, sms_id):
        d = await _delivery(delivery_id)
        assert d.status is DeliveryStatus.SENT and d.sent_at and d.attempts == 1

    # Already sent: a second sweep sends nothing again.
    before = len(email.sent)
    await DeliveryDispatcher(AsyncSessionLocal, email=email, sms=sms).dispatch()
    assert len(email.sent) == before


@pytest.mark.asyncio
async def test_transient_failures_back_off_then_give_up() -> None:
    address = f"{uuid.uuid4().hex[:8]}@test.local"
    delivery_id = await _queued(NotificationChannel.EMAIL, address, "Body")
    flaky = RecordingEmail(fail={address: DeliveryFailed("Could not reach the mail server.")})
    dispatcher = DeliveryDispatcher(AsyncSessionLocal, email=flaky, sms=None)

    await dispatcher.dispatch()
    d = await _delivery(delivery_id)
    assert d.status is DeliveryStatus.PENDING and d.attempts == 1
    assert d.next_attempt_at > datetime.now(UTC), "retried later, not immediately"
    assert d.last_error and "mail server" in d.last_error

    # Make every retry due at once and exhaust the attempts.
    for _ in range(MAX_ATTEMPTS):
        async with AsyncSessionLocal() as s:
            await s.execute(
                text("UPDATE notification_deliveries SET next_attempt_at = now() WHERE id = :id"),
                {"id": delivery_id},
            )
            await s.commit()
        await dispatcher.dispatch()
    d = await _delivery(delivery_id)
    assert d.status is DeliveryStatus.FAILED and d.attempts == MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_permanent_failures_are_not_retried() -> None:
    address = f"{uuid.uuid4().hex[:8]}@test.local"
    delivery_id = await _queued(NotificationChannel.EMAIL, address, "Body")
    refused = RecordingEmail(fail={address: DeliveryFailed("Recipient refused.", permanent=True)})

    await DeliveryDispatcher(AsyncSessionLocal, email=refused, sms=None).dispatch()
    d = await _delivery(delivery_id)
    assert d.status is DeliveryStatus.FAILED and d.attempts == 1


@pytest.mark.asyncio
async def test_a_stale_claim_is_taken_over() -> None:
    """A worker that died mid-send leaves a SENDING row; it is retried."""
    address = f"{uuid.uuid4().hex[:8]}@test.local"
    delivery_id = await _queued(NotificationChannel.EMAIL, address, "Body")
    async with AsyncSessionLocal() as s:
        await s.execute(
            text(
                "UPDATE notification_deliveries SET status = 'SENDING', "
                "claimed_at = now() - interval '1 hour' WHERE id = :id"
            ),
            {"id": delivery_id},
        )
        await s.commit()
    email = RecordingEmail()
    await DeliveryDispatcher(AsyncSessionLocal, email=email, sms=None).dispatch()
    assert (await _delivery(delivery_id)).status is DeliveryStatus.SENT


# ------------------------------------------------------------ worker runtime


def test_worker_loop_survives_many_tasks() -> None:
    """Regression: tasks used asyncio.run(), so the pooled DB connections of
    the first task broke every later task in the same worker process."""
    from app.workers import runtime

    async def query() -> int:
        async with AsyncSessionLocal() as s:
            return int((await s.execute(text("SELECT 1"))).scalar_one())

    try:
        assert [runtime.run_async(query()) for _ in range(3)] == [1, 1, 1]
    finally:
        runtime.shutdown()


def test_run_in_transaction_commits_then_fires_callbacks() -> None:
    from app.workers import runtime

    fired: list[str] = []

    async def ok(session: AsyncSession) -> str:
        after_commit(session, lambda: fired.append("ok"))
        return "done"

    async def boom(session: AsyncSession) -> None:
        after_commit(session, lambda: fired.append("boom"))
        raise RuntimeError("job failed")

    try:
        assert runtime.run_async(runtime.run_in_transaction(ok)) == "done"
        with pytest.raises(RuntimeError):
            runtime.run_async(runtime.run_in_transaction(boom))
    finally:
        runtime.shutdown()
    assert fired == ["ok"], "callbacks of a failed job never fire"


def test_every_scheduled_job_is_a_registered_task() -> None:
    from app.workers.celery_app import celery_app

    celery_app.loader.import_default_modules()
    schedule = celery_app.conf.beat_schedule
    assert schedule
    for name, entry in schedule.items():
        assert entry["task"] in celery_app.tasks, f"{name} points at an unknown task"


# ------------------------------------------------------- housekeeping jobs


@pytest.mark.asyncio
async def test_finished_leave_is_completed(session: AsyncSession) -> None:
    student_id = (await session.execute(select(Student.id).limit(1))).scalar_one()
    ended = LeaveRequest(
        student_id=student_id,
        leave_type=LeaveType.HOME_VISIT,
        from_date=date(2026, 9, 1),
        to_date=date(2026, 9, 3),
        reason="Dashain at home.",
        status=LeaveStatus.APPROVED,
    )
    ongoing = LeaveRequest(
        student_id=student_id,
        leave_type=LeaveType.HOME_VISIT,
        from_date=date(2026, 9, 1),
        to_date=date(2026, 9, 30),
        reason="Long stay at home.",
        status=LeaveStatus.APPROVED,
    )
    session.add_all([ended, ongoing])
    await session.flush()

    await LeaveService(session).complete_finished(today=date(2026, 9, 10))
    await session.refresh(ended)
    await session.refresh(ongoing)
    assert ended.status is LeaveStatus.COMPLETED
    assert ongoing.status is LeaveStatus.APPROVED


@pytest.mark.asyncio
async def test_expired_refresh_tokens_are_purged(session: AsyncSession) -> None:
    user = User(
        email=f"{uuid.uuid4().hex[:8]}@test.local",
        full_name="Token Test",
        password_hash=hash_password("TokenTestPass1"),
        role=UserRole.STAFF,
    )
    session.add(user)
    await session.flush()
    now = datetime.now(UTC)
    for days, tag in ((-1, "old"), (1, "live")):
        session.add(
            RefreshToken(
                user_id=user.id,
                token_hash=uuid.uuid4().hex + tag,
                jti=uuid.uuid4().hex,
                expires_at=now + timedelta(days=days),
            )
        )
    await session.flush()

    assert await AuthService(session).purge_expired_refresh_tokens(now=now) >= 1
    left = (
        (
            await session.execute(
                select(RefreshToken.expires_at).where(RefreshToken.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(left) == 1 and left[0] > now
