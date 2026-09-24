"""Blocks, rooms and beds: structure management and the allocation rules."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from api_helpers import (
    h,
    login,
    new_room,
    new_student,
    notifications,
    sita,
    warden,
)
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_creating_a_room_creates_its_beds(client: AsyncClient) -> None:
    staff = await warden(client)
    room = await new_room(client, staff, capacity=3, room_type="TRIPLE")

    assert room["bed_count"] == 3
    assert [b["bed_label"] for b in room["beds"]] == ["A", "B", "C"]
    assert all(b["status"] == "VACANT" and b["occupant"] is None for b in room["beds"])

    listed = (await client.get("/api/v1/rooms", headers=staff)).json()
    mine = next(r for r in listed if r["id"] == room["id"])
    assert mine["block_name"] and mine["bed_count"] == 3 and mine["occupied"] == 0


async def test_room_rules_are_enforced(client: AsyncClient) -> None:
    staff = await warden(client)
    room = await new_room(client, staff)
    body = {
        "block_id": room["block_id"],
        "floor": 1,
        "room_type": "DOUBLE",
        "capacity": 2,
    }

    duplicate = await client.post(
        "/api/v1/rooms", headers=staff, json={**body, "room_number": "101"}
    )
    assert duplicate.status_code == 409

    wrong_capacity = await client.post(
        "/api/v1/rooms", headers=staff, json={**body, "room_number": "102", "capacity": 3}
    )
    assert wrong_capacity.status_code == 422

    no_such_floor = await client.post(
        "/api/v1/rooms", headers=staff, json={**body, "room_number": "901", "floor": 9}
    )
    assert no_such_floor.status_code == 422


async def test_students_cannot_change_the_hostel_structure(client: AsyncClient) -> None:
    student = await sita(client)
    r = await client.post(
        "/api/v1/rooms/blocks", headers=student, json={"name": "Sneaky", "floors": 1}
    )
    assert r.status_code == 403


async def test_capacity_changes_add_or_remove_unused_beds(client: AsyncClient) -> None:
    staff = await warden(client)
    room = await new_room(client, staff, capacity=4, room_type="DORMITORY")

    grown = await client.patch(f"/api/v1/rooms/{room['id']}", headers=staff, json={"capacity": 6})
    assert grown.status_code == 200, grown.text
    assert [b["bed_label"] for b in grown.json()["beds"]] == ["A", "B", "C", "D", "E", "F"]

    shrunk = await client.patch(f"/api/v1/rooms/{room['id']}", headers=staff, json={"capacity": 4})
    assert shrunk.status_code == 200
    assert [b["bed_label"] for b in shrunk.json()["beds"]] == ["A", "B", "C", "D"]


async def test_beds_with_history_are_never_removed(client: AsyncClient) -> None:
    staff = await warden(client)
    room = await new_room(client, staff, capacity=4, room_type="DORMITORY")
    student, _ = await new_student(client, staff)

    # Use every bed once, so none is removable.
    for bed in room["beds"]:
        alloc = await client.post(
            "/api/v1/rooms/allocations",
            headers=staff,
            json={"student_id": student["id"], "bed_id": bed["id"], "from_date": str(date.today())},
        )
        assert alloc.status_code == 201, alloc.text
        vacate = await client.post(
            f"/api/v1/rooms/allocations/{alloc.json()['id']}/vacate", headers=staff
        )
        assert vacate.status_code == 200

    shrink = await client.patch(
        f"/api/v1/rooms/{room['id']}",
        headers=staff,
        json={"room_type": "TRIPLE", "capacity": 3},
    )
    assert shrink.status_code == 409, "every bed has history, so none may be removed"
    beds = (await client.get(f"/api/v1/rooms/{room['id']}", headers=staff)).json()["beds"]
    assert len(beds) == 4

    deleted = await client.delete(f"/api/v1/rooms/{room['id']}", headers=staff)
    assert deleted.status_code == 409, "a room that was lived in keeps its history"


async def test_unused_rooms_and_empty_blocks_can_be_deleted(client: AsyncClient) -> None:
    staff = await warden(client)
    room = await new_room(client, staff)

    blocked = await client.delete(f"/api/v1/rooms/blocks/{room['block_id']}", headers=staff)
    assert blocked.status_code == 409, "a block with rooms cannot be deleted"

    assert (await client.delete(f"/api/v1/rooms/{room['id']}", headers=staff)).status_code == 204
    assert (
        await client.delete(f"/api/v1/rooms/blocks/{room['block_id']}", headers=staff)
    ).status_code == 204


async def test_allocation_rules_and_notification(client: AsyncClient) -> None:
    staff = await warden(client)
    room = await new_room(client, staff)
    student, password = await new_student(client, staff)
    bed_a, bed_b = room["beds"]

    unknown = await client.post(
        "/api/v1/rooms/allocations",
        headers=staff,
        json={"student_id": str(uuid.uuid4()), "bed_id": bed_a["id"], "from_date": "2026-09-01"},
    )
    assert unknown.status_code == 404, "an unknown student is not an 'occupied bed'"

    out_of_service = await client.patch(
        f"/api/v1/rooms/beds/{bed_b['id']}", headers=staff, json={"status": "OUT_OF_SERVICE"}
    )
    assert out_of_service.status_code == 200
    refused = await client.post(
        "/api/v1/rooms/allocations",
        headers=staff,
        json={"student_id": student["id"], "bed_id": bed_b["id"], "from_date": "2026-09-01"},
    )
    assert refused.status_code == 409

    ok = await client.post(
        "/api/v1/rooms/allocations",
        headers=staff,
        json={"student_id": student["id"], "bed_id": bed_a["id"], "from_date": "2026-09-01"},
    )
    assert ok.status_code == 201, ok.text

    detail = (await client.get(f"/api/v1/rooms/{room['id']}", headers=staff)).json()
    occupant = detail["beds"][0]["occupant"]
    assert occupant["student_id"] == student["id"] and detail["occupied"] == 1

    busy = await client.patch(
        f"/api/v1/rooms/beds/{bed_a['id']}", headers=staff, json={"status": "OUT_OF_SERVICE"}
    )
    assert busy.status_code == 409, "an occupied bed cannot be taken out of service"

    resident = h(await login(client, student["email"], password))
    categories = [n["category"] for n in await notifications(client, resident)]
    assert "ROOM_ALLOCATED" in categories


async def test_rooms_under_maintenance_cannot_be_allocated(client: AsyncClient) -> None:
    staff = await warden(client)
    room = await new_room(client, staff)
    student, _ = await new_student(client, staff)
    await client.patch(f"/api/v1/rooms/{room['id']}", headers=staff, json={"status": "MAINTENANCE"})

    r = await client.post(
        "/api/v1/rooms/allocations",
        headers=staff,
        json={
            "student_id": student["id"],
            "bed_id": room["beds"][0]["id"],
            "from_date": "2026-09-01",
        },
    )
    assert r.status_code == 409


async def test_closing_an_occupied_room_is_refused(client: AsyncClient) -> None:
    staff = await warden(client)
    room = await new_room(client, staff)
    student, _ = await new_student(client, staff)
    await client.post(
        "/api/v1/rooms/allocations",
        headers=staff,
        json={
            "student_id": student["id"],
            "bed_id": room["beds"][0]["id"],
            "from_date": "2026-09-01",
        },
    )
    r = await client.patch(f"/api/v1/rooms/{room['id']}", headers=staff, json={"status": "CLOSED"})
    assert r.status_code == 409


async def test_vacating_a_future_allocation_does_not_fail(client: AsyncClient) -> None:
    """Cancelling an allocation that starts next week used to violate the
    to_date >= from_date constraint and return a 500."""
    staff = await warden(client)
    room = await new_room(client, staff)
    student, _ = await new_student(client, staff)
    starts = date.today() + timedelta(days=7)
    alloc = await client.post(
        "/api/v1/rooms/allocations",
        headers=staff,
        json={
            "student_id": student["id"],
            "bed_id": room["beds"][0]["id"],
            "from_date": str(starts),
        },
    )
    r = await client.post(f"/api/v1/rooms/allocations/{alloc.json()['id']}/vacate", headers=staff)
    assert r.status_code == 200, r.text
    assert r.json()["to_date"] == str(starts)
