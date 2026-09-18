"""Rooms, beds and bed allocation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import SessionDep, require_roles
from app.core.errors import ConflictError, NotFoundError
from app.models.enums import AssignmentStatus, BedStatus, UserRole
from app.models.hostel import Bed, BedAssignment, Room
from app.schemas.hostel import AllocationCreate, AssignmentOut, RoomOut

router = APIRouter(
    prefix="/rooms",
    tags=["rooms"],
    dependencies=[Depends(require_roles(UserRole.STAFF, UserRole.WARDEN, UserRole.SUPER_ADMIN))],
)


@router.get("", response_model=list[RoomOut])
async def list_rooms(session: SessionDep) -> list[RoomOut]:
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
    rows = (
        (await session.execute(select(Room).order_by(Room.floor, Room.room_number))).scalars().all()
    )
    out = []
    for r in rows:
        item = RoomOut.model_validate(r)
        item.occupied = int(occupancy.get(r.id, 0))
        out.append(item)
    return out


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
    assignment.to_date = datetime.now(UTC).date()
    bed = await session.get(Bed, assignment.bed_id)
    if bed is not None:
        bed.status = BedStatus.VACANT
    await session.flush()
    return assignment
