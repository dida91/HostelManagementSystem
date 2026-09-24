"""Running async code inside Celery tasks.

Celery's prefork pool runs tasks synchronously, one at a time per child
process. The async engine's connection pool, the Redis client and the Gemini
SDK's HTTP client are process-wide, and each binds to the event loop it was
first used on. Creating a fresh loop per task (asyncio.run) therefore breaks
the SECOND task in every process with "Event loop is closed" or "attached to a
different loop" -- which is exactly how queued complaint analyses were failing.

So each worker process keeps ONE event loop for its whole life, created after
the fork. This requires the prefork (default) or solo pool, not threads/gevent.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

from celery.signals import worker_process_init
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import (
    AsyncSessionLocal,
    async_engine,
    discard_after_commit,
    run_after_commit,
    sync_engine,
)

_loop: asyncio.AbstractEventLoop | None = None


def _worker_loop() -> asyncio.AbstractEventLoop:
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    return _loop


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine to completion on this process's long-lived loop."""
    loop = _worker_loop()
    task = loop.create_task(coro)
    try:
        return loop.run_until_complete(task)
    except BaseException:
        # e.g. Celery's SoftTimeLimitExceeded, raised from a signal handler while
        # the loop is running. Cancel the task so it cannot resume on the next run.
        if not task.done():
            task.cancel()
            with contextlib.suppress(BaseException):
                loop.run_until_complete(task)
        raise


async def run_in_transaction[T](work: Callable[[AsyncSession], Awaitable[T]]) -> T:
    """One committed transaction for a background job, with after-commit
    callbacks (e.g. queued notification delivery) fired only on success."""
    async with AsyncSessionLocal() as session:
        try:
            result = await work(session)
            await session.commit()
        except BaseException:
            discard_after_commit(session)
            await session.rollback()
            raise
        run_after_commit(session)
        return result


def shutdown() -> None:
    """Close this process's loop. Used by tests; workers simply exit."""
    global _loop
    if _loop is not None and not _loop.is_closed():
        _loop.run_until_complete(async_engine.dispose())
        _loop.close()
    _loop = None


@worker_process_init.connect
def _reset_after_fork(**_kwargs: Any) -> None:
    """A forked child must not reuse the parent's loop or pooled connections."""
    global _loop
    _loop = None
    async_engine.sync_engine.dispose(close=False)
    sync_engine.dispose(close=False)
