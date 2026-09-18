from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey
from app.models.enums import AssignmentStatus, BedStatus, RoomStatus, RoomType

if TYPE_CHECKING:
    from app.models.user import Student


class Block(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "blocks"

    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    floors: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    rooms: Mapped[list[Room]] = relationship(back_populates="block")

    __table_args__ = (CheckConstraint("floors > 0", name="ck_blocks_floors_positive"),)


class Room(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "rooms"

    block_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("blocks.id", ondelete="RESTRICT"), nullable=False
    )
    floor: Mapped[int] = mapped_column(Integer, nullable=False)
    room_number: Mapped[str] = mapped_column(String(20), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    room_type: Mapped[RoomType] = mapped_column(Enum(RoomType, name="room_type"), nullable=False)
    status: Mapped[RoomStatus] = mapped_column(
        Enum(RoomStatus, name="room_status"), default=RoomStatus.AVAILABLE, nullable=False
    )
    monthly_rate_npr: Mapped[int | None] = mapped_column(Integer)

    block: Mapped[Block] = relationship(back_populates="rooms")
    beds: Mapped[list[Bed]] = relationship(back_populates="room", order_by="Bed.bed_label")

    __table_args__ = (
        UniqueConstraint("block_id", "room_number", name="uq_room_number_per_block"),
        CheckConstraint("capacity > 0 AND capacity <= 12", name="ck_rooms_capacity_range"),
        CheckConstraint("floor >= 0", name="ck_rooms_floor_nonneg"),
        Index("ix_rooms_status", "status"),
    )


class Bed(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "beds"

    room_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )
    bed_label: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[BedStatus] = mapped_column(
        Enum(BedStatus, name="bed_status"), default=BedStatus.VACANT, nullable=False
    )

    room: Mapped[Room] = relationship(back_populates="beds")

    __table_args__ = (
        UniqueConstraint("room_id", "bed_label", name="uq_bed_label_per_room"),
        Index("ix_beds_status", "status"),
    )


class BedAssignment(UUIDPrimaryKey, Timestamps, Base):
    """Residency history. Rows are never deleted or overwritten; ending an
    assignment sets to_date and status=ENDED."""

    __tablename__ = "bed_assignments"

    student_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("students.id", ondelete="RESTRICT"), nullable=False
    )
    bed_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("beds.id", ondelete="RESTRICT"), nullable=False
    )
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, name="assignment_status"),
        default=AssignmentStatus.ACTIVE,
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(Text)

    student: Mapped[Student] = relationship(back_populates="assignments")
    bed: Mapped[Bed] = relationship()

    __table_args__ = (
        CheckConstraint("to_date IS NULL OR to_date >= from_date", name="ck_assignment_date_order"),
        # Occupancy invariants enforced by the database, not by application code:
        # a bed can hold at most one active occupant, and a student can hold at
        # most one active bed. Partial unique indexes make double-allocation a
        # constraint violation rather than a race condition.
        Index(
            "uq_one_active_occupant_per_bed",
            "bed_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index(
            "uq_one_active_bed_per_student",
            "student_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index("ix_assignments_student", "student_id", "status"),
    )
