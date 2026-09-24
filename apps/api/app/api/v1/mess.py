"""Mess menu and feedback."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, SessionDep, require_roles
from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.models.enums import MealType, UserRole
from app.models.mess import MessFeedback, MessMenu
from app.models.user import Student
from app.schemas.common import Page
from app.schemas.hostel import MenuOut, MenuUpsert, MessFeedbackCreate, MessFeedbackOut
from app.workers.enqueue import enqueue_after_commit

router = APIRouter(prefix="/mess", tags=["mess"])
StaffOnly = Depends(require_roles(UserRole.STAFF, UserRole.WARDEN, UserRole.SUPER_ADMIN))
DayOfWeek = Path(ge=0, le=6, description="0 = Sunday")


@router.get("/menu", response_model=list[MenuOut])
async def get_menu(
    session: SessionDep, day_of_week: int | None = Query(default=None, ge=0, le=6)
) -> list[MenuOut]:
    stmt = select(MessMenu)
    if day_of_week is not None:
        stmt = stmt.where(MessMenu.day_of_week == day_of_week)
    rows = (
        (await session.execute(stmt.order_by(MessMenu.day_of_week, MessMenu.meal_type)))
        .scalars()
        .all()
    )
    return [MenuOut.model_validate(r) for r in rows]


@router.put("/menu/{day_of_week}/{meal_type}", response_model=MenuOut, dependencies=[StaffOnly])
async def set_menu(
    meal_type: MealType,
    payload: MenuUpsert,
    session: SessionDep,
    day_of_week: int = DayOfWeek,
) -> MenuOut:
    """Set what is served for one meal on one day of the week (create or replace)."""
    stmt = (
        pg_insert(MessMenu)
        .values(
            day_of_week=day_of_week,
            meal_type=meal_type,
            items=payload.items.strip(),
            serving_time=payload.serving_time,
        )
        .on_conflict_do_update(
            constraint="uq_menu_day_meal",
            set_={
                "items": payload.items.strip(),
                "serving_time": payload.serving_time,
                "updated_at": func.now(),
            },
        )
        .returning(MessMenu.day_of_week, MessMenu.meal_type, MessMenu.items, MessMenu.serving_time)
    )
    row = (await session.execute(stmt)).one()
    return MenuOut(
        day_of_week=row.day_of_week,
        meal_type=row.meal_type,
        items=row.items,
        serving_time=row.serving_time,
    )


@router.delete(
    "/menu/{day_of_week}/{meal_type}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[StaffOnly],
)
async def remove_menu(
    meal_type: MealType, session: SessionDep, day_of_week: int = DayOfWeek
) -> None:
    """Stop serving a meal on that day (e.g. no snacks on Saturday)."""
    result = await session.execute(
        delete(MessMenu).where(MessMenu.day_of_week == day_of_week, MessMenu.meal_type == meal_type)
    )
    if not result.rowcount:  # type: ignore[attr-defined]
        raise NotFoundError("No menu is set for that meal.")


@router.post("/feedback", response_model=MessFeedbackOut, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    payload: MessFeedbackCreate, user: CurrentUser, session: SessionDep
) -> MessFeedbackOut:
    """Submit mess feedback.

    The rating and comment are stored exactly as written. AI analysis is a
    separate derived record produced in the background.
    """
    student_id = (
        await session.execute(select(Student.id).where(Student.user_id == user.id))
    ).scalar_one_or_none()
    if student_id is None:
        raise PermissionDeniedError("Only student accounts can submit mess feedback.")

    duplicate = (
        await session.execute(
            select(MessFeedback.id).where(
                MessFeedback.student_id == student_id,
                MessFeedback.meal_date == payload.meal_date,
                MessFeedback.meal_type == payload.meal_type,
            )
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise ConflictError("You have already given feedback for this meal.")

    feedback = MessFeedback(
        student_id=student_id,
        meal_date=payload.meal_date,
        meal_type=payload.meal_type,
        rating=payload.rating,
        comment=payload.comment,
    )
    session.add(feedback)
    await session.flush()

    if payload.comment:
        # Queued after commit so the worker is guaranteed to find the row. The
        # feedback is stored regardless of whether queueing succeeds.
        enqueue_after_commit(session, "ai.analyse_mess_feedback", str(feedback.id))

    # Built explicitly rather than serialised from the ORM instance: touching
    # `analysis` here would lazy-load outside the async context. The analysis is
    # produced in the background and is always absent at this point.
    return MessFeedbackOut(
        id=feedback.id,
        meal_date=feedback.meal_date,
        meal_type=feedback.meal_type,
        rating=feedback.rating,
        comment=feedback.comment,
        created_at=feedback.created_at,
        analysis=None,
    )


@router.get("/feedback", response_model=Page[MessFeedbackOut])
async def list_feedback(
    user: CurrentUser,
    session: SessionDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[MessFeedbackOut]:
    stmt = select(MessFeedback).options(selectinload(MessFeedback.analysis))
    count_stmt = select(func.count(MessFeedback.id))

    if user.role is UserRole.STUDENT:
        sid = (
            await session.execute(select(Student.id).where(Student.user_id == user.id))
        ).scalar_one_or_none()
        if sid is None:
            return Page(items=[], total=0, limit=limit, offset=offset)
        stmt = stmt.where(MessFeedback.student_id == sid)
        count_stmt = count_stmt.where(MessFeedback.student_id == sid)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(MessFeedback.meal_date.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return Page(
        items=[MessFeedbackOut.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )
