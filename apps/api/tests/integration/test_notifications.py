"""Notifications raised by domain events, the inbox API, and the outbox rules."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from api_helpers import h, login, mina, new_student, notifications, sita, warden
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.models.enums import NotificationChannel
from app.models.notification import Notification, NotificationDelivery
from app.services.announcements import AnnouncementService

pytestmark = pytest.mark.asyncio


async def _leave(client: AsyncClient, student: dict[str, str]) -> str:
    r = await client.post(
        "/api/v1/leave",
        headers=student,
        json={
            "leave_type": "HOME_VISIT",
            "from_date": str(date.today() + timedelta(days=3)),
            "to_date": str(date.today() + timedelta(days=5)),
            "reason": "Family function at home in Syangja.",
            "guardian_consent": True,
        },
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def test_leave_request_and_decision_notify_both_sides(client: AsyncClient) -> None:
    student = await sita(client)
    leave_id = await _leave(client, student)

    staff = await warden(client)
    requests = [n for n in await notifications(client, staff) if n["category"] == "LEAVE_REQUESTED"]
    assert any("Sita" in n["title"] for n in requests)

    decided = await client.patch(
        f"/api/v1/leave/{leave_id}",
        headers=staff,
        json={"status": "REJECTED", "decision_note": "Exams that week."},
    )
    assert decided.status_code == 200
    decision = next(
        n for n in await notifications(client, student) if n["category"] == "LEAVE_DECIDED"
    )
    assert "rejected" in decision["body"] and "Exams that week." in decision["body"]


async def test_a_decision_must_approve_or_reject(client: AsyncClient) -> None:
    leave_id = await _leave(client, await sita(client))
    r = await client.patch(
        f"/api/v1/leave/{leave_id}", headers=await warden(client), json={"status": "COMPLETED"}
    )
    assert r.status_code == 422


async def test_complaint_status_change_notifies_the_resident(client: AsyncClient) -> None:
    student = await sita(client)
    cid = (
        await client.post(
            "/api/v1/complaints",
            headers=student,
            json={"text": "The geyser on the second floor has stopped working."},
        )
    ).json()["id"]
    r = await client.patch(
        f"/api/v1/complaints/{cid}",
        headers=await warden(client),
        json={"status": "RESOLVED", "note": "Internal: replaced heating element."},
    )
    assert r.status_code == 200
    update = next(
        n for n in await notifications(client, student) if n["category"] == "COMPLAINT_UPDATED"
    )
    assert "resolved" in update["body"]
    assert "heating element" not in update["body"], "the staff note stays internal"


async def test_inbox_is_private_and_can_be_marked_read(client: AsyncClient) -> None:
    student = await sita(client)
    await _leave(client, student)
    staff = await warden(client)
    theirs = (await notifications(client, staff))[0]

    stolen = await client.post(f"/api/v1/notifications/{theirs['id']}/read", headers=student)
    assert stolen.status_code == 404

    page = (await client.get("/api/v1/notifications?unread_only=true", headers=staff)).json()
    assert page["unread"] >= 1 and all(n["read_at"] is None for n in page["items"])

    read = await client.post(f"/api/v1/notifications/{theirs['id']}/read", headers=staff)
    assert read.status_code == 200 and read.json()["read_at"] is not None

    await client.post("/api/v1/notifications/read-all", headers=staff)
    assert (await client.get("/api/v1/notifications", headers=staff)).json()["unread"] == 0


async def test_announcements_respect_their_audience(client: AsyncClient) -> None:
    staff = await warden(client)
    tag = uuid.uuid4().hex[:6]
    for audience in ("STUDENTS", "STAFF"):
        r = await client.post(
            "/api/v1/announcements",
            headers=staff,
            json={"title": f"{audience} notice {tag}", "body": "Details.", "audience": audience},
        )
        assert r.status_code == 201, r.text
        assert r.json()["notified_at"] is not None

    student = await mina(client)
    visible = [
        a["title"] for a in (await client.get("/api/v1/announcements", headers=student)).json()
    ]
    assert f"STUDENTS notice {tag}" in visible
    assert f"STAFF notice {tag}" not in visible, "staff-only notices are hidden from residents"

    notified = [n["title"] for n in await notifications(client, student)]
    assert f"Notice: STUDENTS notice {tag}" in notified
    assert f"Notice: STAFF notice {tag}" not in notified


async def test_scheduled_announcement_is_notified_once_when_due(client: AsyncClient) -> None:
    staff = await warden(client)
    publish_at = datetime.now(UTC) + timedelta(hours=2)
    created = await client.post(
        "/api/v1/announcements",
        headers=staff,
        json={
            "title": f"Scheduled {uuid.uuid4().hex[:6]}",
            "body": "Visitors' day is Saturday.",
            "publish_at": publish_at.isoformat(),
        },
    )
    assert created.status_code == 201
    assert created.json()["notified_at"] is None
    student = await mina(client)
    titles = [
        a["title"] for a in (await client.get("/api/v1/announcements", headers=student)).json()
    ]
    assert created.json()["title"] not in titles, "not visible before publish time"

    later = publish_at + timedelta(minutes=1)
    for _ in range(2):  # the scheduler may run twice; residents hear once
        async with AsyncSessionLocal() as s:
            await AnnouncementService(s).publish_due(now=later)
            await s.commit()

    matching = [
        n
        for n in await notifications(client, student)
        if n["title"] == f"Notice: {created.json()['title']}"
    ]
    assert len(matching) == 1


async def test_announcement_edit_and_delete(client: AsyncClient) -> None:
    staff = await warden(client)
    a = (
        await client.post(
            "/api/v1/announcements", headers=staff, json={"title": "Typo notcie", "body": "Body."}
        )
    ).json()
    edited = await client.patch(
        f"/api/v1/announcements/{a['id']}", headers=staff, json={"title": "Typo notice"}
    )
    assert edited.status_code == 200 and edited.json()["title"] == "Typo notice"

    bad_window = await client.patch(
        f"/api/v1/announcements/{a['id']}",
        headers=staff,
        json={"expires_at": "2000-01-01T00:00:00Z"},
    )
    assert bad_window.status_code == 422

    assert (
        await client.patch(
            f"/api/v1/announcements/{a['id']}", headers=await sita(client), json={"title": "Hacked"}
        )
    ).status_code == 403
    assert (
        await client.delete(f"/api/v1/announcements/{a['id']}", headers=staff)
    ).status_code == 204


async def test_outbox_rows_follow_channel_configuration(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Email for every message once SMTP is set; SMS only for messages that
    carry SMS text, and only to a valid Nepali mobile."""
    notify = get_settings().notify
    monkeypatch.setattr(notify, "smtp_host", "mail.test")
    monkeypatch.setattr(notify, "sms_provider", "sparrow")
    monkeypatch.setattr(notify, "sparrow_sms_token", SecretStr("test-token"))
    monkeypatch.setattr(notify, "sparrow_sms_from", "KUTUMBA")

    staff = await warden(client)
    student, password = await new_student(client, staff, phone="+977-981-2345678")
    resident = h(await login(client, student["email"], password))
    leave = await _leave(client, resident)
    await client.patch(f"/api/v1/leave/{leave}", headers=staff, json={"status": "APPROVED"})

    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(
                select(Notification.category, NotificationDelivery)
                .join(NotificationDelivery, NotificationDelivery.notification_id == Notification.id)
                .where(NotificationDelivery.destination.in_([student["email"], "9812345678"]))
            )
        ).all()
    by_channel = {d.channel: (category, d) for category, d in rows}
    assert set(by_channel) == {NotificationChannel.EMAIL, NotificationChannel.SMS}
    email = by_channel[NotificationChannel.EMAIL][1]
    assert "/leave" in email.content and "approved" in email.content
    sms_category, sms = by_channel[NotificationChannel.SMS]
    assert sms_category.value == "LEAVE_DECIDED"
    assert sms.destination == "9812345678" and len(sms.content) <= 160


async def test_staff_see_who_requested_leave(client: AsyncClient) -> None:
    await _leave(client, await sita(client))
    items = (await client.get("/api/v1/leave?status=PENDING", headers=await warden(client))).json()[
        "items"
    ]
    mine = [i for i in items if i["student_code"] == "KH-2026-001"]
    assert mine and mine[0]["student_name"] == "Sita Gurung"


async def test_triage_can_filter_complaints_by_status(client: AsyncClient) -> None:
    student = await sita(client)
    cid = (
        await client.post(
            "/api/v1/complaints",
            headers=student,
            json={"text": "Bathroom tap on floor two keeps dripping all night."},
        )
    ).json()["id"]
    staff = await warden(client)
    await client.patch(f"/api/v1/complaints/{cid}", headers=staff, json={"status": "CLOSED"})

    open_ = await client.get(
        "/api/v1/complaints?status=SUBMITTED&status=TRIAGED&status=IN_PROGRESS&limit=100",
        headers=staff,
    )
    assert open_.status_code == 200
    assert cid not in {c["id"] for c in open_.json()["items"]}
    assert all(
        c["status"] in {"SUBMITTED", "TRIAGED", "IN_PROGRESS"} for c in open_.json()["items"]
    )

    closed = await client.get("/api/v1/complaints?status=CLOSED&limit=100", headers=staff)
    assert cid in {c["id"] for c in closed.json()["items"]}
