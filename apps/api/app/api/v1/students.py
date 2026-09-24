"""Student records. Staff manage; students read only their own."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, SessionDep, require_roles
from app.core.errors import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.enums import StudentStatus, UserRole
from app.models.user import Student, User
from app.schemas.common import Page
from app.schemas.student import (
    DeactivationOut,
    PasswordReset,
    StudentCreate,
    StudentDeactivate,
    StudentOut,
    StudentUpdate,
)
from app.services.audit import record_audit
from app.services.rooms import active_room_labels
from app.services.students import StudentService

router = APIRouter(prefix="/students", tags=["students"])
StaffOnly = Depends(require_roles(UserRole.STAFF, UserRole.WARDEN, UserRole.SUPER_ADMIN))
WardenOnly = Depends(require_roles(UserRole.WARDEN, UserRole.SUPER_ADMIN))
# Profile fields that may be cleared with an explicit null.
NULLABLE_FIELDS = set(StudentUpdate.model_fields) - {"full_name", "email"}


def _to_out(student: Student, user: User, room: str | None = None) -> StudentOut:
    return StudentOut(
        id=student.id,
        student_code=student.student_code,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        college=student.college,
        program=student.program,
        status=student.status,
        is_active=user.is_active,
        guardian_name=student.guardian_name,
        guardian_phone=student.guardian_phone,
        guardian_relation=student.guardian_relation,
        emergency_contact=student.emergency_contact,
        permanent_address=student.permanent_address,
        admission_date=student.admission_date,
        date_of_birth=student.date_of_birth,
        room=room,
    )


async def _out(session: SessionDep, student: Student, user: User) -> StudentOut:
    rooms = await active_room_labels(session, [student.id])
    return _to_out(student, user, rooms.get(student.id))


@router.get("", response_model=Page[StudentOut], dependencies=[StaffOnly])
async def list_students(
    session: SessionDep,
    status_filter: StudentStatus | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, min_length=1, max_length=80),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[StudentOut]:
    stmt = select(Student, User).join(User, User.id == Student.user_id)
    count_stmt = select(func.count(Student.id)).join(User, User.id == Student.user_id)
    if status_filter is not None:
        stmt = stmt.where(Student.status == status_filter)
        count_stmt = count_stmt.where(Student.status == status_filter)
    if q:
        pattern = f"%{q.strip()}%"
        match = or_(
            User.full_name.ilike(pattern),
            User.email.ilike(pattern),
            Student.student_code.ilike(pattern),
        )
        stmt = stmt.where(match)
        count_stmt = count_stmt.where(match)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (
        await session.execute(stmt.order_by(Student.student_code).limit(limit).offset(offset))
    ).all()
    rooms = await active_room_labels(session, [s.id for s, _ in rows])
    return Page(
        items=[_to_out(s, u, rooms.get(s.id)) for s, u in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=StudentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[StaffOnly],
)
async def create_student(
    payload: StudentCreate, actor: CurrentUser, session: SessionDep
) -> StudentOut:
    """Register a resident. Creates the login and the student record together."""
    user = User(
        email=payload.email.lower().strip(),
        full_name=payload.full_name,
        phone=payload.phone,
        password_hash=hash_password(payload.initial_password),
        role=UserRole.STUDENT,
    )
    student = Student(
        student_code=payload.student_code,
        college=payload.college,
        program=payload.program,
        guardian_name=payload.guardian_name,
        guardian_phone=payload.guardian_phone,
        emergency_contact=payload.emergency_contact,
        permanent_address=payload.permanent_address,
        admission_date=payload.admission_date,
        date_of_birth=payload.date_of_birth,
        status=StudentStatus.ACTIVE,
    )
    try:
        async with session.begin_nested():
            session.add(user)
            await session.flush()
            student.user_id = user.id
            session.add(student)
            await session.flush()
    except IntegrityError as exc:
        raise ConflictError(
            "That email, phone number or student code is already registered."
        ) from exc
    record_audit(
        session,
        actor_id=actor.id,
        action="student.create",
        entity_type="student",
        entity_id=student.id,
        after={"student_code": student.student_code, "email": user.email},
    )
    return _to_out(student, user)


@router.get("/{student_id}", response_model=StudentOut)
async def get_student(student_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> StudentOut:
    row = (
        await session.execute(
            select(Student, User)
            .join(User, User.id == Student.user_id)
            .where(Student.id == student_id)
        )
    ).first()
    if row is None:
        raise NotFoundError("Student not found.")
    student, owner = row

    # A student may read only their own record, and gets 404 for anyone else's
    # so the existence of other residents is not disclosed.
    if user.role is UserRole.STUDENT and owner.id != user.id:
        raise NotFoundError("Student not found.")
    return await _out(session, student, owner)


@router.patch("/{student_id}", response_model=StudentOut, dependencies=[StaffOnly])
async def update_student(
    student_id: uuid.UUID, payload: StudentUpdate, actor: CurrentUser, session: SessionDep
) -> StudentOut:
    """Edit a resident's profile. Every change is audited."""
    service = StudentService(session)
    student, user = await service.get_with_user(student_id)
    changes = {
        k: v
        for k, v in payload.model_dump(exclude_unset=True).items()
        if v is not None or k in NULLABLE_FIELDS
    }
    await service.update_profile(student, user, changes, actor=actor)
    return await _out(session, student, user)


@router.post("/{student_id}/deactivate", response_model=DeactivationOut, dependencies=[WardenOnly])
async def deactivate_student(
    student_id: uuid.UUID, payload: StudentDeactivate, actor: CurrentUser, session: SessionDep
) -> DeactivationOut:
    """Check a resident out (ALUMNI) or suspend them.

    Sign-in is disabled immediately and every session revoked. The resident's
    bed is vacated (always for ALUMNI). Fees, complaints and leave history are
    kept.
    """
    service = StudentService(session)
    student, user = await service.get_with_user(student_id)
    ended = await service.deactivate(
        student,
        user,
        status=payload.status,
        reason=payload.reason,
        vacate_bed=payload.vacate_bed,
        leaving_date=payload.leaving_date,
        actor=actor,
    )
    return DeactivationOut(student=await _out(session, student, user), ended_assignment_id=ended)


@router.post("/{student_id}/reactivate", response_model=StudentOut, dependencies=[WardenOnly])
async def reactivate_student(
    student_id: uuid.UUID, actor: CurrentUser, session: SessionDep
) -> StudentOut:
    """Restore an ALUMNI or SUSPENDED resident to ACTIVE and re-enable sign-in.
    A bed is not re-allocated automatically."""
    service = StudentService(session)
    student, user = await service.get_with_user(student_id)
    await service.reactivate(student, user, actor=actor)
    return await _out(session, student, user)


@router.post(
    "/{student_id}/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[WardenOnly],
)
async def reset_password(
    student_id: uuid.UUID, payload: PasswordReset, actor: CurrentUser, session: SessionDep
) -> None:
    """Set a new password for a resident who has lost theirs. All of their
    sessions are signed out and they are notified."""
    service = StudentService(session)
    student, user = await service.get_with_user(student_id)
    await service.reset_password(student, user, new_password=payload.new_password, actor=actor)
