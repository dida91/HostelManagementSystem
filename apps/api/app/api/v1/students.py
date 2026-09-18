"""Student records. Staff manage; students read only their own."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep, require_roles
from app.core.errors import NotFoundError
from app.core.security import hash_password
from app.models.enums import StudentStatus, UserRole
from app.models.user import Student, User
from app.schemas.common import Page
from app.schemas.student import StudentCreate, StudentOut

router = APIRouter(prefix="/students", tags=["students"])
StaffOnly = Depends(require_roles(UserRole.STAFF, UserRole.WARDEN, UserRole.SUPER_ADMIN))


def _to_out(student: Student, user: User) -> StudentOut:
    return StudentOut(
        id=student.id,
        student_code=student.student_code,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        college=student.college,
        program=student.program,
        status=student.status,
        guardian_name=student.guardian_name,
        guardian_phone=student.guardian_phone,
        admission_date=student.admission_date,
    )


@router.get("", response_model=Page[StudentOut], dependencies=[StaffOnly])
async def list_students(
    session: SessionDep,
    status_filter: StudentStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[StudentOut]:
    stmt = select(Student, User).join(User, User.id == Student.user_id)
    count_stmt = select(func.count(Student.id))
    if status_filter is not None:
        stmt = stmt.where(Student.status == status_filter)
        count_stmt = count_stmt.where(Student.status == status_filter)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (
        await session.execute(stmt.order_by(Student.student_code).limit(limit).offset(offset))
    ).all()
    return Page(
        items=[_to_out(s, u) for s, u in rows],
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
async def create_student(payload: StudentCreate, session: SessionDep) -> StudentOut:
    """Register a resident. Creates the login and the student record together."""
    user = User(
        email=payload.email.lower().strip(),
        full_name=payload.full_name,
        phone=payload.phone,
        password_hash=hash_password(payload.initial_password),
        role=UserRole.STUDENT,
    )
    session.add(user)
    await session.flush()

    student = Student(
        user_id=user.id,
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
    session.add(student)
    await session.flush()
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
    return _to_out(student, owner)
