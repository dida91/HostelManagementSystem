"""Leave requests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep, require_roles
from app.core.errors import NotFoundError, PermissionDeniedError, ValidationFailedError
from app.models.enums import LeaveStatus, UserRole
from app.models.leave import LeaveRequest
from app.models.user import Student, User
from app.schemas.common import Page
from app.schemas.hostel import LeaveCreate, LeaveDecision, LeaveOut
from app.services.notifications import (
    APPROVER_ROLES,
    NotificationService,
    leave_decided_message,
    leave_requested_message,
)

router = APIRouter(prefix="/leave", tags=["leave"])
WardenOnly = Depends(require_roles(UserRole.WARDEN, UserRole.SUPER_ADMIN))
DECISIONS = {LeaveStatus.APPROVED, LeaveStatus.REJECTED}


async def _own_student_id(session, user) -> uuid.UUID | None:  # type: ignore[no-untyped-def]
    return (
        await session.execute(select(Student.id).where(Student.user_id == user.id))
    ).scalar_one_or_none()


async def _with_requester(session: SessionDep, leaves: list[LeaveRequest]) -> list[LeaveOut]:
    """Attach who asked, in one query for the whole page."""
    names = {
        sid: (code, name)
        for sid, code, name in (
            await session.execute(
                select(Student.id, Student.student_code, User.full_name)
                .join(User, User.id == Student.user_id)
                .where(Student.id.in_({leave.student_id for leave in leaves}))
            )
        ).all()
    }
    out = []
    for leave in leaves:
        item = LeaveOut.model_validate(leave)
        item.student_code, item.student_name = names.get(leave.student_id, (None, None))
        out.append(item)
    return out


@router.post("", response_model=LeaveOut, status_code=status.HTTP_201_CREATED)
async def request_leave(payload: LeaveCreate, user: CurrentUser, session: SessionDep) -> LeaveOut:
    student_id = await _own_student_id(session, user)
    if student_id is None:
        raise PermissionDeniedError("Only student accounts can request leave.")
    if payload.to_date < payload.from_date:
        raise ValidationFailedError("Leave end date cannot precede the start date.")

    leave = LeaveRequest(
        student_id=student_id,
        leave_type=payload.leave_type,
        from_date=payload.from_date,
        to_date=payload.to_date,
        reason=payload.reason,
        destination=payload.destination,
        guardian_consent=payload.guardian_consent,
        status=LeaveStatus.PENDING,
    )
    session.add(leave)
    await session.flush()

    name, code = (
        await session.execute(
            select(User.full_name, Student.student_code)
            .join(Student, Student.user_id == User.id)
            .where(Student.id == student_id)
        )
    ).one()
    await NotificationService(session).notify_roles(
        APPROVER_ROLES,
        leave_requested_message(
            student_name=name,
            student_code=code,
            leave_type=leave.leave_type.value,
            from_date=leave.from_date,
            to_date=leave.to_date,
            reason=leave.reason,
        ),
    )
    return (await _with_requester(session, [leave]))[0]


@router.get("", response_model=Page[LeaveOut])
async def list_leave(
    user: CurrentUser,
    session: SessionDep,
    status_filter: LeaveStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[LeaveOut]:
    stmt = select(LeaveRequest)
    count_stmt = select(func.count(LeaveRequest.id))

    if user.role is UserRole.STUDENT:
        sid = await _own_student_id(session, user)
        if sid is None:
            return Page(items=[], total=0, limit=limit, offset=offset)
        stmt = stmt.where(LeaveRequest.student_id == sid)
        count_stmt = count_stmt.where(LeaveRequest.student_id == sid)

    if status_filter is not None:
        stmt = stmt.where(LeaveRequest.status == status_filter)
        count_stmt = count_stmt.where(LeaveRequest.status == status_filter)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(LeaveRequest.from_date.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return Page(
        items=await _with_requester(session, list(rows)),
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.patch("/{leave_id}", response_model=LeaveOut, dependencies=[WardenOnly])
async def decide_leave(
    leave_id: uuid.UUID, payload: LeaveDecision, user: CurrentUser, session: SessionDep
) -> LeaveOut:
    leave = await session.get(LeaveRequest, leave_id)
    if leave is None:
        raise NotFoundError("Leave request not found.")
    if leave.status is not LeaveStatus.PENDING:
        raise ValidationFailedError("This request has already been decided.")
    if payload.status not in DECISIONS:
        raise ValidationFailedError("A decision must be APPROVED or REJECTED.")

    leave.status = payload.status
    leave.decision_note = payload.decision_note
    leave.approver_user_id = user.id
    leave.decided_at = datetime.now(UTC)
    await session.flush()
    await NotificationService(session).notify_student(
        leave.student_id,
        leave_decided_message(
            status=leave.status,
            leave_type=leave.leave_type.value,
            from_date=leave.from_date,
            to_date=leave.to_date,
            note=leave.decision_note,
        ),
    )
    return (await _with_requester(session, [leave]))[0]
