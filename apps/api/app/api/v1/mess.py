"""Mess menu and feedback."""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, SessionDep
from app.core.errors import ConflictError, PermissionDeniedError
from app.models.enums import UserRole
from app.models.mess import MessFeedback, MessMenu
from app.models.user import Student
from app.schemas.common import Page
from app.schemas.hostel import MenuOut, MessFeedbackCreate, MessFeedbackOut

router = APIRouter(prefix="/mess", tags=["mess"])


@router.get("/menu", response_model=list[MenuOut])
async def get_menu(
    session: SessionDep, day_of_week: int | None = Query(default=None, ge=0, le=6)
) -> list[MenuOut]:
    stmt = select(MessMenu)
    if day_of_week is not None:
        stmt = stmt.where(MessMenu.day_of_week == day_of_week)
    rows = (await session.execute(stmt.order_by(MessMenu.day_of_week))).scalars().all()
    return [MenuOut.model_validate(r) for r in rows]


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
        from app.workers.tasks.ai_tasks import analyse_mess_feedback_task

        try:
            analyse_mess_feedback_task.delay(str(feedback.id))
        except Exception:  # noqa: BLE001 - feedback is stored regardless
            from app.core.logging import get_logger

            get_logger("api.mess").error("ai_task_enqueue_failed", feedback_id=str(feedback.id))

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
