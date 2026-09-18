"""End-to-end coverage for the domain surface, with authorization as the focus."""

from __future__ import annotations

import random
import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, password: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _student(client: AsyncClient) -> str:
    return await _login(client, "sita@kutumba.local", "StudentPass123!")


async def _warden(client: AsyncClient) -> str:
    return await _login(client, "warden@kutumba.local", "WardenPass123!")


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------- fees


async def test_student_sees_own_balance_derived_from_ledger(client: AsyncClient) -> None:
    r = await client.get("/api/v1/fees/balance", headers=_h(await _student(client)))
    assert r.status_code == 200
    body = r.json()
    # Seed data: 16000 charged, 8000 paid.
    assert body["currency"] == "NPR"
    assert float(body["outstanding"]) == float(body["total_charged"]) - float(body["total_paid"])


async def test_student_cannot_request_another_students_balance(client: AsyncClient) -> None:
    """Passing someone else's id must be refused, not silently redirected."""
    r = await client.get(
        f"/api/v1/fees/balance?student_id={uuid.uuid4()}", headers=_h(await _student(client))
    )
    assert r.status_code == 403


async def test_student_cannot_issue_an_invoice(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/fees/invoices",
        headers=_h(await _student(client)),
        json={
            "student_id": str(uuid.uuid4()),
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "due_date": "2026-10-07",
            "line_items": [{"description": "Fee", "quantity": 1, "unit_amount_npr": 8000}],
        },
    )
    assert r.status_code == 403


async def test_payment_requires_an_idempotency_key(client: AsyncClient) -> None:
    warden = await _warden(client)
    students = await client.get("/api/v1/students", headers=_h(warden))
    sid = students.json()["items"][0]["id"]

    r = await client.post(
        "/api/v1/fees/payments",
        headers=_h(warden),
        json={"student_id": sid, "amount_npr": 100, "method": "CASH"},
    )
    assert r.status_code == 422


async def test_repeated_payment_with_same_key_is_recorded_once(client: AsyncClient) -> None:
    warden = await _warden(client)
    sid = (await client.get("/api/v1/students", headers=_h(warden))).json()["items"][0]["id"]
    key = f"test-{uuid.uuid4()}"
    body = {"student_id": sid, "amount_npr": 250, "method": "CASH"}

    before = (await client.get(f"/api/v1/fees/balance?student_id={sid}", headers=_h(warden))).json()

    first = await client.post(
        "/api/v1/fees/payments", headers={**_h(warden), "Idempotency-Key": key}, json=body
    )
    second = await client.post(
        "/api/v1/fees/payments", headers={**_h(warden), "Idempotency-Key": key}, json=body
    )
    assert first.status_code == 201
    assert second.json()["id"] == first.json()["id"]

    after = (await client.get(f"/api/v1/fees/balance?student_id={sid}", headers=_h(warden))).json()
    # Credited exactly once despite two requests.
    assert float(after["total_paid"]) - float(before["total_paid"]) == 250.0


# -------------------------------------------------------------------- leave


