"""Fees, invoices, payments and the student ledger."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, SessionDep, require_roles
from app.core.clock import hostel_today
from app.core.config import get_settings
from app.core.errors import NotFoundError, PermissionDeniedError, ValidationFailedError
from app.models.enums import InvoiceStatus, UserRole
from app.models.finance import FeeInvoice, FeeStructure, Payment
from app.models.user import Student, User
from app.schemas.common import Page
from app.schemas.finance import (
    BalanceOut,
    FeeStructureCreate,
    FeeStructureOut,
    FeeStructureUpdate,
    InvoiceCreate,
    InvoiceDetailOut,
    InvoiceGenerate,
    InvoiceGenerationOut,
    InvoiceLineOut,
    InvoiceOut,
    LedgerEntryOut,
    PaymentCreate,
    PaymentOut,
)
from app.services.audit import record_audit
from app.services.finance import FinanceService, parse_billing_period

router = APIRouter(prefix="/fees", tags=["fees"])

StaffOnly = Depends(require_roles(UserRole.STAFF, UserRole.WARDEN, UserRole.SUPER_ADMIN))
WardenOnly = Depends(require_roles(UserRole.WARDEN, UserRole.SUPER_ADMIN))


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


async def _invoice_outs(session: SessionDep, invoices: list[FeeInvoice]) -> list[InvoiceOut]:
    amounts = await FinanceService(session).invoice_amounts([i.id for i in invoices])
    names = {
        sid: (code, name)
        for sid, code, name in (
            await session.execute(
                select(Student.id, Student.student_code, User.full_name)
                .join(User, User.id == Student.user_id)
                .where(Student.id.in_({i.student_id for i in invoices}))
            )
        ).all()
    }
    out = []
    for invoice in invoices:
        item = InvoiceOut.model_validate(invoice)
        item.total_npr = amounts[invoice.id][0]
        item.student_code, item.student_name = names.get(invoice.student_id, (None, None))
        out.append(item)
    return out


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


# ----------------------------------------------------------- fee structures


@router.get("/structures", response_model=list[FeeStructureOut], dependencies=[StaffOnly])
async def list_structures(session: SessionDep) -> list[FeeStructure]:
    """Fee schedule. MONTHLY structures in effect are billed by monthly
    invoicing alongside each resident's room rent."""
    return list(
        (
            await session.execute(
                select(FeeStructure).order_by(FeeStructure.effective_from.desc(), FeeStructure.name)
            )
        )
        .scalars()
        .all()
    )


@router.post(
    "/structures",
    response_model=FeeStructureOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[WardenOnly],
)
async def create_structure(
    payload: FeeStructureCreate, user: CurrentUser, session: SessionDep
) -> FeeStructure:
    structure = FeeStructure(**payload.model_dump())
    session.add(structure)
    await session.flush()
    record_audit(
        session,
        actor_id=user.id,
        action="fee_structure.create",
        entity_type="fee_structure",
        entity_id=structure.id,
        after=payload.model_dump(),
    )
    return structure


@router.patch(
    "/structures/{structure_id}", response_model=FeeStructureOut, dependencies=[WardenOnly]
)
async def update_structure(
    structure_id: uuid.UUID, payload: FeeStructureUpdate, user: CurrentUser, session: SessionDep
) -> FeeStructure:
    """Edit a fee. Invoices already issued keep the amounts they were issued
    with; to change a fee from a date, end this one and create a new one."""
    structure = await session.get(FeeStructure, structure_id)
    if structure is None:
        raise NotFoundError("Fee structure not found.")
    changes = payload.model_dump(exclude_unset=True)
    # description and effective_to may be cleared with an explicit null.
    changes = {
        k: v for k, v in changes.items() if v is not None or k in {"description", "effective_to"}
    }
    effective_from = changes.get("effective_from", structure.effective_from)
    effective_to = changes.get("effective_to", structure.effective_to)
    if effective_to is not None and effective_to < effective_from:
        raise ValidationFailedError("effective_to cannot be before effective_from.")

    before = {k: getattr(structure, k) for k in changes}
    for key, value in changes.items():
        setattr(structure, key, value)
    await session.flush()
    record_audit(
        session,
        actor_id=user.id,
        action="fee_structure.update",
        entity_type="fee_structure",
        entity_id=structure.id,
        before=before,
        after=changes,
    )
    return structure


