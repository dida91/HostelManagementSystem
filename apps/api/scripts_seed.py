"""Seed development data. Synthetic only -- no real resident data."""
from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.core.security import hash_password
from app.models.enums import (
    AssignmentStatus, BedStatus, DocumentType, LedgerEntryType, MealType,
    RoomStatus, RoomType, StudentStatus, UserRole,
)
from app.models.finance import StudentLedgerEntry
from app.models.hostel import Bed, BedAssignment, Block, Room
from app.models.mess import Announcement, MessMenu
from app.models.user import Student, User


async def seed() -> None:
    async with AsyncSessionLocal() as s:
        if (await s.execute(select(User).limit(1))).scalar_one_or_none():
            print("already seeded; skipping")
            return

        warden = User(
            email="warden@kutumba.local", full_name="Warden Sharma",
            password_hash=hash_password("WardenPass123!"), role=UserRole.WARDEN,
        )
        u1 = User(email="sita@kutumba.local", full_name="Sita Gurung",
                  password_hash=hash_password("StudentPass123!"), role=UserRole.STUDENT)
        u2 = User(email="mina@kutumba.local", full_name="Mina Thapa",
                  password_hash=hash_password("StudentPass123!"), role=UserRole.STUDENT)
        s.add_all([warden, u1, u2])
        await s.flush()

        st1 = Student(user_id=u1.id, student_code="KH-2026-001", college="Pokhara University",
                      program="BBA", status=StudentStatus.ACTIVE, admission_date=date(2026, 8, 1))
        st2 = Student(user_id=u2.id, student_code="KH-2026-002", college="Prithvi Narayan Campus",
                      program="BSc CSIT", status=StudentStatus.ACTIVE, admission_date=date(2026, 8, 5))
        s.add_all([st1, st2])

        block = Block(name="A Block", floors=3, description="Main residential block")
        s.add(block)
        await s.flush()

        rooms, beds = [], []
        for floor in (1, 2, 3):
            for n in (1, 2):
                r = Room(block_id=block.id, floor=floor, room_number=f"{floor}0{n}",
                         capacity=2, room_type=RoomType.DOUBLE, status=RoomStatus.AVAILABLE,
                         monthly_rate_npr=8000)
                rooms.append(r)
        s.add_all(rooms)
        await s.flush()
        for r in rooms:
            for label in ("A", "B"):
                beds.append(Bed(room_id=r.id, bed_label=label, status=BedStatus.VACANT))
        s.add_all(beds)
        await s.flush()

        s.add_all([
            BedAssignment(student_id=st1.id, bed_id=beds[0].id, from_date=date(2026, 8, 1),
                          status=AssignmentStatus.ACTIVE),
            BedAssignment(student_id=st2.id, bed_id=beds[2].id, from_date=date(2026, 8, 5),
                          status=AssignmentStatus.ACTIVE),
        ])
        beds[0].status = BedStatus.OCCUPIED
        beds[2].status = BedStatus.OCCUPIED

        # Ledger: two months charged, one paid -> outstanding 8000 for Sita.
        now = datetime.now(UTC)
        s.add_all([
            StudentLedgerEntry(student_id=st1.id, entry_type=LedgerEntryType.DEBIT,
                               amount_npr=Decimal("8000.00"), description="Hostel fee August",
                               occurred_at=now - timedelta(days=45)),
            StudentLedgerEntry(student_id=st1.id, entry_type=LedgerEntryType.DEBIT,
                               amount_npr=Decimal("8000.00"), description="Hostel fee September",
                               occurred_at=now - timedelta(days=15)),
            StudentLedgerEntry(student_id=st1.id, entry_type=LedgerEntryType.CREDIT,
                               amount_npr=Decimal("8000.00"), description="Payment received",
                               occurred_at=now - timedelta(days=40)),
        ])

        for dow in range(7):
            s.add_all([
                MessMenu(day_of_week=dow, meal_type=MealType.BREAKFAST,
                         items="Tea, bread, eggs", serving_time="07:00-09:00"),
                MessMenu(day_of_week=dow, meal_type=MealType.DINNER,
                         items="Dal, bhat, tarkari", serving_time="19:00-21:00"),
            ])

        s.add(Announcement(title="Water supply maintenance",
                           body="Water will be unavailable on Saturday 10am-2pm.",
                           audience="ALL", publish_at=now - timedelta(days=1),
                           expires_at=now + timedelta(days=7),
                           created_by_user_id=warden.id))
        await s.commit()
        print("seeded: 3 users, 2 students, 6 rooms, 12 beds, ledger, menu, announcement")


if __name__ == "__main__":
    asyncio.run(seed())
