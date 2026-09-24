"""Email/SMS delivery.

Triggered right after a notification commits, and every 30 seconds by beat
as a sweep for anything due for a retry or queued while the broker was down.
Concurrent runs are safe: deliveries are claimed with SKIP LOCKED.
"""

from __future__ import annotations

from app.core.db import AsyncSessionLocal
from app.core.logging import get_logger
from app.services.delivery import build_dispatcher
from app.workers.celery_app import celery_app
from app.workers.runtime import run_async

log = get_logger("workers.notifications")


@celery_app.task(name="notifications.dispatch", ignore_result=True)
def dispatch_notifications_task() -> dict[str, int]:
    dispatcher = build_dispatcher(AsyncSessionLocal)
    return run_async(dispatcher.dispatch()).as_dict()