@router.delete(
    "/structures/{structure_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[WardenOnly],
)
async def delete_structure(structure_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> None:
    """Remove a fee created by mistake. Issued invoices are unaffected: they
    carry their own line items."""
    structure = await session.get(FeeStructure, structure_id)
    if structure is None:
        raise NotFoundError("Fee structure not found.")
    record_audit(
        session,
        actor_id=user.id,
        action="fee_structure.delete",
        entity_type="fee_structure",
        entity_id=structure.id,
        before={
            "name": structure.name,
            "amount_npr": structure.amount_npr,
            "cadence": structure.cadence,
            "effective_from": structure.effective_from,
            "effective_to": structure.effective_to,
        },
    )
    await session.delete(structure)
    await session.flush()


# ----------------------------------------------------------------- invoices


@router.get("/invoices", response_model=Page[InvoiceOut])
async def list_invoices(
    user: CurrentUser,
    session: SessionDep,
    student_id: uuid.UUID | None = Query(default=None),
    status_filter: InvoiceStatus | None = Query(default=None, alias="status"),
    billing_period: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[InvoiceOut]:
    stmt = select(FeeInvoice)
    count_stmt = select(func.count(FeeInvoice.id))
    if user.role is UserRole.STUDENT or student_id is not None:
        sid = await _resolve_student(session, user, student_id)
        stmt = stmt.where(FeeInvoice.student_id == sid)
        count_stmt = count_stmt.where(FeeInvoice.student_id == sid)
    if status_filter is not None:
        stmt = stmt.where(FeeInvoice.status == status_filter)
        count_stmt = count_stmt.where(FeeInvoice.status == status_filter)
    if billing_period is not None:
        stmt = stmt.where(FeeInvoice.billing_period == billing_period)
        count_stmt = count_stmt.where(FeeInvoice.billing_period == billing_period)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(FeeInvoice.due_date.desc(), FeeInvoice.invoice_number.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return Page(
        items=await _invoice_outs(session, list(rows)),
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
async def create_invoice(payload: InvoiceCreate, session: SessionDep) -> InvoiceOut:
    invoice = await FinanceService(session).issue_invoice(
        student_id=payload.student_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        due_date=payload.due_date,
        line_items=[(li.description, li.quantity, li.unit_amount_npr) for li in payload.line_items],
        note=payload.note,
    )
    return (await _invoice_outs(session, [invoice]))[0]


@router.post(
    "/invoices/generate",
    response_model=InvoiceGenerationOut,
    dependencies=[WardenOnly],
)
async def generate_invoices(
    payload: InvoiceGenerate, user: CurrentUser, session: SessionDep
) -> InvoiceGenerationOut:
    """Bill every resident for a month: room rent plus MONTHLY fee structures.

    Runs automatically on the 1st of each month; this endpoint is for running
    it by hand (e.g. after fixing a fee). Safe to repeat: residents already
    billed for the month are skipped.
    """
    if payload.period:
        year, month = parse_billing_period(payload.period)
    else:
        today = hostel_today()
        year, month = today.year, today.month
    result = await FinanceService(session).generate_monthly_invoices(
        year=year,
        month=month,
        due_day=payload.due_day or get_settings().invoice_due_day,
    )
    record_audit(
        session,
        actor_id=user.id,
        action="invoices.generate",
        entity_type="billing_period",
        entity_id=result.billing_period,
        after=result.as_dict(),
    )
    return InvoiceGenerationOut(
        billing_period=result.billing_period,
        created=len(result.created),
        skipped_existing=result.skipped_existing,
        skipped_no_charges=result.skipped_no_charges,
        invoices=await _invoice_outs(session, result.created),
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetailOut)
async def get_invoice(
    invoice_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> InvoiceDetailOut:
    """An invoice with its line items and what remains to pay."""
    invoice = (
        await session.execute(
            select(FeeInvoice)
            .options(selectinload(FeeInvoice.line_items))
            .where(FeeInvoice.id == invoice_id)
        )
    ).scalar_one_or_none()
    if invoice is None:
        raise NotFoundError("Invoice not found.")
    if user.role is UserRole.STUDENT:
        own = (
            await session.execute(select(Student.id).where(Student.user_id == user.id))
        ).scalar_one_or_none()
        if own != invoice.student_id:
            # 404, not 403: other residents' invoices are not acknowledged.
            raise NotFoundError("Invoice not found.")

    total, paid = (await FinanceService(session).invoice_amounts([invoice.id]))[invoice.id]
    base = (await _invoice_outs(session, [invoice]))[0].model_dump()
    base["total_npr"] = total
    return InvoiceDetailOut(
        **base,
        note=invoice.note,
        line_items=[InvoiceLineOut.model_validate(li) for li in invoice.line_items],
        paid_npr=paid,
        outstanding_npr=total - paid,
    )


# ----------------------------------------------------------------- payments


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
