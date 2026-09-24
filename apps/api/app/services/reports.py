"""Report data, assembled from SQL into the format-neutral Report model.

Every figure is computed by the database (see docs/adr/0003). Complaint
reports deliberately omit who filed each complaint, matching the triage
screen: a report is easy to forward, and a complaint about harassment or a
staff member must not travel with the resident's name attached.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import hostel_tz
from app.models.complaint import Complaint
from app.models.enums import (
    AssignmentStatus,
    BedStatus,
    ComplaintStatus,
    InvoiceStatus,
    LedgerEntryType,
    StudentStatus,
)
from app.models.finance import FeeInvoice, StudentLedgerEntry
from app.models.hostel import Bed, BedAssignment, Block, Room
from app.models.leave import LeaveRequest
from app.models.user import Student, User
from app.reports.model import Column, Report, Table
from app.services.finance import FinanceService
from app.services.rooms import active_room_labels

OPEN_INVOICE = (InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE)
RESOLVED_COMPLAINT = (ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED)


def _words(value: str | None) -> str | None:
    return value.replace("_", " ").lower() if value else None


def _day(d: date) -> str:
    return f"{d:%d %b %Y}"


class ReportService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._tz = hostel_tz()

    def _now(self) -> datetime:
        return datetime.now(self._tz)

    def _local(self, value: datetime | None) -> datetime | None:
        return value.astimezone(self._tz) if value else None

    def _utc_range(self, date_from: date, date_to: date) -> tuple[datetime, datetime]:
        start = datetime.combine(date_from, time.min, tzinfo=self._tz)
        end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=self._tz)
        return start, end

    # ------------------------------------------------------------ students

    async def students(self, *, status: StudentStatus | None = None) -> Report:
        stmt = (
            select(Student, User)
            .join(User, User.id == Student.user_id)
            .order_by(Student.student_code)
        )
        if status is not None:
            stmt = stmt.where(Student.status == status)
        rows = (await self._session.execute(stmt)).all()
        rooms = await active_room_labels(self._session, [s.id for s, _ in rows])

        table = Table(
            title="Residents",
            columns=[
                Column("Code", width=12),
                Column("Name", width=20),
                Column("Email", width=24),
                Column("Phone", width=13),
                Column("College", width=20),
                Column("Program", width=12),
                Column("Status", width=10),
                Column("Room", width=16),
                Column("Admitted", "date", 11),
                Column("Guardian", width=18),
                Column("Guardian phone", width=14),
            ],
            rows=[
                [
                    s.student_code,
                    u.full_name,
                    u.email,
                    u.phone,
                    s.college,
                    s.program,
                    _words(s.status.value),
                    rooms.get(s.id),
                    s.admission_date,
                    s.guardian_name,
                    s.guardian_phone,
                ]
                for s, u in rows
            ],
        )
        scope = f"Status: {_words(status.value)}" if status else "All residents"
        return Report(
            title="Resident register",
            subtitle=f"{scope} ({len(rows)})",
            generated_at=self._now(),
            tables=[table],
            notes=["Contains personal data. Store and share it only as hostel policy allows."],
        )

    # ----------------------------------------------------------- occupancy

    async def occupancy(self) -> Report:
        rooms = (
            await self._session.execute(
                select(Room, Block.name)
                .join(Block, Block.id == Room.block_id)
                .order_by(Block.name, Room.floor, Room.room_number)
            )
        ).all()
        bed_counts: dict[Any, tuple[int, int]] = {
            room_id: (int(total), int(out_of_service))
            for room_id, total, out_of_service in (
                await self._session.execute(
                    select(
                        Bed.room_id,
                        func.count(Bed.id),
                        func.count(Bed.id).filter(Bed.status == BedStatus.OUT_OF_SERVICE),
                    ).group_by(Bed.room_id)
                )
            ).all()
        }
        residents: dict[Any, list[str]] = {}
        for room_id, name, code in (
            await self._session.execute(
                select(Bed.room_id, User.full_name, Student.student_code)
                .join(BedAssignment, BedAssignment.bed_id == Bed.id)
                .join(Student, Student.id == BedAssignment.student_id)
                .join(User, User.id == Student.user_id)
                .where(BedAssignment.status == AssignmentStatus.ACTIVE)
                .order_by(Bed.bed_label)
            )
        ).all():
            residents.setdefault(room_id, []).append(f"{name} ({code})")

        table_rows: list[list[Any]] = []
        sums = [0, 0, 0, 0]
        for room, block_name in rooms:
            beds, out_of_service = bed_counts.get(room.id, (0, 0))
            occupied = len(residents.get(room.id, []))
            vacant = max(beds - occupied - out_of_service, 0)
            for i, n in enumerate((beds, occupied, vacant, out_of_service)):
                sums[i] += n
            table_rows.append(
                [
                    block_name,
                    room.room_number,
                    room.floor,
                    _words(room.room_type.value),
                    beds,
                    occupied,
                    vacant,
                    out_of_service,
                    _words(room.status.value),
                    Decimal(room.monthly_rate_npr) if room.monthly_rate_npr is not None else None,
                    ", ".join(residents.get(room.id, [])),
                ]
            )

        total_beds, total_occupied = sums[0], sums[1]
        rate = round(100 * total_occupied / total_beds, 1) if total_beds else 0.0
        table = Table(
            title="Rooms",
            columns=[
                Column("Block", width=12),
                Column("Room", width=7),
                Column("Floor", "int", 6),
                Column("Type", width=10),
                Column("Beds", "int", 6),
                Column("Occupied", "int", 8),
                Column("Vacant", "int", 7),
                Column("Out of service", "int", 8),
                Column("Status", width=11),
                Column("Monthly rate (NPR)", "money", 12),
                Column("Residents", width=40),
            ],
            rows=table_rows,
            totals=["Total", None, None, None, *sums, None, None, None],
        )
        return Report(
            title="Occupancy report",
            subtitle=f"{total_occupied} of {total_beds} beds occupied ({rate}%)",
            generated_at=self._now(),
            tables=[table],
        )

    # ---------------------------------------------------------------- fees

    async def fees(self, *, billing_period: str | None = None) -> Report:
        debit = func.coalesce(
            func.sum(StudentLedgerEntry.amount_npr).filter(
                StudentLedgerEntry.entry_type == LedgerEntryType.DEBIT
            ),
            0,
        )
        credit = func.coalesce(
            func.sum(StudentLedgerEntry.amount_npr).filter(
                StudentLedgerEntry.entry_type == LedgerEntryType.CREDIT
            ),
            0,
        )
        balances = (
            await self._session.execute(
                select(Student.student_code, User.full_name, Student.status, debit, credit)
                .join(User, User.id == Student.user_id)
                .join(StudentLedgerEntry, StudentLedgerEntry.student_id == Student.id)
                .group_by(Student.id, Student.student_code, User.full_name, Student.status)
                .order_by(Student.student_code)
            )
        ).all()
        balance_rows: list[list[Any]] = []
        charged_sum = paid_sum = Decimal("0")
        for code, name, status, charged, paid in balances:
            charged, paid = Decimal(charged), Decimal(paid)
            charged_sum += charged
            paid_sum += paid
            balance_rows.append([code, name, _words(status.value), charged, paid, charged - paid])

        stmt = (
            select(FeeInvoice, Student.student_code, User.full_name)
            .join(Student, Student.id == FeeInvoice.student_id)
            .join(User, User.id == Student.user_id)
            .order_by(FeeInvoice.due_date, FeeInvoice.invoice_number)
        )
        if billing_period:
            stmt = stmt.where(FeeInvoice.billing_period == billing_period)
            invoice_scope = f"Invoices for {billing_period}"
        else:
            stmt = stmt.where(FeeInvoice.status.in_(OPEN_INVOICE))
            invoice_scope = "Unpaid invoices"
        invoices = (await self._session.execute(stmt)).all()
        amounts = await FinanceService(self._session).invoice_amounts(
            [invoice.id for invoice, _, _ in invoices]
        )
        invoice_rows: list[list[Any]] = []
        inv_totals = [Decimal("0"), Decimal("0"), Decimal("0")]
        for invoice, code, name in invoices:
            total, paid = amounts[invoice.id]
            outstanding = total - paid
            for i, v in enumerate((total, paid, outstanding)):
                inv_totals[i] += v
            invoice_rows.append(
                [
                    invoice.invoice_number,
                    code,
                    name,
                    f"{invoice.period_start:%Y-%m-%d} to {invoice.period_end:%Y-%m-%d}",
                    invoice.due_date,
                    _words(invoice.status.value),
                    total,
                    paid,
                    outstanding,
                ]
            )

        money = [
            Column("Charged (NPR)", "money", 13),
            Column("Paid (NPR)", "money", 13),
            Column("Outstanding (NPR)", "money", 14),
        ]
        return Report(
            title="Fees report",
            subtitle=(
                f"Outstanding across all residents: NPR {charged_sum - paid_sum:,.2f}"
                f"  |  {invoice_scope}"
            ),
            generated_at=self._now(),
            tables=[
                Table(
                    title="Balances",
                    columns=[
                        Column("Code", width=12),
                        Column("Name", width=22),
                        Column("Status", width=10),
                        *money,
                    ],
                    rows=balance_rows,
                    totals=["Total", None, None, charged_sum, paid_sum, charged_sum - paid_sum],
                ),
                Table(
                    title=invoice_scope,
                    columns=[
                        Column("Invoice", width=17),
                        Column("Code", width=12),
                        Column("Name", width=20),
                        Column("Period", width=22),
                        Column("Due", "date", 11),
                        Column("Status", width=12),
                        Column("Total (NPR)", "money", 12),
                        Column("Paid (NPR)", "money", 12),
                        Column("Outstanding (NPR)", "money", 13),
                    ],
                    rows=invoice_rows,
                    totals=["Total", None, None, None, None, None, *inv_totals],
                ),
            ],
            notes=[
                "Balances are derived from the append-only ledger: "
                "charged = invoices issued, paid = payments and credits recorded."
            ],
        )

    # ---------------------------------------------------------- complaints

    async def complaints(self, *, date_from: date, date_to: date) -> Report:
        start, end = self._utc_range(date_from, date_to)
        rows = (
            (
                await self._session.execute(
                    select(Complaint)
                    .where(Complaint.created_at >= start, Complaint.created_at < end)
                    .order_by(Complaint.created_at)
                )
            )
            .scalars()
            .all()
        )
        detail: list[list[Any]] = []
        by_category: dict[str, list[int]] = {}
        for c in rows:
            hours = (
                round((c.resolved_at - c.created_at).total_seconds() / 3600, 1)
                if c.resolved_at
                else None
            )
            category = c.category.value.replace("_", " ").lower() if c.category else "uncategorised"
            counts = by_category.setdefault(category, [0, 0])
            counts[0] += 1
            counts[1] += 1 if c.status in RESOLVED_COMPLAINT else 0
            detail.append(
                [
                    self._local(c.created_at),
                    category,
                    _words(c.priority.value) if c.priority else None,
                    _words(c.status.value),
                    _words(c.department.value) if c.department else None,
                    c.location,
                    c.summary or c.raw_text,
                    self._local(c.resolved_at),
                    Decimal(str(hours)) if hours is not None else None,
                ]
            )
        summary = [
            [category, total, resolved, total - resolved]
            for category, (total, resolved) in sorted(
                by_category.items(), key=lambda kv: (-kv[1][0], kv[0])
            )
        ]
        return Report(
            title="Complaints report",
            subtitle=f"{_day(date_from)} to {_day(date_to)}  |  {len(rows)} complaint(s)",
            generated_at=self._now(),
            tables=[
                Table(
                    title="By category",
                    columns=[
                        Column("Category", width=18),
                        Column("Total", "int", 8),
                        Column("Resolved or closed", "int", 10),
                        Column("Open", "int", 8),
                    ],
                    rows=summary,
                    totals=[
                        "Total",
                        sum(r[1] for r in summary),
                        sum(r[2] for r in summary),
                        sum(r[3] for r in summary),
                    ],
                ),
                Table(
                    title="Complaints",
                    columns=[
                        Column("Filed", "datetime", 14),
                        Column("Category", width=12),
                        Column("Priority", width=8),
                        Column("Status", width=10),
                        Column("Department", width=12),
                        Column("Location", width=12),
                        Column("Summary", width=46),
                        Column("Resolved", "datetime", 14),
                        Column("Hours to resolve", "money", 9),
                    ],
                    rows=detail,
                ),
            ],
            notes=["Resident identities are intentionally omitted from this report."],
        )

    # --------------------------------------------------------------- leave

    async def leave(self, *, date_from: date, date_to: date) -> Report:
        rows = (
            await self._session.execute(
                select(LeaveRequest, Student.student_code, User.full_name)
                .join(Student, Student.id == LeaveRequest.student_id)
                .join(User, User.id == Student.user_id)
                .where(LeaveRequest.from_date <= date_to, LeaveRequest.to_date >= date_from)
                .order_by(LeaveRequest.from_date, Student.student_code)
            )
        ).all()
        return Report(
            title="Leave register",
            subtitle=f"Leave overlapping {_day(date_from)} to {_day(date_to)} ({len(rows)})",
            generated_at=self._now(),
            tables=[
                Table(
                    title="Leave",
                    columns=[
                        Column("Code", width=12),
                        Column("Name", width=20),
                        Column("Type", width=12),
                        Column("From", "date", 11),
                        Column("To", "date", 11),
                        Column("Days", "int", 6),
                        Column("Status", width=10),
                        Column("Destination", width=18),
                        Column("Guardian consent", width=9),
                        Column("Decided", "datetime", 14),
                    ],
                    rows=[
                        [
                            code,
                            name,
                            _words(leave.leave_type.value),
                            leave.from_date,
                            leave.to_date,
                            (leave.to_date - leave.from_date).days + 1,
                            _words(leave.status.value),
                            leave.destination,
                            "yes" if leave.guardian_consent else "no",
                            self._local(leave.decided_at),
                        ]
                        for leave, code, name in rows
                    ],
                )
            ],
        )
