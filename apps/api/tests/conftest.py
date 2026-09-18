from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault("AI_REQUIRED", "false")

from app.core.db import AsyncSessionLocal, async_engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.models.user import Student, User  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine() -> AsyncIterator[None]:
    """Dispose pooled connections after every test.

    The async engine is module-level, but pytest-asyncio gives each test its own
    event loop. An asyncpg connection is bound to the loop that created it, so a
    pooled connection reused in the next test fails with "Event loop is closed".
    Disposing between tests keeps the pool loop-local.
    """
    yield
    await async_engine.dispose()


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def student_factory(session: AsyncSession):  # type: ignore[no-untyped-def]
    created: list[uuid.UUID] = []

    async def _make(role: UserRole = UserRole.STUDENT, password: str = "TestPass123!"):  # type: ignore[no-untyped-def]
        suffix = uuid.uuid4().hex[:8]
        user = User(
            email=f"{suffix}@test.local",
            full_name=f"Test {suffix}",
            password_hash=hash_password(password),
            role=role,
        )
        session.add(user)
        await session.flush()
        student = None
        if role is UserRole.STUDENT:
            student = Student(user_id=user.id, student_code=f"T-{suffix}")
            session.add(student)
            await session.flush()
        created.append(user.id)
        return user, student

    yield _make
