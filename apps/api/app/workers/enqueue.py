"""Queue background tasks from the request path.

Tasks are sent by name, after the request's transaction commits. Sending by
name keeps the worker's task modules (and the AI SDK they import) out of the
API process; sending after commit guarantees the worker can see the rows the
task is about.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import after_commit
from app.core.logging import get_logger

log = get_logger("workers.enqueue")


def send_task(task_name: str, *args: str) -> None:
    """Send immediately. A broker outage is logged, never raised: the data is
    already stored, and every task here can be re-run or is swept up later."""
    from app.workers.celery_app import celery_app

    try:
        celery_app.send_task(task_name, args=list(args))
    except Exception as exc:  # noqa: BLE001
        log.error("task_enqueue_failed", task=task_name, args=list(args), error=str(exc))


def enqueue_after_commit(session: AsyncSession, task_name: str, *args: str) -> None:
    """Queue a task once the transaction commits. Identical requests within one
    transaction are sent once."""
    after_commit(session, lambda: send_task(task_name, *args), key=(task_name, args))
