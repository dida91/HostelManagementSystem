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
from app.models.user import Student
from app.schemas.common import Page
from app.schemas.hostel import LeaveCreate, LeaveDecision, LeaveOut

router = APIRouter(prefix="/leave", tags=["leave"])
WardenOnly = Depends(require_roles(UserRole.WARDEN, UserRole.SUPER_ADMIN))


async def _own_student_id(session, user) -> uuid.UUID | None:  # type: ignore[no-untyped-def]
    return (
        await session.execute(select(Student.id).where(Student.user_id == user.id))
    ).scalar_one_or_none()


@router.post("", response_model=LeaveOut, status_code=status.HTTP_201_CREATED)
async def request_leave(
    payload: LeaveCreate, user: CurrentUser, session: SessionDep
) -> LeaveRequest:
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
    return leave


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
        items=[LeaveOut.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.patch("/{leave_id}", response_model=LeaveOut, dependencies=[WardenOnly])
async def decide_leave(
    leave_id: uuid.UUID, payload: LeaveDecision, user: CurrentUser, session: SessionDep
) -> LeaveRequest:
    leave = await session.get(LeaveRequest, leave_id)
    if leave is None:
        raise NotFoundError("Leave request not found.")
    if leave.status is not LeaveStatus.PENDING:
        raise ValidationFailedError("This request has already been decided.")

    leave.status = payload.status
    leave.decision_note = payload.decision_note
    leave.approver_user_id = user.id
    leave.decided_at = datetime.now(UTC)
    await session.flush()
    return leave
