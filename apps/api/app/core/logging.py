"""Structured JSON logging with secret redaction."""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import MutableMapping
from contextvars import ContextVar
from typing import Any

import structlog

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)

# Patterns that must never reach a log sink.
_REDACT_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),  # Google API keys
    re.compile(r"(?i)(api[_-]?key\"?\s*[:=]\s*)\S+"),
    re.compile(r"(?i)(authorization\"?\s*[:=]\s*)\S+"),
    re.compile(r"(?i)(password\"?\s*[:=]\s*)\S+"),
]
_SENSITIVE_KEYS = {
    "api_key",
    "gemini_api_key",
    "password",
    "authorization",
    "token",
    "access_token",
    "refresh_token",
    "secret_key",
    "password_hash",
}


def _redact(
    _logger: Any, _name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in list(event_dict):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "[REDACTED]"
        elif isinstance(event_dict[key], str):
            val = event_dict[key]
            for pat in _REDACT_PATTERNS:
                val = pat.sub(
                    lambda m: (m.group(1) + "[REDACTED]") if m.groups() else "[REDACTED]", val
                )
            event_dict[key] = val
    return event_dict


def _add_context(
    _logger: Any, _name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    if rid := request_id_ctx.get():
        event_dict.setdefault("request_id", rid)
    if uid := user_id_ctx.get():
        event_dict.setdefault("user_id", uid)
    return event_dict


def configure_logging(*, debug: bool = False) -> None:
    logging.basicConfig(
        format="%(message)s", stream=sys.stdout, level=logging.DEBUG if debug else logging.INFO
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_context,
            _redact,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    return structlog.get_logger(name)
