"""Blocks, rooms and beds.

Residency history is never destroyed: a room or bed that has ever been
assigned cannot be deleted, only closed or taken out of service. Beds are
created with their room (capacity = number of beds) and labelled A, B, C...
"""

from __future__ import annotations

import string
import uuid
from datetime import date
from typing import Any

from sqlalchemy import delete, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.models.enums import AssignmentStatus, BedStatus, RoomStatus, RoomType
from app.models.hostel import Bed, BedAssignment, Block, Room
from app.models.user import Student, User

# Beds per room type. A room with more beds than its type allows is a data
# error, not a layout choice.
CAPACITY_RANGE: dict[RoomType, tuple[int, int]] = {
    RoomType.SINGLE: (1, 1),
    RoomType.DOUBLE: (2, 2),
    RoomType.TRIPLE: (3, 3),
    RoomType.DORMITORY: (4, 12),
}
BED_LABELS = string.ascii_uppercase


def _check_capacity(room_type: RoomType, capacity: int) -> None:
    low, high = CAPACITY_RANGE[room_type]
    if not low <= capacity <= high:
        allowed = str(low) if low == high else f"{low} to {high}"
        raise ValidationFailedError(
            f"A {room_type.value.lower()} room has {allowed} bed(s), not {capacity}."
        )


