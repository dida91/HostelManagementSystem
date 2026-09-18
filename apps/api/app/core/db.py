"""Database engines and session factories.

Two engines on purpose:
  * async (asyncpg)  -> FastAPI request path
  * sync  (psycopg)  -> Celery workers. Celery tasks are synchronous; driving an
    async engine from them is a known source of event-loop bugs, so workers get
    their own synchronous sessionmaker against the same database.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


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


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one transaction per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_sync_session() -> Iterator[Session]:
    """Celery worker session."""
    with SyncSessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
