"""Fees, invoices, payments and the student ledger."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep, require_roles
from app.core.errors import PermissionDeniedError, ValidationFailedError
from app.models.enums import UserRole
from app.models.finance import FeeInvoice, Payment
from app.models.user import Student
from app.schemas.common import Page
from app.schemas.finance import (
    BalanceOut,
    InvoiceCreate,
    InvoiceOut,
    LedgerEntryOut,
    PaymentCreate,
    PaymentOut,
)
from app.services.finance import FinanceService

router = APIRouter(prefix="/fees", tags=["fees"])

StaffOnly = Depends(require_roles(UserRole.STAFF, UserRole.WARDEN, UserRole.SUPER_ADMIN))


async def _resolve_student(session, user, student_id: uuid.UUID | None) -> uuid.UUID:  # type: ignore[no-untyped-def]
    """Students may only ever address their own record.

    A student supplying someone else's id is refused rather than silently
    redirected, so the attempt is visible in logs.
    """
    own = (
        await session.execute(select(Student.id).where(Student.user_id == user.id))
    ).scalar_one_or_none()

    if user.role is UserRole.STUDENT:
        if own is None:
            raise PermissionDeniedError("This account has no student record.")
        if student_id is not None and student_id != own:
            raise PermissionDeniedError("You may only view your own fees.")
        return own

    if student_id is None:
        raise ValidationFailedError("student_id is required.")
    return student_id


@router.get("/balance", response_model=BalanceOut)
async def get_balance(
    user: CurrentUser, session: SessionDep, student_id: uuid.UUID | None = Query(default=None)
) -> BalanceOut:
    sid = await _resolve_student(session, user, student_id)
    totals = await FinanceService(session).balance_for(sid)
    return BalanceOut(
        total_charged=totals["total_charged"],
        total_paid=totals["total_paid"],
        outstanding=totals["outstanding"],
        as_of=datetime.now(UTC),
    )


@router.get("/ledger", response_model=list[LedgerEntryOut])
async def get_ledger(
    user: CurrentUser, session: SessionDep, student_id: uuid.UUID | None = Query(default=None)
) -> list[LedgerEntryOut]:
    sid = await _resolve_student(session, user, student_id)
    rows = await FinanceService(session).ledger_for(sid)
    return [LedgerEntryOut.model_validate(r) for r in rows]


@router.get("/invoices", response_model=Page[InvoiceOut])
async def list_invoices(
    user: CurrentUser,
    session: SessionDep,
    student_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[InvoiceOut]:
    stmt = select(FeeInvoice)
    count_stmt = select(func.count(FeeInvoice.id))
    if user.role is UserRole.STUDENT or student_id is not None:
        sid = await _resolve_student(session, user, student_id)
        stmt = stmt.where(FeeInvoice.student_id == sid)
        count_stmt = count_stmt.where(FeeInvoice.student_id == sid)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(FeeInvoice.due_date.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return Page(
        items=[InvoiceOut.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.post(
    "/invoices",
    response_model=InvoiceOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[StaffOnly],
)
async def create_invoice(payload: InvoiceCreate, session: SessionDep) -> FeeInvoice:
    return await FinanceService(session).issue_invoice(
        student_id=payload.student_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        due_date=payload.due_date,
        line_items=[(li.description, li.quantity, li.unit_amount_npr) for li in payload.line_items],
        note=payload.note,
    )


@router.post(
    "/payments",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[StaffOnly],
)
async def record_payment(
    payload: PaymentCreate,
    user: CurrentUser,
    session: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Payment:
    """Record a payment. An Idempotency-Key is required so a retried request
    cannot create a second credit."""
    if not idempotency_key:
        raise ValidationFailedError("An Idempotency-Key header is required.")
    return await FinanceService(session).record_payment(
        student_id=payload.student_id,
        amount=payload.amount_npr,
        method=payload.method,
        idempotency_key=idempotency_key,
        received_by_user_id=user.id,
        invoice_id=payload.invoice_id,
        reference_no=payload.reference_no,
        paid_at=payload.paid_at,
    )
