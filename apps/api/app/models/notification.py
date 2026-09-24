"""In-app notifications and their outbound email/SMS deliveries.

A notification is written in the SAME transaction as the change it describes
(a leave decision, an issued invoice), so a change that rolls back can never
announce itself.

Deliveries are an outbox: one row per channel, claimed and sent by the worker
after commit, retried with backoff. Nothing is lost if the broker is down when
the change is made -- a periodic sweep sends anything still PENDING.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey
from app.models.enums import DeliveryStatus, NotificationCategory, NotificationChannel


class Notification(UUIDPrimaryKey, Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[NotificationCategory] = mapped_column(
        Enum(NotificationCategory, name="notification_category"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # A path inside the web app, e.g. "/leave". Never an external URL.
    link: Mapped[str | None] = mapped_column(String(300))
    # Makes scheduled jobs safe to re-run: the same reminder for the same
    # invoice is recorded (and sent) at most once per user.
    dedupe_key: Mapped[str | None] = mapped_column(String(160))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    deliveries: Mapped[list[NotificationDelivery]] = relationship(
        back_populates="notification", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index(
            "ix_notifications_user_unread",
            "user_id",
            postgresql_where=text("read_at IS NULL"),
        ),
        Index(
            "uq_notifications_user_dedupe",
            "user_id",
            "dedupe_key",
            unique=True,
            postgresql_where=text("dedupe_key IS NOT NULL"),
        ),
    )


class NotificationDelivery(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "notification_deliveries"

    notification_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel, name="notification_channel"), nullable=False
    )
    # Address or number at the time the notification was raised, so the record
    # shows where a message actually went even if the profile changes later.
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    # Exactly what is sent on this channel (the email body, or the SMS text).
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DeliveryStatus] = mapped_column(
        Enum(DeliveryStatus, name="delivery_status"),
        default=DeliveryStatus.PENDING,
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Operator-facing only; never contains credentials.
    last_error: Mapped[str | None] = mapped_column(String(500))
    provider_message_id: Mapped[str | None] = mapped_column(String(200))

    notification: Mapped[Notification] = relationship(back_populates="deliveries")

    __table_args__ = (
        Index("ix_deliveries_due", "status", "next_attempt_at"),
        CheckConstraint("attempts >= 0", name="ck_delivery_attempts_nonneg"),
    )
