from __future__ import annotations

import pytest

from app.ai.providers.gemini import classify_error
from app.models.enums import AIErrorCategory


@pytest.mark.parametrize(
    ("exc", "category", "retryable"),
    [
        (TimeoutError(), AIErrorCategory.TIMEOUT, True),
        (Exception("429 RESOURCE_EXHAUSTED: quota"), AIErrorCategory.RATE_LIMITED, True),
        (Exception("503 Service unavailable"), AIErrorCategory.UNAVAILABLE, True),
        (Exception("API key not valid"), AIErrorCategory.AUTH, False),
        (Exception("blocked by safety filter"), AIErrorCategory.SAFETY_BLOCKED, False),
    ],
)
def test_classification_and_retry_policy(exc, category, retryable) -> None:  # type: ignore[no-untyped-def]
    err = classify_error(exc)
    assert err.category is category
    assert err.retryable is retryable


def test_auth_errors_are_never_retried() -> None:
    """Retrying a bad key burns quota and hides the real problem."""
    assert classify_error(Exception("401 unauthenticated")).retryable is False
