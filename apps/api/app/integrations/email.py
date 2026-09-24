"""SMTP email sender.

Blocking by design (smtplib). The dispatcher runs it in a worker thread, off
the event loop. One connection per message is plenty at hostel scale and means
a broken connection can never take a batch of messages down with it.
"""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr

from app.core.config import NotificationSettings
from app.integrations.base import DeliveryFailed


class SmtpEmailSender:
    def __init__(self, settings: NotificationSettings) -> None:
        if not settings.email_enabled:
            raise ValueError("SMTP is not configured (SMTP_HOST is empty).")
        self._s = settings

    def _connect(self) -> smtplib.SMTP:
        s = self._s
        assert s.smtp_host is not None
        if s.smtp_security == "ssl":
            return smtplib.SMTP_SSL(
                s.smtp_host,
                s.smtp_port,
                timeout=s.smtp_timeout_seconds,
                context=ssl.create_default_context(),
            )
        return smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout_seconds)

    def send(self, *, to: str, subject: str, text: str) -> str | None:
        s = self._s
        msg = EmailMessage()
        msg["From"] = s.email_from
        msg["To"] = to
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=False)
        sender_domain = parseaddr(s.email_from)[1].partition("@")[2] or None
        msg["Message-ID"] = make_msgid(domain=sender_domain)
        msg.set_content(text)  # UTF-8, so Nepali text survives

        try:
            with self._connect() as smtp:
                if s.smtp_security == "starttls":
                    smtp.starttls(context=ssl.create_default_context())
                if s.smtp_username:
                    password = s.smtp_password.get_secret_value() if s.smtp_password else ""
                    smtp.login(s.smtp_username, password)
                smtp.send_message(msg)
        except smtplib.SMTPRecipientsRefused as exc:
            raise DeliveryFailed(
                "The mail server refused the recipient address.", permanent=True
            ) from exc
        except smtplib.SMTPAuthenticationError as exc:
            # A configuration problem, not a property of this message: retry,
            # so messages go out once the credentials are fixed.
            raise DeliveryFailed(f"SMTP authentication failed ({exc.smtp_code}).") from exc
        except smtplib.SMTPResponseException as exc:
            raw = exc.smtp_error
            reply = raw.decode(errors="replace") if isinstance(raw, bytes) else str(raw or "")
            raise DeliveryFailed(
                f"SMTP error {exc.smtp_code}: {reply[:200]}",
                # 5xx replies are permanent by definition (RFC 5321 section 4.2.1).
                permanent=500 <= exc.smtp_code < 600,
            ) from exc
        except (smtplib.SMTPException, OSError) as exc:
            raise DeliveryFailed(
                f"Could not reach the mail server ({type(exc).__name__})."
            ) from exc
        return str(msg["Message-ID"])
