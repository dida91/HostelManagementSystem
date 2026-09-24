"""Resident lifecycle: profile edits, deactivation, password resets and changes."""

from __future__ import annotations

import pytest
from api_helpers import h, login, new_room, new_student, notifications, sita, warden
from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.user import AuditLog

pytestmark = pytest.mark.asyncio


async def test_duplicate_registration_is_a_conflict_not_a_crash(client: AsyncClient) -> None:
    staff = await warden(client)
    student, _ = await new_student(client, staff)
    again = await client.post(
        "/api/v1/students",
        headers=staff,
        json={
            "full_name": "Someone Else",
            "email": student["email"].upper(),  # emails are case-insensitive
            "initial_password": "AnotherPass123!",
            "student_code": "T-other-code",
        },
    )
    assert again.status_code == 409


async def test_profile_edit_is_applied_and_audited(client: AsyncClient) -> None:
    staff = await warden(client)
    student, _ = await new_student(client, staff)

    r = await client.patch(
        f"/api/v1/students/{student['id']}",
        headers=staff,
        json={"college": "Pokhara University", "guardian_phone": "9800000001", "phone": None},
    )
    assert r.status_code == 200, r.text
    assert r.json()["college"] == "Pokhara University"
    assert r.json()["guardian_phone"] == "9800000001"

    async with AsyncSessionLocal() as s:
        audit = (
            await s.execute(
                select(AuditLog).where(
                    AuditLog.entity_id == student["id"], AuditLog.action == "student.update"
                )
            )
        ).scalar_one()
    assert audit.after == {"college": "Pokhara University", "guardian_phone": "9800000001"}


async def test_profile_edit_to_a_taken_email_is_a_conflict(client: AsyncClient) -> None:
    staff = await warden(client)
    first, _ = await new_student(client, staff)
    second, _ = await new_student(client, staff)
    r = await client.patch(
        f"/api/v1/students/{second['id']}", headers=staff, json={"email": first["email"]}
    )
    assert r.status_code == 409


async def test_students_cannot_edit_records(client: AsyncClient) -> None:
    me = (await client.get("/api/v1/auth/me", headers=await sita(client))).json()
    r = await client.patch(
        f"/api/v1/students/{me['student_id']}",
        headers=await sita(client),
        json={"college": "Somewhere"},
    )
    assert r.status_code == 403


async def test_checkout_disables_login_and_frees_the_bed(client: AsyncClient) -> None:
    staff = await warden(client)
    room = await new_room(client, staff)
    student, password = await new_student(client, staff)
    await client.post(
        "/api/v1/rooms/allocations",
        headers=staff,
        json={
            "student_id": student["id"],
            "bed_id": room["beds"][0]["id"],
            "from_date": "2026-08-01",
        },
    )
    session = await client.post(
        "/api/v1/auth/login", json={"email": student["email"], "password": password}
    )
    refresh_token = session.json()["refresh_token"]

    r = await client.post(
        f"/api/v1/students/{student['id']}/deactivate",
        headers=staff,
        json={"status": "ALUMNI", "reason": "Graduated and moved out."},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["student"]["status"] == "ALUMNI" and body["student"]["is_active"] is False
    assert body["ended_assignment_id"] is not None
    assert body["student"]["room"] is None

    # Sign-in is refused, and the existing session cannot be refreshed.
    denied = await client.post(
        "/api/v1/auth/login", json={"email": student["email"], "password": password}
    )
    assert denied.status_code == 401
    stale = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert stale.status_code == 401

    detail = (await client.get(f"/api/v1/rooms/{room['id']}", headers=staff)).json()
    assert detail["beds"][0]["status"] == "VACANT" and detail["beds"][0]["occupant"] is None

    back = await client.post(f"/api/v1/students/{student['id']}/reactivate", headers=staff)
    assert back.status_code == 200 and back.json()["is_active"] is True
    assert await login(client, student["email"], password)


async def test_deactivation_only_accepts_alumni_or_suspended(client: AsyncClient) -> None:
    staff = await warden(client)
    student, _ = await new_student(client, staff)
    r = await client.post(
        f"/api/v1/students/{student['id']}/deactivate",
        headers=staff,
        json={"status": "ACTIVE", "reason": "Not a deactivation."},
    )
    assert r.status_code == 422


async def test_warden_password_reset(client: AsyncClient) -> None:
    staff = await warden(client)
    student, old_password = await new_student(client, staff)

    r = await client.post(
        f"/api/v1/students/{student['id']}/reset-password",
        headers=staff,
        json={"new_password": "BrandNewPass456!"},
    )
    assert r.status_code == 204

    old = await client.post(
        "/api/v1/auth/login", json={"email": student["email"], "password": old_password}
    )
    assert old.status_code == 401
    resident = h(await login(client, student["email"], "BrandNewPass456!"))
    assert "ACCOUNT_SECURITY" in [n["category"] for n in await notifications(client, resident)]

    async with AsyncSessionLocal() as s:
        audit = (
            await s.execute(
                select(AuditLog).where(
                    AuditLog.entity_id == student["id"],
                    AuditLog.action == "student.password_reset",
                )
            )
        ).scalar_one()
    assert "BrandNewPass456!" not in str(audit.after) + str(audit.before)


async def test_change_own_password(client: AsyncClient) -> None:
    staff = await warden(client)
    student, password = await new_student(client, staff)
    first = await client.post(
        "/api/v1/auth/login", json={"email": student["email"], "password": password}
    )
    token, other_device_refresh = first.json()["access_token"], first.json()["refresh_token"]

    wrong = await client.post(
        "/api/v1/auth/change-password",
        headers=h(token),
        json={"current_password": "NotMyPassword1", "new_password": "ChangedPass789!"},
    )
    assert wrong.status_code == 422

    same = await client.post(
        "/api/v1/auth/change-password",
        headers=h(token),
        json={"current_password": password, "new_password": password},
    )
    assert same.status_code == 422

    ok = await client.post(
        "/api/v1/auth/change-password",
        headers=h(token),
        json={"current_password": password, "new_password": "ChangedPass789!"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["refresh_token"] and "access_token" in ok.cookies

    # Other sessions are signed out; the new password works. The client's cookie
    # jar now holds the NEW session, which /refresh would prefer, so clear it to
    # present only the other device's token.
    client.cookies.clear()
    revoked = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": other_device_refresh}
    )
    assert revoked.status_code == 401
    assert await login(client, student["email"], "ChangedPass789!")
