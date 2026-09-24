"""Fees, payments and the student ledger.

Design note: there is deliberately NO writable `balance` column anywhere.
A student's outstanding balance is always derived as
    SUM(DEBIT) - SUM(CREDIT)  over student_ledger_entries
in SQL. This is what makes it structurally impossible for an AI code path --
or any other code path -- to invent or corrupt a financial figure.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey
from app.models.enums import InvoiceStatus, LedgerEntryType, PaymentMethod, PaymentStatus

# All monetary amounts: NPR, NUMERIC(12,2). Never float.
Money = Numeric(12, 2)


class FeeStructure(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "fee_structures"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    amount_npr: Mapped[Decimal] = mapped_column(Money, nullable=False)
    cadence: Mapped[str] = mapped_column(String(20), default="MONTHLY", nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        CheckConstraint("amount_npr >= 0", name="ck_fee_amount_nonneg"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_fee_effective_order",
        ),
    )


class FeeInvoice(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "fee_invoices"

    student_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    invoice_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status"), default=InvoiceStatus.DRAFT, nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)
    # "YYYY-MM" on invoices produced by monthly billing; NULL on manual ones.
    billing_period: Mapped[str | None] = mapped_column(String(7))

    line_items: Mapped[list[InvoiceLineItem]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("period_end >= period_start", name="ck_invoice_period_order"),
        CheckConstraint(
            "billing_period IS NULL OR billing_period ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'",
            name="ck_invoice_billing_period_format",
        ),
        Index("ix_invoices_student_status", "student_id", "status"),
        Index("ix_invoices_due", "due_date"),
        # One monthly-billing invoice per student per month, enforced by the
        # database: re-running the generator, or running it twice at once,
        # cannot bill anyone twice.
        Index(
            "uq_invoice_billing_period_per_student",
            "student_id",
            "billing_period",
            unique=True,
            postgresql_where=text("billing_period IS NOT NULL AND status <> 'VOID'"),
        ),
    )


class InvoiceLineItem(UUIDPrimaryKey, Base):
    __tablename__ = "invoice_line_items"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("fee_invoices.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("1"), nullable=False)
    unit_amount_npr: Mapped[Decimal] = mapped_column(Money, nullable=False)

    invoice: Mapped[FeeInvoice] = relationship(back_populates="line_items")

    __table_args__ = (CheckConstraint("quantity > 0", name="ck_line_qty_positive"),)


class Payment(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "payments"

    student_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("fee_invoices.id", ondelete="RESTRICT")
    )
    amount_npr: Mapped[Decimal] = mapped_column(Money, nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method"), nullable=False
    )
    reference_no: Mapped[str | None] = mapped_column(String(120))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"), default=PaymentStatus.RECORDED, nullable=False
    )
    # Guarantees a double-submitted payment is recorded exactly once.
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)

    __table_args__ = (
        CheckConstraint("amount_npr > 0", name="ck_payment_amount_positive"),
        Index("ix_payments_paid_at", "paid_at"),
    )


class StudentLedgerEntry(UUIDPrimaryKey, Base):
    """Append-only. Corrections are new reversing entries, never edits."""

    __tablename__ = "student_ledger_entries"

    student_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    entry_type: Mapped[LedgerEntryType] = mapped_column(
        Enum(LedgerEntryType, name="ledger_entry_type"), nullable=False
    )
    amount_npr: Mapped[Decimal] = mapped_column(Money, nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("fee_invoices.id", ondelete="RESTRICT")
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("payments.id", ondelete="RESTRICT")
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("amount_npr > 0", name="ck_ledger_amount_positive"),
        Index("ix_ledger_student_time", "student_id", "occurred_at"),
    )
