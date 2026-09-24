"""Scheduled jobs (see beat_schedule in celery_app).

Every job is idempotent -- dedupe keys, a unique index and row locks make a
repeated or overlapping run harmless -- so each may safely retry on failure.
Dates are the hostel's (Asia/Kathmandu), not the server's.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import hostel_today
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.announcements import AnnouncementService
from app.services.auth import AuthService
from app.services.finance import FinanceService, parse_billing_period
from app.services.leave import LeaveService
from app.workers.celery_app import celery_app
from app.workers.runtime import run_async, run_in_transaction

log = get_logger("workers.scheduled")

RETRYING = {
    "bind": True,
    "autoretry_for": (Exception,),
    "max_retries": 3,
    "retry_backoff": 60,
    "retry_jitter": True,
}


@celery_app.task(name="fees.generate_monthly_invoices", **RETRYING)
def generate_monthly_invoices_task(self, period: str | None = None) -> dict[str, object]:  # type: ignore[no-untyped-def]
    """Bill every resident for the month. Scheduled for the 1st; pass a
    period ('2026-10') to run it by hand."""
    settings = get_settings()
    if period is None and not settings.auto_generate_monthly_invoices:
        return {"skipped": "AUTO_GENERATE_MONTHLY_INVOICES is false"}
    if period:
        year, month = parse_billing_period(period)
    else:
        today = hostel_today()
        year, month = today.year, today.month

    async def work(session: AsyncSession) -> dict[str, object]:
        result = await FinanceService(session).generate_monthly_invoices(
            year=year, month=month, due_day=settings.invoice_due_day
        )
        return result.as_dict()

    return run_async(run_in_transaction(work))


@celery_app.task(name="fees.mark_overdue", **RETRYING)
def mark_overdue_task(self) -> dict[str, int]:  # type: ignore[no-untyped-def]
    async def work(session: AsyncSession) -> dict[str, int]:
        overdue = await FinanceService(session).mark_overdue(today=hostel_today())
        return {"marked_overdue": len(overdue)}

    return run_async(run_in_transaction(work))


@celery_app.task(name="fees.send_due_reminders", **RETRYING)
def send_due_reminders_task(self) -> dict[str, int]:  # type: ignore[no-untyped-def]
    days = get_settings().fee_reminder_days_before_due

    async def work(session: AsyncSession) -> dict[str, int]:
        sent = await FinanceService(session).send_due_reminders(
            today=hostel_today(), days_before=days
        )
        return {"reminded": sent}

    return run_async(run_in_transaction(work))


@celery_app.task(name="announcements.publish_due", **RETRYING)
def publish_due_announcements_task(self) -> dict[str, int]:  # type: ignore[no-untyped-def]
    async def work(session: AsyncSession) -> dict[str, int]:
        count = await AnnouncementService(session).publish_due(now=datetime.now(UTC))
        return {"announced": count}

    return run_async(run_in_transaction(work))


@celery_app.task(name="leave.complete_finished", **RETRYING)
def complete_finished_leave_task(self) -> dict[str, int]:  # type: ignore[no-untyped-def]
    async def work(session: AsyncSession) -> dict[str, int]:
        return {"completed": await LeaveService(session).complete_finished(today=hostel_today())}

    return run_async(run_in_transaction(work))


@celery_app.task(name="auth.purge_expired_refresh_tokens", **RETRYING)
def purge_expired_refresh_tokens_task(self) -> dict[str, int]:  # type: ignore[no-untyped-def]
    async def work(session: AsyncSession) -> dict[str, int]:
        purged = await AuthService(session).purge_expired_refresh_tokens(now=datetime.now(UTC))
        return {"purged": purged}

    return run_async(run_in_transaction(work))
