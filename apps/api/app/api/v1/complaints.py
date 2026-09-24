from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep, require_roles
from app.core.errors import PermissionDeniedError
from app.models.complaint import Complaint
from app.models.enums import ComplaintStatus, UserRole
from app.models.user import Student
from app.schemas.common import Page
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintDetailOut,
    ComplaintOut,
    ComplaintOverride,
)
from app.services.complaints import ComplaintService
from app.workers.enqueue import enqueue_after_commit

router = APIRouter(prefix="/complaints", tags=["complaints"])

StaffOnly = Depends(require_roles(UserRole.STAFF, UserRole.WARDEN, UserRole.SUPER_ADMIN))


async def _student_id_of(session, user) -> uuid.UUID | None:  # type: ignore[no-untyped-def]
    return (
        await session.execute(select(Student.id).where(Student.user_id == user.id))
    ).scalar_one_or_none()


@router.post("", response_model=ComplaintOut, status_code=status.HTTP_201_CREATED)
async def create_complaint(
    payload: ComplaintCreate, user: CurrentUser, session: SessionDep
) -> Complaint:
    """Submit a complaint.

    Returns immediately. AI analysis is queued to a background worker, so a slow
    or failing model never blocks a student from filing a complaint.
    """
    student_id = await _student_id_of(session, user)
    if student_id is None:
        raise PermissionDeniedError("Only student accounts can submit complaints.")

    complaint = await ComplaintService(session).create(student_id=student_id, text=payload.text)

    # Dispatched only after the request's transaction commits, so the worker is
    # guaranteed to find the row. If the broker is unreachable the complaint is
    # still safely stored.
    enqueue_after_commit(session, "ai.analyse_complaint", str(complaint.id))
    return complaint


@router.get("", response_model=Page[ComplaintOut])
async def list_complaints(
    user: CurrentUser,
    session: SessionDep,
    status_filter: list[ComplaintStatus] | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[ComplaintOut]:
    """Newest first. `status` may repeat (e.g. the open ones for triage)."""
    stmt = select(Complaint)
    count_stmt = select(func.count(Complaint.id))
    if status_filter:
        stmt = stmt.where(Complaint.status.in_(status_filter))
        count_stmt = count_stmt.where(Complaint.status.in_(status_filter))

    # Students are scoped to their own rows at the query level.
    if user.role is UserRole.STUDENT:
        student_id = await _student_id_of(session, user)
        if student_id is None:
            return Page(items=[], total=0, limit=limit, offset=offset)
        stmt = stmt.where(Complaint.student_id == student_id)
        count_stmt = count_stmt.where(Complaint.student_id == student_id)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(Complaint.created_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return Page(
        items=[ComplaintOut.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/{complaint_id}", response_model=ComplaintDetailOut)
async def get_complaint(
    complaint_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> ComplaintDetailOut:
    student_id = await _student_id_of(session, user)
    complaint = await ComplaintService(session).get_for_user(
        complaint_id=complaint_id, user=user, student_id=student_id
    )
    latest = complaint.analyses[0] if complaint.analyses else None
    out = ComplaintDetailOut.model_validate(complaint)
    if latest is not None:
        from app.schemas.complaint import ComplaintAIOut

        out.ai_analysis = ComplaintAIOut.model_validate(
            {**latest.__dict__, "status": latest.status.value}
        )
    return out


@router.patch("/{complaint_id}", response_model=ComplaintOut, dependencies=[StaffOnly])
async def override_complaint(
    complaint_id: uuid.UUID, payload: ComplaintOverride, user: CurrentUser, session: SessionDep
) -> Complaint:
    """Staff override of AI triage. Every change is audited."""
    service = ComplaintService(session)
    complaint = await service.get_for_user(complaint_id=complaint_id, user=user, student_id=None)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    note = changes.pop("note", None)
    return await service.override(complaint=complaint, actor=user, changes=changes, note=note)
