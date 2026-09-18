"""Fee, payment and ledger logic.

Every monetary figure in this module is computed in SQL or Python from stored
rows. Nothing here is ever produced by, or passed through, a model.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationFailedError
from app.core.logging import get_logger
from app.models.enums import InvoiceStatus, LedgerEntryType, PaymentMethod, PaymentStatus
from app.models.finance import (
    FeeInvoice,
    InvoiceLineItem,
    Payment,
    StudentLedgerEntry,
)

log = get_logger("services.finance")


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

    async def issue_invoice(
        self,
        *,
        student_id: uuid.UUID,
        period_start: date,
        period_end: date,
        due_date: date,
        line_items: list[tuple[str, Decimal, Decimal]],
        note: str | None = None,
    ) -> FeeInvoice:
        """Issue an invoice and post the matching DEBIT to the ledger, in one
        transaction, so the ledger can never disagree with the invoice."""
        if period_end < period_start:
            raise ValidationFailedError("Invoice period end cannot precede its start.")
        if not line_items:
            raise ValidationFailedError("An invoice needs at least one line item.")

        seq = (await self._session.execute(select(func.count(FeeInvoice.id)))).scalar_one()
        invoice = FeeInvoice(
            student_id=student_id,
            invoice_number=f"INV-{datetime.now(UTC):%Y%m}-{int(seq) + 1:05d}",
            period_start=period_start,
            period_end=period_end,
            due_date=due_date,
            status=InvoiceStatus.ISSUED,
            note=note,
        )
        self._session.add(invoice)
        await self._session.flush()

        total = Decimal("0")
        for description, quantity, unit_amount in line_items:
            if quantity <= 0 or unit_amount < 0:
                raise ValidationFailedError("Invalid invoice line item.")
            self._session.add(
                InvoiceLineItem(
                    invoice_id=invoice.id,
                    description=description,
                    quantity=quantity,
                    unit_amount_npr=unit_amount,
                )
            )
            total += quantity * unit_amount

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
        log.info(
            "invoice_issued",
            invoice_id=str(invoice.id),
            student_id=str(student_id),
            total=str(total),
        )
        return invoice

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
                description=f"Payment {payment.id}",
                invoice_id=invoice_id,
                payment_id=payment.id,
                occurred_at=payment.paid_at,
            )
        )

        if invoice_id is not None:
            await self._settle_invoice(invoice_id)

        await self._session.flush()
        log.info("payment_recorded", payment_id=str(payment.id), amount=str(amount))
        return payment

    async def _settle_invoice(self, invoice_id: uuid.UUID) -> None:
        invoice = await self._session.get(FeeInvoice, invoice_id)
        if invoice is None:
            raise NotFoundError("Invoice not found.")

        total = (
            await self._session.execute(
                select(
                    func.coalesce(
                        func.sum(InvoiceLineItem.quantity * InvoiceLineItem.unit_amount_npr), 0
                    )
                ).where(InvoiceLineItem.invoice_id == invoice_id)
            )
        ).scalar_one()
        paid = (
            await self._session.execute(
                select(func.coalesce(func.sum(Payment.amount_npr), 0)).where(
                    Payment.invoice_id == invoice_id,
                    Payment.status == PaymentStatus.RECORDED,
                )
            )
        ).scalar_one()

        if Decimal(paid) >= Decimal(total):
            invoice.status = InvoiceStatus.PAID
        elif Decimal(paid) > 0:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
