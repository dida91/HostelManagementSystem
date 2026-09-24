"""Blocks, rooms, beds and bed allocation.

Staff can read everything and allocate beds; changing the hostel's structure
(blocks, rooms, bed status) is the warden's.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import SessionDep, require_roles
from app.core.clock import hostel_today
from app.core.errors import ConflictError, NotFoundError
from app.models.enums import (
    AssignmentStatus,
    BedStatus,
    RoomStatus,
    StudentStatus,
    UserRole,
)
from app.models.hostel import Bed, BedAssignment, Block, Room
from app.models.user import Student
from app.schemas.hostel import (
    AllocationCreate,
    AssignmentOut,
    BedOut,
    BedUpdate,
    BlockCreate,
    BlockOut,
    BlockUpdate,
    RoomCreate,
    RoomDetailOut,
    RoomOut,
    RoomUpdate,
)
from app.services.notifications import NotificationService, room_allocated_message
from app.services.rooms import RoomService, assignment_end_date

router = APIRouter(
    prefix="/rooms",
    tags=["rooms"],
    dependencies=[Depends(require_roles(UserRole.STAFF, UserRole.WARDEN, UserRole.SUPER_ADMIN))],
)
WardenOnly = Depends(require_roles(UserRole.WARDEN, UserRole.SUPER_ADMIN))
UNAVAILABLE_ROOM = {RoomStatus.MAINTENANCE, RoomStatus.CLOSED}


async def _room_detail(session: SessionDep, room: Room) -> RoomDetailOut:
    beds = await RoomService(session).room_beds(room.id)
    block = await session.get(Block, room.block_id)
    base = RoomOut.model_validate(room)
    base.block_name = block.name if block else None
    base.bed_count = len(beds)
    base.occupied = sum(1 for b in beds if b["occupant"])
    return RoomDetailOut(**base.model_dump(), beds=[BedOut.model_validate(b) for b in beds])


# ------------------------------------------------------------------ blocks
# Declared before /{room_id} so "blocks" is never parsed as a room id.


@router.get("/blocks", response_model=list[BlockOut])
async def list_blocks(session: SessionDep) -> list[BlockOut]:
    counts = dict(
        (await session.execute(select(Room.block_id, func.count(Room.id)).group_by(Room.block_id)))
        .tuples()
        .all()
    )
    blocks = (await session.execute(select(Block).order_by(Block.name))).scalars().all()
    out = []
    for block in blocks:
        item = BlockOut.model_validate(block)
        item.room_count = int(counts.get(block.id, 0))
        out.append(item)
    return out


@router.post(
    "/blocks",
    response_model=BlockOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[WardenOnly],
)
async def create_block(payload: BlockCreate, session: SessionDep) -> BlockOut:
    block = await RoomService(session).create_block(
        name=payload.name, description=payload.description, floors=payload.floors
    )
    return BlockOut.model_validate(block)


@router.patch("/blocks/{block_id}", response_model=BlockOut, dependencies=[WardenOnly])
async def update_block(block_id: uuid.UUID, payload: BlockUpdate, session: SessionDep) -> BlockOut:
    service = RoomService(session)
    block = await service.get_block(block_id)
    changes = payload.model_dump(exclude_unset=True)
    # The description may be cleared with an explicit null; nothing else may.
    changes = {k: v for k, v in changes.items() if v is not None or k == "description"}
    await service.update_block(block, changes)
    rooms = (
        await session.execute(select(func.count(Room.id)).where(Room.block_id == block.id))
    ).scalar_one()
    out = BlockOut.model_validate(block)
    out.room_count = int(rooms)
    return out


@router.delete(
    "/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[WardenOnly]
)
async def delete_block(block_id: uuid.UUID, session: SessionDep) -> None:
    service = RoomService(session)
    await service.delete_block(await service.get_block(block_id))


# -------------------------------------------------------------------- beds


@router.patch("/beds/{bed_id}", response_model=BedOut, dependencies=[WardenOnly])
async def update_bed(bed_id: uuid.UUID, payload: BedUpdate, session: SessionDep) -> BedOut:
    """Reserve a bed or take it out of service (and back). A bed becomes
    OCCUPIED only through an allocation."""
    bed = await RoomService(session).set_bed_status(bed_id, payload.status)
    return BedOut(id=bed.id, bed_label=bed.bed_label, status=bed.status)


# ------------------------------------------------------------------- rooms


@router.get("", response_model=list[RoomOut])
async def list_rooms(
    session: SessionDep,
    block_id: uuid.UUID | None = Query(default=None),
    status_filter: RoomStatus | None = Query(default=None, alias="status"),
) -> list[RoomOut]:
    """Rooms with live occupancy counted from active assignments."""
    occupancy: dict[uuid.UUID, int] = {
        row[0]: row[1]
        for row in (
            await session.execute(
                select(Room.id, func.count(BedAssignment.id))
                .select_from(Room)
                .join(Bed, Bed.room_id == Room.id)
                .join(
                    BedAssignment,
                    (BedAssignment.bed_id == Bed.id)
                    & (BedAssignment.status == AssignmentStatus.ACTIVE),
                    isouter=True,
                )
                .group_by(Room.id)
            )
        ).all()
    }
    bed_counts = dict(
        (await session.execute(select(Bed.room_id, func.count(Bed.id)).group_by(Bed.room_id)))
        .tuples()
        .all()
    )
    stmt = (
        select(Room, Block.name)
        .join(Block, Block.id == Room.block_id)
        .order_by(Block.name, Room.floor, Room.room_number)
    )
    if block_id is not None:
        stmt = stmt.where(Room.block_id == block_id)
    if status_filter is not None:
        stmt = stmt.where(Room.status == status_filter)

    out = []
    for room, block_name in (await session.execute(stmt)).all():
        item = RoomOut.model_validate(room)
        item.block_name = block_name
        item.bed_count = int(bed_counts.get(room.id, 0))
        item.occupied = int(occupancy.get(room.id, 0))
        out.append(item)
    return out


@router.post(
    "",
    response_model=RoomDetailOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[WardenOnly],
)
async def create_room(payload: RoomCreate, session: SessionDep) -> RoomDetailOut:
    """Create a room together with its beds (labelled A, B, C...)."""
    room = await RoomService(session).create_room(**payload.model_dump())
    return await _room_detail(session, room)


@router.post("/allocations", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
async def allocate_bed(payload: AllocationCreate, session: SessionDep) -> BedAssignment:
    """Allocate a bed.

    Double-allocation is prevented by partial unique indexes in the database, so
    two concurrent requests cannot both succeed. The IntegrityError is translated
    into a clear conflict rather than a 500.
    """
    bed = await session.get(Bed, payload.bed_id)
    if bed is None:
        raise NotFoundError("Bed not found.")
    if bed.status is BedStatus.OUT_OF_SERVICE:
        raise ConflictError("That bed is out of service.")
    room = await session.get(Room, bed.room_id)
    assert room is not None  # FK
    if room.status in UNAVAILABLE_ROOM:
        raise ConflictError(
            f"Room {room.room_number} is {room.status.value.lower()}; its beds cannot be allocated."
        )
    student = await session.get(Student, payload.student_id)
    if student is None:
        raise NotFoundError("Student not found.")
    if student.status in {StudentStatus.ALUMNI, StudentStatus.SUSPENDED}:
        raise ConflictError(
            f"This student is {student.status.value.lower()} and cannot be allocated a bed."
        )

    assignment = BedAssignment(
        student_id=payload.student_id,
        bed_id=payload.bed_id,
        from_date=payload.from_date,
        status=AssignmentStatus.ACTIVE,
    )
    session.add(assignment)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "That bed is already occupied, or the student already has an active bed."
        ) from exc

    bed.status = BedStatus.OCCUPIED
    await session.flush()

    block = await session.get(Block, room.block_id)
    await NotificationService(session).notify_student(
        student.id,
        room_allocated_message(
            block_name=block.name if block else "",
            room_number=room.room_number,
            bed_label=bed.bed_label,
            from_date=payload.from_date,
        ),
    )
    return assignment


@router.post("/allocations/{assignment_id}/vacate", response_model=AssignmentOut)
async def vacate_bed(assignment_id: uuid.UUID, session: SessionDep) -> BedAssignment:
    """End an allocation. The row is closed, never deleted, so residency history
    remains auditable."""
    assignment = await session.get(BedAssignment, assignment_id)
    if assignment is None:
        raise NotFoundError("Assignment not found.")
    if assignment.status is not AssignmentStatus.ACTIVE:
        raise ConflictError("That assignment is not active.")

    assignment.status = AssignmentStatus.ENDED
    # Never before the start date: an allocation that has not begun yet can
    # still be cancelled without violating the date-order constraint.
    assignment.to_date = assignment_end_date(None, hostel_today(), assignment.from_date)
    bed = await session.get(Bed, assignment.bed_id)
    if bed is not None:
        bed.status = BedStatus.VACANT
    await session.flush()
    return assignment


@router.get("/{room_id}", response_model=RoomDetailOut)
async def get_room(room_id: uuid.UUID, session: SessionDep) -> RoomDetailOut:
    """A room with each bed and its current occupant."""
    return await _room_detail(session, await RoomService(session).get_room(room_id))


@router.patch("/{room_id}", response_model=RoomDetailOut, dependencies=[WardenOnly])
async def update_room(
    room_id: uuid.UUID, payload: RoomUpdate, session: SessionDep
) -> RoomDetailOut:
    """Edit a room. Changing capacity adds beds, or removes never-used ones."""
    service = RoomService(session)
    room = await service.get_room(room_id)
    changes = payload.model_dump(exclude_unset=True)
    # monthly_rate_npr may be cleared with an explicit null; nothing else may.
    changes = {k: v for k, v in changes.items() if v is not None or k == "monthly_rate_npr"}
    await service.update_room(room, changes)
    return await _room_detail(session, room)


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[WardenOnly])
async def delete_room(room_id: uuid.UUID, session: SessionDep) -> None:
    """Delete a room that has never been lived in. Otherwise close it instead."""
    service = RoomService(session)
    await service.delete_room(await service.get_room(room_id))
