"""Authorization matrix: the tests that matter most for a residential system
holding data about young women."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, password: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def test_health_live(client: AsyncClient) -> None:
    r = await client.get("/api/v1/health/live")
    assert r.status_code == 200


async def test_login_succeeds_for_seeded_student(client: AsyncClient) -> None:
    token = await _login(client, "sita@kutumba.local", "StudentPass123!")
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["student_code"] == "KH-2026-001"


async def test_wrong_password_and_unknown_user_are_indistinguishable(client: AsyncClient) -> None:
    """Identical responses prevent account enumeration."""
    bad_pw = await client.post(
        "/api/v1/auth/login",
        json={"email": "sita@kutumba.local", "password": "WrongPassword1"},
    )
    unknown = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@kutumba.local", "password": "WrongPassword1"},
    )
    assert bad_pw.status_code == unknown.status_code == 401
    assert bad_pw.json()["detail"] == unknown.json()["detail"]


async def test_unauthenticated_requests_are_rejected(client: AsyncClient) -> None:
    for path in ["/api/v1/complaints", "/api/v1/auth/me"]:
        assert (await client.get(path)).status_code == 401


async def test_student_cannot_read_another_students_complaint(client: AsyncClient) -> None:
    sita = await _login(client, "sita@kutumba.local", "StudentPass123!")
    mina = await _login(client, "mina@kutumba.local", "StudentPass123!")

    created = await client.post(
        "/api/v1/complaints",
        headers={"Authorization": f"Bearer {sita}"},
        json={"text": "Testing cross tenant isolation between two residents."},
    )
    assert created.status_code == 201
    cid = created.json()["id"]

    # 404 rather than 403: Mina must not learn the complaint exists at all.
    leaked = await client.get(
        f"/api/v1/complaints/{cid}", headers={"Authorization": f"Bearer {mina}"}
    )
    assert leaked.status_code == 404


async def test_student_cannot_override_triage(client: AsyncClient) -> None:
    sita = await _login(client, "sita@kutumba.local", "StudentPass123!")
    created = await client.post(
        "/api/v1/complaints",
        headers={"Authorization": f"Bearer {sita}"},
        json={"text": "A complaint used to verify that students cannot retriage."},
    )
    cid = created.json()["id"]
    r = await client.patch(
        f"/api/v1/complaints/{cid}",
        headers={"Authorization": f"Bearer {sita}"},
        json={"priority": "LOW"},
    )
    assert r.status_code == 403


async def test_warden_override_is_recorded(client: AsyncClient) -> None:
    sita = await _login(client, "sita@kutumba.local", "StudentPass123!")
    warden = await _login(client, "warden@kutumba.local", "WardenPass123!")
    cid = (
        await client.post(
            "/api/v1/complaints",
            headers={"Authorization": f"Bearer {sita}"},
            json={"text": "Complaint used to verify that overrides are tracked."},
        )
    ).json()["id"]

    r = await client.patch(
        f"/api/v1/complaints/{cid}",
        headers={"Authorization": f"Bearer {warden}"},
        json={"priority": "HIGH", "category": "WATER"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["priority"] == "HIGH"
    assert set(body["overridden_fields"]) == {"priority", "category"}


async def test_complaint_submission_works_while_ai_is_unavailable(client: AsyncClient) -> None:
    """Graceful degradation: students must still be able to report problems."""
    sita = await _login(client, "sita@kutumba.local", "StudentPass123!")
    r = await client.post(
        "/api/v1/complaints",
        headers={"Authorization": f"Bearer {sita}"},
        json={"text": "The system must accept this even with no Gemini key configured."},
    )
    assert r.status_code == 201


async def test_ai_endpoints_degrade_without_leaking_internals(client: AsyncClient) -> None:
    sita = await _login(client, "sita@kutumba.local", "StudentPass123!")
    r = await client.post(
        "/api/v1/assistant/ask",
        headers={"Authorization": f"Bearer {sita}"},
        json={"message": "What is my outstanding fee?"},
    )
    assert r.status_code == 503
    detail = r.json()["detail"].lower()
    for leak in ["gemini", "api key", "traceback", "sqlalchemy"]:
        assert leak not in detail
