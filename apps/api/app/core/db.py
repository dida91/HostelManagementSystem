"""Database engines and session factories.

Two engines on purpose:
  * async (asyncpg)  -> FastAPI request path
  * sync  (psycopg)  -> Celery workers. Celery tasks are synchronous; driving an
    async engine from them is a known source of event-loop bugs, so workers get
    their own synchronous sessionmaker against the same database.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Hashable, Iterator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("core.db")
_AFTER_COMMIT = "after_commit_callbacks"


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    type_annotation_map: dict[Any, Any] = {}


_settings = get_settings()

async_engine = create_async_engine(
    _settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=20, echo=False
)
AsyncSessionLocal = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)

sync_engine = create_engine(
    _settings.database_url_sync, pool_pre_ping=True, pool_size=5, max_overflow=10, echo=False
)
SyncSessionLocal = sessionmaker(
    sync_engine, class_=Session, expire_on_commit=False, autoflush=False
)


def after_commit(
    session: AsyncSession, callback: Callable[[], object], *, key: Hashable | None = None
) -> None:
    """Run `callback` once the session's transaction has committed.

    Background work must not be queued before the rows it reads are committed:
    a fast worker would look them up, find nothing, and silently give up.
    Callbacks are discarded if the transaction rolls back. Registering the same
    `key` twice keeps a single callback (e.g. one delivery run for a batch).
    """
    callbacks: dict[Hashable, Callable[[], object]] = session.info.setdefault(_AFTER_COMMIT, {})
    callbacks[key if key is not None else object()] = callback


def run_after_commit(session: AsyncSession) -> None:
    """Fire callbacks registered with after_commit(). Call only after a commit."""
    for callback in session.info.pop(_AFTER_COMMIT, {}).values():
        try:
            callback()
        except Exception as exc:  # noqa: BLE001 - the data is committed; never fail on this
            log.error("after_commit_callback_failed", error=str(exc))


def discard_after_commit(session: AsyncSession) -> None:
    session.info.pop(_AFTER_COMMIT, None)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one transaction per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            discard_after_commit(session)
            await session.rollback()
            raise
        run_after_commit(session)


def get_sync_session() -> Iterator[Session]:
    """Celery worker session."""
    with SyncSessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
