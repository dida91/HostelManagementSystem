"""Fee, payment and ledger logic.

Every monetary figure in this module is computed in SQL or Python from stored
rows. Nothing here is ever produced by, or passed through, a model.
"""

from __future__ import annotations

import calendar
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Sequence, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import hostel_today
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.core.logging import get_logger
from app.models.enums import (
    AssignmentStatus,
    InvoiceStatus,
    LedgerEntryType,
    PaymentMethod,
    PaymentStatus,
)
from app.models.finance import (
    FeeInvoice,
    FeeStructure,
    InvoiceLineItem,
    Payment,
    StudentLedgerEntry,
)
from app.models.hostel import Bed, BedAssignment, Block, Room
from app.models.user import Student
from app.services.notifications import (
    NotificationService,
    fee_overdue_message,
    fee_reminder_message,
    invoice_issued_message,
    payment_method_label,
    payment_received_message,
)

log = get_logger("services.finance")

# Created by migration 0004. A sequence cannot hand two concurrent requests the
# same number, unlike the count(*)+1 it replaced.
INVOICE_NUMBER_SEQ = Sequence("invoice_number_seq")
CENTS = Decimal("0.01")
UNPAID_STATUSES = (InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID)


@dataclass(slots=True)
class GenerationResult:
    billing_period: str
    created: list[FeeInvoice] = field(default_factory=list)
    skipped_existing: int = 0
    skipped_no_charges: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "billing_period": self.billing_period,
            "created": len(self.created),
            "skipped_existing": self.skipped_existing,
            "skipped_no_charges": self.skipped_no_charges,
        }


def parse_billing_period(period: str) -> tuple[int, int]:
    """'2026-10' -> (2026, 10)."""
    try:
        year_s, month_s = period.split("-")
        year, month = int(year_s), int(month_s)
    except ValueError as exc:
        raise ValidationFailedError("Billing period must look like 2026-10.") from exc
    if not (2000 <= year <= 2100 and 1 <= month <= 12):
        raise ValidationFailedError("Billing period must look like 2026-10.")
    return year, month


class FinanceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def balance_for(self, student_id: uuid.UUID) -> dict[str, Decimal]:
        """Outstanding balance, derived from the append-only ledger.

        There is no stored balance to drift or be overwritten.
        """
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
        row = (
            await self._session.execute(
                select(debit.label("d"), credit.label("c")).where(
                    StudentLedgerEntry.student_id == student_id
                )
            )
        ).one()
        charged = Decimal(row.d or 0)
        paid = Decimal(row.c or 0)
        return {
            "total_charged": charged,
            "total_paid": paid,
            "outstanding": charged - paid,
        }

    async def ledger_for(
        self, student_id: uuid.UUID, *, limit: int = 100
    ) -> list[StudentLedgerEntry]:
        return list(
            (
                await self._session.execute(
                    select(StudentLedgerEntry)
                    .where(StudentLedgerEntry.student_id == student_id)
                    .order_by(StudentLedgerEntry.occurred_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )

    async def invoice_amounts(
        self, invoice_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[Decimal, Decimal]]:
        """(total, paid) per invoice, from line items and recorded payments."""
        if not invoice_ids:
            return {}
        totals = dict(
            (
                await self._session.execute(
                    select(
                        InvoiceLineItem.invoice_id,
                        func.sum(InvoiceLineItem.quantity * InvoiceLineItem.unit_amount_npr),
                    )
                    .where(InvoiceLineItem.invoice_id.in_(invoice_ids))
                    .group_by(InvoiceLineItem.invoice_id)
                )
            )
            .tuples()
            .all()
        )
        paid = dict(
            (
                await self._session.execute(
                    select(Payment.invoice_id, func.sum(Payment.amount_npr))
                    .where(
                        Payment.invoice_id.in_(invoice_ids),
                        Payment.status == PaymentStatus.RECORDED,
                    )
                    .group_by(Payment.invoice_id)
                )
            )
            .tuples()
            .all()
        )
        return {
            i: (
                Decimal(totals.get(i) or 0).quantize(CENTS),
                Decimal(paid.get(i) or 0).quantize(CENTS),
            )
            for i in invoice_ids
        }

    async def issue_invoice(
        self,
        *,
        student_id: uuid.UUID,
        period_start: date,
        period_end: date,
        due_date: date,
        line_items: list[tuple[str, Decimal, Decimal]],
        note: str | None = None,
        billing_period: str | None = None,
    ) -> FeeInvoice:
        """Issue an invoice and post the matching DEBIT to the ledger, in one
        transaction, so the ledger can never disagree with the invoice."""
        if period_end < period_start:
            raise ValidationFailedError("Invoice period end cannot precede its start.")
        if not line_items:
            raise ValidationFailedError("An invoice needs at least one line item.")
        if await self._session.get(Student, student_id) is None:
            raise NotFoundError("Student not found.")

        total = Decimal("0")
        for _description, quantity, unit_amount in line_items:
            if quantity <= 0 or unit_amount < 0:
                raise ValidationFailedError("Invalid invoice line item.")
            total += quantity * unit_amount
        if total <= 0:
            raise ValidationFailedError("An invoice total must be greater than zero.")

        seq = (await self._session.execute(select(INVOICE_NUMBER_SEQ.next_value()))).scalar_one()
        invoice = FeeInvoice(
            student_id=student_id,
            invoice_number=f"INV-{datetime.now(UTC):%Y%m}-{int(seq):05d}",
            period_start=period_start,
            period_end=period_end,
            due_date=due_date,
            status=InvoiceStatus.ISSUED,
            note=note,
            billing_period=billing_period,
        )
        self._session.add(invoice)
        await self._session.flush()

        for description, quantity, unit_amount in line_items:
            self._session.add(
                InvoiceLineItem(
                    invoice_id=invoice.id,
                    description=description,
                    quantity=quantity,
                    unit_amount_npr=unit_amount,
                )
            )

        self._session.add(
            StudentLedgerEntry(
                student_id=student_id,
                entry_type=LedgerEntryType.DEBIT,
                amount_npr=total,
                description=f"Invoice {invoice.invoice_number}",
                invoice_id=invoice.id,
                occurred_at=datetime.now(UTC),
            )
        )
        await self._session.flush()
        await NotificationService(self._session).notify_student(
            student_id,
            invoice_issued_message(
                invoice_number=invoice.invoice_number,
                total=total.quantize(CENTS),
                due_date=due_date,
                period_start=period_start,
                period_end=period_end,
            ),
        )
        log.info(
            "invoice_issued",
            invoice_id=str(invoice.id),
            student_id=str(student_id),
            total=str(total),
        )
        return invoice

    async def generate_monthly_invoices(
        self, *, year: int, month: int, due_day: int
    ) -> GenerationResult:
        """Bill every resident for one month: room rent plus active monthly fees.

        A resident is anyone holding an ACTIVE bed that started on or before
        the month's last day. Safe to re-run: a student already billed for the
        month is skipped, and the partial unique index on (student,
        billing_period) makes a concurrent double-run fail safe rather than
        double-bill. Mid-month arrivals are billed the full month; prorating
        is left to the warden (issue a manual invoice instead).
        """
        last_day = calendar.monthrange(year, month)[1]
        period_start = date(year, month, 1)
        period_end = date(year, month, last_day)
        billing_period = f"{year:04d}-{month:02d}"
        due_date = date(year, month, min(due_day, last_day))
        label = f"{calendar.month_name[month]} {year}"

        structures = (
            (
                await self._session.execute(
                    select(FeeStructure)
                    .where(
                        FeeStructure.cadence == "MONTHLY",
                        FeeStructure.amount_npr > 0,
                        FeeStructure.effective_from <= period_end,
                        or_(
                            FeeStructure.effective_to.is_(None),
                            FeeStructure.effective_to >= period_start,
                        ),
                    )
                    .order_by(FeeStructure.name)
                )
            )
            .scalars()
            .all()
        )
        residents = (
            await self._session.execute(
                select(
                    BedAssignment.student_id,
                    Room.monthly_rate_npr,
                    Room.room_number,
                    Block.name,
                    Bed.bed_label,
                )
                .join(Bed, Bed.id == BedAssignment.bed_id)
                .join(Room, Room.id == Bed.room_id)
                .join(Block, Block.id == Room.block_id)
                .join(Student, Student.id == BedAssignment.student_id)
                .where(
                    BedAssignment.status == AssignmentStatus.ACTIVE,
                    BedAssignment.from_date <= period_end,
                )
                .order_by(Student.student_code)
            )
        ).all()
        already_billed = set(
            (
                await self._session.execute(
                    select(FeeInvoice.student_id).where(
                        FeeInvoice.billing_period == billing_period,
                        FeeInvoice.status != InvoiceStatus.VOID,
                    )
                )
            )
            .scalars()
            .all()
        )

        result = GenerationResult(billing_period=billing_period)
        for student_id, rate, room_number, block_name, bed_label in residents:
            if student_id in already_billed:
                result.skipped_existing += 1
                continue

            items: list[tuple[str, Decimal, Decimal]] = []
            if rate:
                items.append(
                    (
                        f"Room rent, {block_name} room {room_number} bed {bed_label} ({label})",
                        Decimal("1"),
                        Decimal(rate),
                    )
                )
            items += [(f"{s.name} ({label})", Decimal("1"), s.amount_npr) for s in structures]
            if not items:
                result.skipped_no_charges += 1
                continue

            try:
                async with self._session.begin_nested():
                    invoice = await self.issue_invoice(
                        student_id=student_id,
                        period_start=period_start,
                        period_end=period_end,
                        due_date=due_date,
                        line_items=items,
                        billing_period=billing_period,
                    )
            except IntegrityError:
                # A concurrent run billed this student first; the index held.
                result.skipped_existing += 1
                continue
            result.created.append(invoice)

        log.info("monthly_invoices_generated", **result.as_dict())
        return result

    async def mark_overdue(self, *, today: date) -> list[FeeInvoice]:
        """Move unpaid invoices past their due date to OVERDUE, notifying each
        student once per invoice."""
        invoices = (
            (
                await self._session.execute(
                    select(FeeInvoice)
                    .where(FeeInvoice.status.in_(UNPAID_STATUSES), FeeInvoice.due_date < today)
                    .order_by(FeeInvoice.due_date)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        amounts = await self.invoice_amounts([i.id for i in invoices])
        notifier = NotificationService(self._session)
        for invoice in invoices:
            invoice.status = InvoiceStatus.OVERDUE
            total, paid = amounts[invoice.id]
            await notifier.notify_student(
                invoice.student_id,
                fee_overdue_message(
                    invoice_number=invoice.invoice_number,
                    amount_due=total - paid,
                    due_date=invoice.due_date,
                ),
                dedupe_key=f"fee_overdue:{invoice.id}",
            )
        await self._session.flush()
        if invoices:
            log.info("invoices_marked_overdue", count=len(invoices))
        return list(invoices)

    async def send_due_reminders(self, *, today: date, days_before: int) -> int:
        """Remind students about unpaid invoices falling due within
        `days_before` days. Each invoice is reminded once, even if the job
        runs repeatedly or misses a day."""
        invoices = (
            (
                await self._session.execute(
                    select(FeeInvoice).where(
                        FeeInvoice.status.in_(UNPAID_STATUSES),
                        FeeInvoice.due_date >= today,
                        FeeInvoice.due_date <= today + timedelta(days=days_before),
                    )
                )
            )
            .scalars()
            .all()
        )
        amounts = await self.invoice_amounts([i.id for i in invoices])
        notifier = NotificationService(self._session)
        sent = 0
        for invoice in invoices:
            total, paid = amounts[invoice.id]
            if total - paid <= 0:
                continue
            sent += await notifier.notify_student(
                invoice.student_id,
                fee_reminder_message(
                    invoice_number=invoice.invoice_number,
                    amount_due=total - paid,
                    due_date=invoice.due_date,
                ),
                dedupe_key=f"fee_reminder:{invoice.id}:{invoice.due_date.isoformat()}",
            )
        return sent

    async def record_payment(
        self,
        *,
        student_id: uuid.UUID,
        amount: Decimal,
        method: PaymentMethod,
        idempotency_key: str,
        received_by_user_id: uuid.UUID | None,
        invoice_id: uuid.UUID | None = None,
        reference_no: str | None = None,
        paid_at: datetime | None = None,
    ) -> Payment:
        """Record a payment and post the matching CREDIT.

        The idempotency key makes a double-submitted payment a no-op rather than
        a duplicate credit -- important when staff record cash on a flaky
        connection.
        """
        if amount <= 0:
            raise ValidationFailedError("Payment amount must be positive.")

        existing = (
            await self._session.execute(
                select(Payment).where(Payment.idempotency_key == idempotency_key)
            )
        ).scalar_one_or_none()
        if existing is not None:
            log.info("payment_idempotent_replay", payment_id=str(existing.id))
            return existing

        if await self._session.get(Student, student_id) is None:
            raise NotFoundError("Student not found.")
        invoice: FeeInvoice | None = None
        if invoice_id is not None:
            invoice = await self._session.get(FeeInvoice, invoice_id)
            if invoice is None:
                raise NotFoundError("Invoice not found.")
            # Otherwise one student's payment could settle another's invoice.
            if invoice.student_id != student_id:
                raise ValidationFailedError("That invoice belongs to a different student.")
            if invoice.status is InvoiceStatus.VOID:
                raise ConflictError("That invoice has been voided.")

        payment = Payment(
            student_id=student_id,
            invoice_id=invoice_id,
            amount_npr=amount,
            method=method,
            reference_no=reference_no,
            paid_at=paid_at or datetime.now(UTC),
            received_by_user_id=received_by_user_id,
            status=PaymentStatus.RECORDED,
            idempotency_key=idempotency_key,
        )
        self._session.add(payment)
        await self._session.flush()

        self._session.add(
            StudentLedgerEntry(
                student_id=student_id,
                entry_type=LedgerEntryType.CREDIT,
                amount_npr=amount,
                # Residents read this line in their account history.
                description=(
                    f"Payment by {payment_method_label(method)}"
                    + (f" for {invoice.invoice_number}" if invoice else "")
                ),
                invoice_id=invoice_id,
                payment_id=payment.id,
                occurred_at=payment.paid_at,
            )
        )

        if invoice is not None:
            await self._settle_invoice(invoice)

        await self._session.flush()
        await NotificationService(self._session).notify_student(
            student_id,
            payment_received_message(
                amount=amount,
                method=method,
                invoice_number=invoice.invoice_number if invoice else None,
            ),
        )
        log.info("payment_recorded", payment_id=str(payment.id), amount=str(amount))
        return payment

    async def _settle_invoice(self, invoice: FeeInvoice) -> None:
        await self._session.flush()
        total, paid = (await self.invoice_amounts([invoice.id]))[invoice.id]
        if paid >= total:
            invoice.status = InvoiceStatus.PAID
        elif paid > 0:
            # A part payment does not cure lateness.
            invoice.status = (
                InvoiceStatus.OVERDUE
                if invoice.due_date < hostel_today()
                else InvoiceStatus.PARTIALLY_PAID
            )
