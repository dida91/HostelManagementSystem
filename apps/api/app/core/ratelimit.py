"""Redis-backed rate limiting and an AI circuit breaker.

Both are shared across processes: a per-process limiter would let N workers each
allow the full quota, and a per-process breaker would keep hammering a failing
model from every other worker.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.errors import RateLimitedError
from app.core.logging import get_logger

log = get_logger("core.ratelimit")

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    return _client


@dataclass(slots=True)
class Limit:
    requests: int
    window_seconds: int


# AI endpoints are limited far more tightly than ordinary reads: they cost money
# and quota, and a runaway client would exhaust the shared Gemini budget.
LIMITS = {
    "ai": Limit(requests=20, window_seconds=60),
    "auth": Limit(requests=10, window_seconds=60),
    "default": Limit(requests=120, window_seconds=60),
}


async def enforce_rate_limit(*, key: str, bucket: str = "default") -> None:
    """Fixed-window counter. Fails OPEN if Redis is unreachable.

    Rationale: Redis being down must not lock residents out of filing a
    complaint. The failure is logged so it is visible.
    """
    limit = LIMITS.get(bucket, LIMITS["default"])
    window = int(time.time()) // limit.window_seconds
    redis_key = f"rl:{bucket}:{key}:{window}"

    try:
        redis = get_redis()
        count = await redis.incr(redis_key)
        if count == 1:
            await redis.expire(redis_key, limit.window_seconds * 2)
    except Exception as exc:  # noqa: BLE001
        log.warning("rate_limit_backend_unavailable", error=str(exc), bucket=bucket)
        return

    if count > limit.requests:
        log.warning("rate_limited", bucket=bucket, key=key, count=count)
        raise RateLimitedError(f"Too many requests. Try again in {limit.window_seconds} seconds.")


class CircuitBreaker:
    """Shared breaker for an upstream model.

    After `threshold` consecutive failures the circuit opens for `cooldown`
    seconds and calls fail fast instead of queueing behind a dead upstream.
    """

    def __init__(self, *, name: str, threshold: int = 5, cooldown_seconds: int = 60) -> None:
        self._name = name
        self._threshold = threshold
        self._cooldown = cooldown_seconds

    @property
    def _fail_key(self) -> str:
        return f"cb:{self._name}:failures"

    @property
    def _open_key(self) -> str:
        return f"cb:{self._name}:open"

    async def is_open(self) -> bool:
        try:
            return bool(await get_redis().exists(self._open_key))
        except Exception:  # noqa: BLE001 - never let the breaker itself break the call
            return False

    async def record_success(self) -> None:
        try:
            await get_redis().delete(self._fail_key)
        except Exception as exc:  # noqa: BLE001
            # Breaker bookkeeping must never fail a successful call.
            log.debug("breaker_success_record_failed", breaker=self._name, error=str(exc))

    async def record_failure(self) -> None:
        try:
            redis = get_redis()
            failures = await redis.incr(self._fail_key)
            await redis.expire(self._fail_key, self._cooldown * 2)
            if failures >= self._threshold:
                await redis.setex(self._open_key, self._cooldown, "1")
                log.error(
                    "circuit_opened",
                    breaker=self._name,
                    failures=failures,
                    cooldown_seconds=self._cooldown,
                )
        except Exception as exc:  # noqa: BLE001
            # Breaker bookkeeping must never mask the original upstream error.
            log.debug("breaker_failure_record_failed", breaker=self._name, error=str(exc))
