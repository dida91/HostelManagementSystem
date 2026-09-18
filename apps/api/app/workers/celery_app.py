"""Celery application.

Workers use the SYNCHRONOUS engine (see core/db.py). Async AI calls are bridged
at the task boundary with asyncio.run, which keeps a single event loop per task
instead of mixing loops with Celery's prefork model.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "hostel",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks.ai_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kathmandu",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=180,
    task_soft_time_limit=150,
    broker_connection_retry_on_startup=True,
)
