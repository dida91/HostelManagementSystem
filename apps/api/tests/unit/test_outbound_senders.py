"""SMTP and Sparrow SMS senders: request shape and failure classification.

Nothing here reaches a real server: SMTP is replaced with a recording stand-in
and the SMS gateway with httpx.MockTransport.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest

from app.core.config import NotificationSettings
from app.integrations.base import DeliveryFailed
from app.integrations.email import SmtpEmailSender
from app.integrations.sms import SparrowSmsSender

TOKEN = "super-secret-token"  # noqa: S105 - test value


def _settings(**overrides: Any) -> NotificationSettings:
    base: dict[str, Any] = {
        "SMTP_HOST": "mail.test",
        "SMTP_PORT": 587,
        "SMTP_USERNAME": "mailer",
        "SMTP_PASSWORD": "mail-pass",
        "SMTP_SECURITY": "starttls",
        "EMAIL_FROM": "Kutumba Hostel <no-reply@kutumba.test>",
        "SMS_PROVIDER": "sparrow",
        "SPARROW_SMS_TOKEN": TOKEN,
        "SPARROW_SMS_FROM": "KUTUMBA",
        "SPARROW_SMS_URL": "https://sms.test/v2/sms/",
    }
    return NotificationSettings(**{**base, **overrides})


class RecordingSMTP:
    last: RecordingSMTP | None = None
    raise_on_send: Exception | None = None

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host, self.port = host, port
        self.tls = False
        self.login_args: tuple[str, str] | None = None
        self.messages: list[EmailMessage] = []
        RecordingSMTP.last = self

    def __enter__(self) -> RecordingSMTP:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def starttls(self, context: object = None) -> None:
        self.tls = True

    def login(self, user: str, password: str) -> None:
        self.login_args = (user, password)

    def send_message(self, msg: EmailMessage) -> None:
        if RecordingSMTP.raise_on_send:
            raise RecordingSMTP.raise_on_send
        self.messages.append(msg)


@pytest.fixture
def smtp(monkeypatch: pytest.MonkeyPatch) -> type[RecordingSMTP]:
    RecordingSMTP.last = None
    RecordingSMTP.raise_on_send = None
    monkeypatch.setattr(smtplib, "SMTP", RecordingSMTP)
    return RecordingSMTP


def test_email_is_sent_over_starttls_with_login(smtp: type[RecordingSMTP]) -> None:
    message_id = SmtpEmailSender(_settings()).send(
        to="sita@example.com", subject="Leave approved", text="नमस्ते! Your leave is approved."
    )
    server = smtp.last
    assert server is not None and server.tls and server.login_args == ("mailer", "mail-pass")
    msg = server.messages[0]
    assert msg["To"] == "sita@example.com" and msg["Subject"] == "Leave approved"
    assert "नमस्ते" in msg.get_content()
    assert message_id and message_id.endswith("@kutumba.test>")


def test_refused_recipient_is_permanent(smtp: type[RecordingSMTP]) -> None:
    smtp.raise_on_send = smtplib.SMTPRecipientsRefused({"x@y": (550, b"no such user")})
    with pytest.raises(DeliveryFailed) as err:
        SmtpEmailSender(_settings()).send(to="x@y", subject="s", text="t")
    assert err.value.permanent


def test_5xx_reply_is_permanent_4xx_is_not(smtp: type[RecordingSMTP]) -> None:
    smtp.raise_on_send = smtplib.SMTPDataError(554, b"rejected as spam")
    with pytest.raises(DeliveryFailed) as err:
        SmtpEmailSender(_settings()).send(to="a@b", subject="s", text="t")
    assert err.value.permanent and "554" in str(err.value)

    smtp.raise_on_send = smtplib.SMTPDataError(451, b"try again later")
    with pytest.raises(DeliveryFailed) as err:
        SmtpEmailSender(_settings()).send(to="a@b", subject="s", text="t")
    assert not err.value.permanent


def test_bad_credentials_are_retried_not_dropped(smtp: type[RecordingSMTP]) -> None:
    """A config error must not permanently fail every queued message."""
    smtp.raise_on_send = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    with pytest.raises(DeliveryFailed) as err:
        SmtpEmailSender(_settings()).send(to="a@b", subject="s", text="t")
    assert not err.value.permanent


def test_connection_failure_is_transient(smtp: type[RecordingSMTP]) -> None:
    smtp.raise_on_send = smtplib.SMTPServerDisconnected("gone")
    with pytest.raises(DeliveryFailed) as err:
        SmtpEmailSender(_settings()).send(to="a@b", subject="s", text="t")
    assert not err.value.permanent


def test_email_sender_refuses_to_exist_unconfigured() -> None:
    with pytest.raises(ValueError):
        SmtpEmailSender(_settings(SMTP_HOST=""))


# ---------------------------------------------------------------------- SMS


def _sms(handler: Any) -> SparrowSmsSender:
    return SparrowSmsSender(_settings(), transport=httpx.MockTransport(handler))


async def test_sms_request_shape_and_success() -> None:
    seen: dict[str, list[str]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(parse_qs(request.content.decode()))
        assert str(request.url) == "https://sms.test/v2/sms/"
        return httpx.Response(200, json={"count": 1, "response_code": 200, "response": "ok"})

    assert await _sms(handler).send(to="9812345678", text="Leave approved.") is None
    assert seen == {
        "token": [TOKEN],
        "from": ["KUTUMBA"],
        "to": ["9812345678"],
        "text": ["Leave approved."],
    }


async def test_sms_rejection_is_permanent_and_never_leaks_the_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"response_code": 1002, "response": "Invalid Token"})

    with pytest.raises(DeliveryFailed) as err:
        await _sms(handler).send(to="9812345678", text="x")
    assert err.value.permanent
    assert "1002" in str(err.value) and TOKEN not in str(err.value)


async def test_sms_gateway_errors_are_transient() -> None:
    def server_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="maintenance")

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    for handler in (server_error, unreachable):
        with pytest.raises(DeliveryFailed) as err:
            await _sms(handler).send(to="9812345678", text="x")
        assert not err.value.permanent
