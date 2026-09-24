"""Interfaces for outbound message senders."""

from __future__ import annotations

from typing import Protocol


class DeliveryFailed(Exception):  # noqa: N818 - reads naturally at the raise site
    """A send attempt failed.

    `permanent` means retrying cannot help (the address was refused, the
    request itself was invalid); anything else is retried with backoff. The
    message is stored for operators, so it must never contain a credential.
    """

    def __init__(self, message: str, *, permanent: bool = False) -> None:
        super().__init__(message)
        self.permanent = permanent


class EmailSender(Protocol):
    def send(self, *, to: str, subject: str, text: str) -> str | None:
        """Send one plain-text email. Blocking. Returns a message id if known."""
        ...


class SmsSender(Protocol):
    async def send(self, *, to: str, text: str) -> str | None:
        """Send one SMS. Returns the provider's message id if it gives one."""
        ...
