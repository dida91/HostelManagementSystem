from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

os.environ.setdefault("AI_REQUIRED", "false")
# Tests never publish to the real broker: a task queued there would be picked up
# by a developer's running worker and executed against real services (and a
# real Gemini quota) long after the test finished.
os.environ["CELERY_BROKER_URL"] = "memory://"
os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"
# Outbound email/SMS stay off unless a test switches them on explicitly.
os.environ["SMTP_HOST"] = ""
os.environ["SMS_PROVIDER"] = "none"

from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import Settings  # noqa: E402

# Integration tests run against their own database, rebuilt from migrations and
# the seed at the start of every run (tests/integration/conftest.py), so they
# neither depend on nor pollute the development data.
TEST_DATABASE = "hostel_test"
_configured = Settings()
for _var, _url in (
    ("DATABASE_URL", _configured.database_url),
    ("DATABASE_URL_SYNC", _configured.database_url_sync),
):
    os.environ[_var] = (
        make_url(_url).set(database=TEST_DATABASE).render_as_string(hide_password=False)
    )

from app.core.db import AsyncSessionLocal, async_engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.models.user import Student, User  # noqa: E402


@pytest.fixture
def ai_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the AI provider to report itself unconfigured.

    Without this, the degradation tests would pass only on machines with no
    GEMINI_API_KEY and would start making real API calls on machines that have
    one.
    """
    for module in (
        "app.api.v1.assistant",
        "app.api.v1.analytics",
    ):
        monkeypatch.setattr(f"{module}.ai_is_available", lambda: False)


@pytest_asyncio.fixture(autouse=True)
async def _reset_rate_limits() -> AsyncIterator[None]:
    """Clear rate-limit and circuit-breaker state between tests.

    The limiter is real shared infrastructure, so without this the suite
    throttles its own repeated logins. Resetting keys keeps the real limiter
    under test while making each test independent -- the same reasoning as
    rolling back the database between tests.
    """
    from app.core.ratelimit import get_redis

    async def _flush() -> None:
        try:
            redis = get_redis()
            for pattern in ("rl:*", "cb:*"):
                if keys := [k async for k in redis.scan_iter(match=pattern)]:
                    await redis.delete(*keys)
        except Exception:  # noqa: BLE001 - tests must run without redis too
            pass

    await _flush()
    yield
    await _flush()


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
