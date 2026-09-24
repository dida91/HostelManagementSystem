from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import DeliveryStatus, NotificationCategory, NotificationChannel
from app.schemas.common import ORMModel


class NotificationOut(ORMModel):
    id: uuid.UUID
    category: NotificationCategory
    title: str
    body: str
    link: str | None
    read_at: datetime | None
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    total: int
    unread: int
    limit: int
    offset: int


class ReadAllResult(BaseModel):
    updated: int


class DeliveryOut(ORMModel):
    id: uuid.UUID
    notification_id: uuid.UUID
    channel: NotificationChannel
    destination: str
    status: DeliveryStatus
    attempts: int
    next_attempt_at: datetime
    sent_at: datetime | None
    last_error: str | None
    created_at: datetime


class RetryResult(BaseModel):
    requeued: int
