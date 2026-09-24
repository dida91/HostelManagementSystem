"""Sparrow SMS (Nepal) sender, HTTP API v2.

    POST {SPARROW_SMS_URL}  form fields: token, from, to, text
    success: HTTP 200, {"response_code": 200, "count": 1, "response": "..."}
    failure: HTTP 4xx, {"response_code": <code>, "response": "<reason>"}

The token is sent in the request body over HTTPS and is never logged or
stored; errors keep only the gateway's status and reason text.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import NotificationSettings
from app.integrations.base import DeliveryFailed


class SparrowSmsSender:
    def __init__(
        self,
        settings: NotificationSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        if not settings.sms_enabled:
            raise ValueError("Sparrow SMS is not configured.")
        assert settings.sparrow_sms_token is not None
        self._token = settings.sparrow_sms_token.get_secret_value()
        self._from = settings.sparrow_sms_from or ""
        self._url = settings.sparrow_sms_url
        self._transport = transport
        self._timeout = timeout_seconds

    async def send(self, *, to: str, text: str) -> str | None:
        data = {"token": self._token, "from": self._from, "to": to, "text": text}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.post(self._url, data=data)
        except httpx.HTTPError as exc:
            raise DeliveryFailed(f"SMS gateway unreachable ({type(exc).__name__}).") from exc

        try:
            payload: dict[str, Any] = response.json()
        except ValueError:
            payload = {}
        code = payload.get("response_code")
        if response.status_code == 200 and code == 200:
            return None  # the v2 API returns no per-message id

        reason = str(payload.get("response") or response.reason_phrase)[:200]
        raise DeliveryFailed(
            f"SMS gateway rejected the message (HTTP {response.status_code}, code {code}): "
            f"{reason}",
            # A 4xx describes this request (bad number, bad sender id); retrying
            # the identical request cannot succeed. 429 and 5xx are transient.
            permanent=400 <= response.status_code < 500 and response.status_code != 429,
        )
