"""Shared helpers for API-level tests."""

from __future__ import annotations

import uuid
from typing import Any

from httpx import AsyncClient

WARDEN = ("warden@kutumba.local", "WardenPass123!")
SITA = ("sita@kutumba.local", "StudentPass123!")
MINA = ("mina@kutumba.local", "StudentPass123!")


async def login(client: AsyncClient, email: str, password: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return str(r.json()["access_token"])


def h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def warden(client: AsyncClient) -> dict[str, str]:
    return h(await login(client, *WARDEN))


async def sita(client: AsyncClient) -> dict[str, str]:
    return h(await login(client, *SITA))


async def mina(client: AsyncClient) -> dict[str, str]:
    return h(await login(client, *MINA))


async def new_student(
    client: AsyncClient, staff: dict[str, str], **overrides: Any
) -> tuple[dict[str, Any], str]:
    """Register a resident through the API. Returns (student, password)."""
    suffix = uuid.uuid4().hex[:8]
    password = "ResidentPass123!"
    body = {
        "full_name": f"Resident {suffix}",
        "email": f"r-{suffix}@test.local",
        "initial_password": password,
        "student_code": f"T-{suffix}",
        **overrides,
    }
    r = await client.post("/api/v1/students", headers=staff, json=body)
    assert r.status_code == 201, r.text
    return r.json(), password


async def new_room(
    client: AsyncClient,
    staff: dict[str, str],
    *,
    capacity: int = 2,
    room_type: str = "DOUBLE",
    rate: int | None = 9000,
) -> dict[str, Any]:
    """A fresh block with one room, so tests never compete for seeded beds."""
    block = await client.post(
        "/api/v1/rooms/blocks",
        headers=staff,
        json={"name": f"Block {uuid.uuid4().hex[:8]}", "floors": 2},
    )
    assert block.status_code == 201, block.text
    room = await client.post(
        "/api/v1/rooms",
        headers=staff,
        json={
            "block_id": block.json()["id"],
            "floor": 1,
            "room_number": "101",
            "room_type": room_type,
            "capacity": capacity,
            "monthly_rate_npr": rate,
        },
    )
    assert room.status_code == 201, room.text
    return dict(room.json())


async def notifications(client: AsyncClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    r = await client.get("/api/v1/notifications?limit=100", headers=headers)
    assert r.status_code == 200, r.text
    return list(r.json()["items"])