class RoomService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------- blocks

    async def get_block(self, block_id: uuid.UUID) -> Block:
        block = await self._session.get(Block, block_id)
        if block is None:
            raise NotFoundError("Block not found.")
        return block

    async def create_block(self, *, name: str, description: str | None, floors: int) -> Block:
        block = Block(name=name.strip(), description=description, floors=floors)
        try:
            # Changes are made INSIDE the savepoint: begin_nested() flushes
            # anything already pending before the savepoint exists, so a
            # conflict there would abort the whole transaction.
            async with self._session.begin_nested():
                self._session.add(block)
                await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(f"A block named {name!r} already exists.") from exc
        return block

    async def update_block(self, block: Block, changes: dict[str, Any]) -> Block:
        if "floors" in changes:
            highest = (
                await self._session.execute(
                    select(func.max(Room.floor)).where(Room.block_id == block.id)
                )
            ).scalar_one()
            if highest is not None and changes["floors"] < highest:
                raise ConflictError(
                    f"This block has rooms on floor {highest}; it cannot have fewer floors."
                )
        try:
            async with self._session.begin_nested():
                for key, value in changes.items():
                    setattr(block, key, value.strip() if key == "name" else value)
                await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError("Another block already has that name.") from exc
        return block

    async def delete_block(self, block: Block) -> None:
        has_rooms = (
            await self._session.execute(select(exists().where(Room.block_id == block.id)))
        ).scalar_one()
        if has_rooms:
            raise ConflictError("This block still has rooms. Remove or move them first.")
        await self._session.execute(delete(Block).where(Block.id == block.id))

    # -------------------------------------------------------------- rooms

    async def get_room(self, room_id: uuid.UUID) -> Room:
        room = await self._session.get(Room, room_id)
        if room is None:
            raise NotFoundError("Room not found.")
        return room

    async def create_room(
        self,
        *,
        block_id: uuid.UUID,
        floor: int,
        room_number: str,
        room_type: RoomType,
        capacity: int,
        monthly_rate_npr: int | None,
        status: RoomStatus,
    ) -> Room:
        block = await self.get_block(block_id)
        self._check_floor(block, floor)
        _check_capacity(room_type, capacity)

        room = Room(
            block_id=block.id,
            floor=floor,
            room_number=room_number.strip(),
            room_type=room_type,
            capacity=capacity,
            monthly_rate_npr=monthly_rate_npr,
            status=status,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(room)
                await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(f"Room {room_number} already exists in {block.name}.") from exc

        self._session.add_all(
            Bed(room_id=room.id, bed_label=BED_LABELS[i], status=BedStatus.VACANT)
            for i in range(capacity)
        )
        await self._session.flush()
        return room

    async def update_room(self, room: Room, changes: dict[str, Any]) -> Room:
        block = await self.get_block(room.block_id)
        if "floor" in changes:
            self._check_floor(block, changes["floor"])

        room_type = changes.get("room_type", room.room_type)
        capacity = changes.get("capacity", room.capacity)
        _check_capacity(room_type, capacity)

        if changes.get("status") is RoomStatus.CLOSED and await self._occupied_count(room.id):
            raise ConflictError("Residents still live in this room; vacate their beds first.")

        try:
            async with self._session.begin_nested():
                if capacity != room.capacity:
                    await self._resize(room, capacity)
                for key, value in changes.items():
                    setattr(room, key, value.strip() if key == "room_number" else value)
                await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError("Another room in this block already has that number.") from exc
        return room

    async def delete_room(self, room: Room) -> None:
        if await self._has_history(room.id):
            raise ConflictError(
                "This room has residency history and cannot be deleted. "
                "Set its status to CLOSED instead."
            )
        await self._session.execute(delete(Room).where(Room.id == room.id))  # beds cascade

    async def room_beds(self, room_id: uuid.UUID) -> list[dict[str, Any]]:
        """Beds with their current occupant, if any."""
        beds = (
            (
                await self._session.execute(
                    select(Bed).where(Bed.room_id == room_id).order_by(Bed.bed_label)
                )
            )
            .scalars()
            .all()
        )
        occupants = {
            row.bed_id: row
            for row in (
                await self._session.execute(
                    select(
                        BedAssignment.bed_id,
                        BedAssignment.id.label("assignment_id"),
                        BedAssignment.from_date,
                        Student.id.label("student_id"),
                        Student.student_code,
                        User.full_name,
                    )
                    .join(Student, Student.id == BedAssignment.student_id)
                    .join(User, User.id == Student.user_id)
                    .where(
                        BedAssignment.bed_id.in_([b.id for b in beds]),
                        BedAssignment.status == AssignmentStatus.ACTIVE,
                    )
                )
            ).all()
        }
        out = []
        for bed in beds:
            occ = occupants.get(bed.id)
            out.append(
                {
                    "id": bed.id,
                    "bed_label": bed.bed_label,
                    "status": bed.status,
                    "occupant": (
                        {
                            "assignment_id": occ.assignment_id,
                            "student_id": occ.student_id,
                            "student_code": occ.student_code,
                            "full_name": occ.full_name,
                            "from_date": occ.from_date,
                        }
                        if occ
                        else None
                    ),
                }
            )
        return out

    # --------------------------------------------------------------- beds

    async def set_bed_status(self, bed_id: uuid.UUID, status: BedStatus) -> Bed:
        bed = await self._session.get(Bed, bed_id)
        if bed is None:
            raise NotFoundError("Bed not found.")
        if status is BedStatus.OCCUPIED:
            raise ValidationFailedError("A bed becomes occupied only through an allocation.")
        occupied = (
            await self._session.execute(
                select(
                    exists().where(
                        BedAssignment.bed_id == bed.id,
                        BedAssignment.status == AssignmentStatus.ACTIVE,
                    )
                )
            )
        ).scalar_one()
        if occupied:
            raise ConflictError("Someone is allocated to this bed; vacate it first.")
        bed.status = status
        await self._session.flush()
        return bed

    # ------------------------------------------------------------ helpers

    @staticmethod
    def _check_floor(block: Block, floor: int) -> None:
        if floor > block.floors:
            raise ValidationFailedError(
                f"{block.name} has {block.floors} floor(s); floor {floor} does not exist."
            )

    async def _occupied_count(self, room_id: uuid.UUID) -> int:
        return int(
            (
                await self._session.execute(
                    select(func.count(BedAssignment.id))
                    .join(Bed, Bed.id == BedAssignment.bed_id)
                    .where(Bed.room_id == room_id, BedAssignment.status == AssignmentStatus.ACTIVE)
                )
            ).scalar_one()
        )

    async def _has_history(self, room_id: uuid.UUID) -> bool:
        return bool(
            (
                await self._session.execute(
                    select(
                        exists().where(BedAssignment.bed_id == Bed.id).where(Bed.room_id == room_id)
                    )
                )
            ).scalar_one()
        )

    async def _resize(self, room: Room, capacity: int) -> None:
        beds = list(
            (
                await self._session.execute(
                    select(Bed).where(Bed.room_id == room.id).order_by(Bed.bed_label)
                )
            )
            .scalars()
            .all()
        )
        if capacity > len(beds):
            used = {b.bed_label for b in beds}
            free = [label for label in BED_LABELS if label not in used]
            self._session.add_all(
                Bed(room_id=room.id, bed_label=label, status=BedStatus.VACANT)
                for label in free[: capacity - len(beds)]
            )
            return

        used_bed_ids = set(
            (
                await self._session.execute(
                    select(BedAssignment.bed_id).where(
                        BedAssignment.bed_id.in_([b.id for b in beds])
                    )
                )
            )
            .scalars()
            .all()
        )
        # Remove never-used beds, highest label first. A bed with any history
        # stays, so past allocations keep pointing at a real bed.
        removable = [b for b in reversed(beds) if b.id not in used_bed_ids]
        excess = len(beds) - capacity
        if len(removable) < excess:
            raise ConflictError(
                f"Only {len(removable)} bed(s) in this room can be removed; the others are "
                "occupied or have residency history. Mark them out of service instead."
            )
        for bed in removable[:excess]:
            await self._session.delete(bed)


async def active_room_labels(
    session: AsyncSession, student_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """'A Block 101 / bed A' for each student currently holding a bed."""
    if not student_ids:
        return {}
    rows = (
        await session.execute(
            select(BedAssignment.student_id, Block.name, Room.room_number, Bed.bed_label)
            .join(Bed, Bed.id == BedAssignment.bed_id)
            .join(Room, Room.id == Bed.room_id)
            .join(Block, Block.id == Room.block_id)
            .where(
                BedAssignment.student_id.in_(student_ids),
                BedAssignment.status == AssignmentStatus.ACTIVE,
            )
        )
    ).all()
    return {sid: f"{block} {room} / bed {bed}" for sid, block, room, bed in rows}


def assignment_end_date(requested: date | None, today: date, from_date: date) -> date:
    """An end date never before the assignment started (DB check constraint)."""
    end = requested or today
    return max(end, from_date)