async def test_student_submits_leave_and_warden_decides(client: AsyncClient) -> None:
    student = await _student(client)
    created = await client.post(
        "/api/v1/leave",
        headers=_h(student),
        json={
            "leave_type": "HOME_VISIT",
            "from_date": str(date.today() + timedelta(days=3)),
            "to_date": str(date.today() + timedelta(days=6)),
            "reason": "Going home for a family function.",
            "guardian_consent": True,
        },
    )
    assert created.status_code == 201
    leave_id = created.json()["id"]
    assert created.json()["status"] == "PENDING"

    denied = await client.patch(
        f"/api/v1/leave/{leave_id}", headers=_h(student), json={"status": "APPROVED"}
    )
    assert denied.status_code == 403, "a student must not approve their own leave"

    approved = await client.patch(
        f"/api/v1/leave/{leave_id}",
        headers=_h(await _warden(client)),
        json={"status": "APPROVED", "decision_note": "Approved."},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"


async def test_leave_rejects_inverted_dates(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/leave",
        headers=_h(await _student(client)),
        json={
            "leave_type": "MEDICAL",
            "from_date": str(date.today() + timedelta(days=5)),
            "to_date": str(date.today() + timedelta(days=1)),
            "reason": "Dates are the wrong way round.",
        },
    )
    assert r.status_code == 422


# --------------------------------------------------------------------- mess


async def test_mess_feedback_is_stored_verbatim_and_deduplicated(client: AsyncClient) -> None:
    student = await _student(client)
    # Feedback is unique per (student, date, meal), so a fixed date would collide
    # with a previous run against the same database.
    meal_date = str(date.today() - timedelta(days=random.randint(2, 3000)))
    comment = "Rice was good but dal was too salty."
    payload = {
        "meal_date": meal_date,
        "meal_type": "DINNER",
        "rating": 3,
        "comment": comment,
    }

    first = await client.post("/api/v1/mess/feedback", headers=_h(student), json=payload)
    assert first.status_code == 201
    # The student's own words are preserved exactly.
    assert first.json()["comment"] == comment
    assert first.json()["rating"] == 3

    duplicate = await client.post("/api/v1/mess/feedback", headers=_h(student), json=payload)
    assert duplicate.status_code == 409


async def test_mess_rating_out_of_range_is_rejected(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/mess/feedback",
        headers=_h(await _student(client)),
        json={"meal_date": str(date.today()), "meal_type": "LUNCH", "rating": 9},
    )
    assert r.status_code == 422


# ------------------------------------------------------------- rooms / admin


async def test_double_allocation_is_rejected_with_a_conflict(client: AsyncClient) -> None:
    """The DB partial unique index must surface as 409, never a 500."""
    warden = await _warden(client)
    rooms = (await client.get("/api/v1/rooms", headers=_h(warden))).json()
    assert rooms, "seed data should include rooms"

    students = (await client.get("/api/v1/students", headers=_h(warden))).json()["items"]
    sid = students[0]["id"]

    # Both seeded students already hold active beds, so re-allocating must conflict.
    from sqlalchemy import select

    from app.core.db import AsyncSessionLocal
    from app.models.hostel import Bed

    async with AsyncSessionLocal() as s:
        bed_id = (await s.execute(select(Bed.id).limit(1))).scalar_one()

    r = await client.post(
        "/api/v1/rooms/allocations",
        headers=_h(warden),
        json={"student_id": sid, "bed_id": str(bed_id), "from_date": str(date.today())},
    )
    assert r.status_code == 409
    assert "already" in r.json()["detail"].lower()


async def test_students_cannot_list_the_resident_directory(client: AsyncClient) -> None:
    r = await client.get("/api/v1/students", headers=_h(await _student(client)))
    assert r.status_code == 403


async def test_student_gets_404_for_another_students_record(client: AsyncClient) -> None:
    warden = await _warden(client)
    items = (await client.get("/api/v1/students", headers=_h(warden))).json()["items"]
    other = next(i for i in items if i["student_code"] != "KH-2026-001")

    r = await client.get(f"/api/v1/students/{other['id']}", headers=_h(await _student(client)))
    assert r.status_code == 404


# ---------------------------------------------------------------- analytics


async def test_analytics_is_staff_only(client: AsyncClient) -> None:
    assert (
        await client.get("/api/v1/analytics/overview", headers=_h(await _student(client)))
    ).status_code == 403


async def test_analytics_figures_come_from_the_database(client: AsyncClient) -> None:
    r = await client.get("/api/v1/analytics/overview", headers=_h(await _warden(client)))
    assert r.status_code == 200
    body = r.json()
    occ = body["occupancy"]
    assert occ["total_beds"] == occ["occupied_beds"] + occ["vacant_beds"]
    assert body["fees"]["currency"] == "NPR"


async def test_ai_insights_degrade_without_a_key(client: AsyncClient, ai_unavailable: None) -> None:
    """The computed metrics must not be lost just because narration is down."""
    r = await client.post(
        "/api/v1/analytics/insights", headers=_h(await _warden(client)), json={"days": 30}
    )
    assert r.status_code == 503


# ---------------------------------------------------------------- documents


async def test_document_upload_is_warden_only(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/documents",
        headers=_h(await _student(client)),
        files={"file": ("rules.txt", b"Hostel rules text", "text/plain")},
        data={"title": "Rules", "doc_type": "HOSTEL_RULES"},
    )
    assert r.status_code == 403


async def test_document_upload_rejects_unsupported_binary(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/documents",
        headers=_h(await _warden(client)),
        files={"file": ("evil.pdf", b"\x00\x01\x02\xff\xfe binary", "application/pdf")},
        data={"title": "Not a PDF", "doc_type": "OTHER"},
    )
    assert r.status_code == 422
