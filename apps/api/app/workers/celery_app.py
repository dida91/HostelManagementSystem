"""Celery application and the schedule of recurring jobs.

Async work inside tasks runs on one long-lived event loop per worker process
(see workers/runtime.py), never a fresh loop per task: the database pool, the
Redis client and the Gemini HTTP client all bind to the loop they first ran on.

Recurring jobs need a beat process. Locally, `make worker` runs beat inside
the worker (-B). In production run exactly one `celery beat` alongside the
workers; the jobs are idempotent, so an accidental second beat is harmless.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "hostel",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.tasks.ai_tasks",
        "app.workers.tasks.document_tasks",
        "app.workers.tasks.notification_tasks",
        "app.workers.tasks.scheduled_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Crontab times below are the hostel's local times.
    timezone=settings.hostel_timezone,
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=180,
    task_soft_time_limit=150,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        # Sweep the email/SMS outbox: retries, and anything queued while the
        # broker was unreachable. Deliveries are also kicked on every commit.
        "notifications-dispatch": {
            "task": "notifications.dispatch",
            "schedule": 30.0,
        },
        "announcements-publish-due": {
            "task": "announcements.publish_due",
            "schedule": crontab(minute="*/5"),
        },
        "fees-generate-monthly-invoices": {
            "task": "fees.generate_monthly_invoices",
            "schedule": crontab(day_of_month="1", hour="6", minute="0"),
        },
        "fees-mark-overdue": {
            "task": "fees.mark_overdue",
            "schedule": crontab(hour="0", minute="30"),
        },
        "fees-send-due-reminders": {
            "task": "fees.send_due_reminders",
            "schedule": crontab(hour="9", minute="0"),
        },
        "leave-complete-finished": {
            "task": "leave.complete_finished",
            "schedule": crontab(hour="0", minute="45"),
        },
        "auth-purge-expired-refresh-tokens": {
            "task": "auth.purge_expired_refresh_tokens",
            "schedule": crontab(hour="3", minute="15"),
        },
    },
)
