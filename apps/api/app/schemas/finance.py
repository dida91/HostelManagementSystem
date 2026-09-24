from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import InvoiceStatus, LedgerEntryType, PaymentMethod
from app.schemas.common import ORMModel


class BalanceOut(BaseModel):
    currency: str = "NPR"
    total_charged: Decimal
    total_paid: Decimal
    outstanding: Decimal
    as_of: datetime


class LedgerEntryOut(ORMModel):
    id: uuid.UUID
    entry_type: LedgerEntryType
    amount_npr: Decimal
    description: str
    occurred_at: datetime


class LineItemIn(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_amount_npr: Decimal = Field(ge=0)


class InvoiceCreate(BaseModel):
    student_id: uuid.UUID
    period_start: date
    period_end: date
    due_date: date
    line_items: list[LineItemIn] = Field(min_length=1)
    note: str | None = Field(default=None, max_length=1000)


class InvoiceOut(ORMModel):
    id: uuid.UUID
    student_id: uuid.UUID
    invoice_number: str
    period_start: date
    period_end: date
    due_date: date
    status: InvoiceStatus
    billing_period: str | None = None
    total_npr: Decimal | None = None
    student_code: str | None = None
    student_name: str | None = None


class InvoiceLineOut(ORMModel):
    description: str
    quantity: Decimal
    unit_amount_npr: Decimal


class InvoiceDetailOut(InvoiceOut):
    note: str | None = None
    line_items: list[InvoiceLineOut] = []
    paid_npr: Decimal = Decimal("0")
    outstanding_npr: Decimal = Decimal("0")


class InvoiceGenerate(BaseModel):
    # Defaults to the current month in the hostel's timezone.
    period: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    # Defaults to INVOICE_DUE_DAY.
    due_day: int | None = Field(default=None, ge=1, le=28)


class InvoiceGenerationOut(BaseModel):
    billing_period: str
    created: int
    skipped_existing: int
    skipped_no_charges: int
    invoices: list[InvoiceOut]


Cadence = Literal["MONTHLY", "ONE_TIME"]


class FeeStructureCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    amount_npr: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    cadence: Cadence = "MONTHLY"
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def _window(self) -> FeeStructureCreate:
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be before effective_from")
        return self


class FeeStructureUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    amount_npr: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    cadence: Cadence | None = None
    effective_from: date | None = None
    effective_to: date | None = None


class FeeStructureOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None
    amount_npr: Decimal
    cadence: str
    effective_from: date
    effective_to: date | None


class PaymentCreate(BaseModel):
    student_id: uuid.UUID
    amount_npr: Decimal = Field(gt=0)
    method: PaymentMethod
    invoice_id: uuid.UUID | None = None
    reference_no: str | None = Field(default=None, max_length=120)
    paid_at: datetime | None = None


class PaymentOut(ORMModel):
    id: uuid.UUID
    student_id: uuid.UUID
    invoice_id: uuid.UUID | None = None
    amount_npr: Decimal
    method: PaymentMethod
    reference_no: str | None
    paid_at: datetime
