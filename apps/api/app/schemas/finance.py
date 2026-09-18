from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

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
    amount_npr: Decimal
    method: PaymentMethod
    reference_no: str | None
    paid_at: datetime
