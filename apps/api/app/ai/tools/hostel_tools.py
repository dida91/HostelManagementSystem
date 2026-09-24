"""Concrete backend tools.

Every figure returned here comes from PostgreSQL. The model receives computed
results and may explain them, but never produces them itself.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select

from app.ai.tools.registry import ToolContext, registry
from app.core.errors import PermissionDeniedError
from app.models.complaint import Complaint
from app.models.enums import (
    AssignmentStatus,
    LeaveStatus,
    LeaveType,
    LedgerEntryType,
    UserRole,
)
from app.models.finance import StudentLedgerEntry
from app.models.hostel import Bed, BedAssignment, Block, Room
from app.models.leave import LeaveRequest
from app.models.mess import Announcement, MessMenu
from app.models.user import Student, User
from app.services.announcements import visible_audiences

ALL_ROLES = {UserRole.STUDENT, UserRole.STAFF, UserRole.WARDEN, UserRole.SUPER_ADMIN}
STAFF_ROLES = {UserRole.STAFF, UserRole.WARDEN, UserRole.SUPER_ADMIN}


def _require_student(ctx: ToolContext) -> Any:
    """Resolve the caller's own student record.

    Note there is no student_id parameter anywhere in this file's self-scoped
    tools -- the identity comes from the authenticated principal only.
    """
    if ctx.principal.student_id is None:
        raise PermissionDeniedError("This tool is only available to student accounts.")
    return ctx.principal.student_id


# --------------------------------------------------------------------------
# Self-scoped read tools (no identity arguments by design)
# --------------------------------------------------------------------------


@registry.register(
    name="get_student_profile",
    description=(
        "Get the signed-in student's own profile details (name, student code, college, status)."
    ),
    allowed_roles=ALL_ROLES,
)
async def get_student_profile(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sid = _require_student(ctx)
    row = (
        await ctx.session.execute(
            select(Student, User).join(User, User.id == Student.user_id).where(Student.id == sid)
        )
    ).first()
    if row is None:
        return {"error": "not_found", "message": "Student profile not found."}
    student, user = row
    return {
        "student_code": student.student_code,
        "full_name": user.full_name,
        "college": student.college,
        "program": student.program,
        "status": student.status.value,
        "admission_date": student.admission_date.isoformat() if student.admission_date else None,
    }


@registry.register(
    name="get_room_assignment",
    description="Get the signed-in student's current room and bed assignment.",
    allowed_roles=ALL_ROLES,
)
async def get_room_assignment(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sid = _require_student(ctx)
    row = (
        await ctx.session.execute(
            select(BedAssignment, Bed, Room, Block)
            .join(Bed, Bed.id == BedAssignment.bed_id)
            .join(Room, Room.id == Bed.room_id)
            .join(Block, Block.id == Room.block_id)
            .where(
                BedAssignment.student_id == sid,
                BedAssignment.status == AssignmentStatus.ACTIVE,
            )
        )
    ).first()
    if row is None:
        return {"assigned": False, "message": "No active room assignment."}
    assignment, bed, room, block = row
    return {
        "assigned": True,
        "block": block.name,
        "floor": room.floor,
        "room_number": room.room_number,
        "bed_label": bed.bed_label,
        "room_type": room.room_type.value,
        "since": assignment.from_date.isoformat(),
    }


@registry.register(
    name="get_fee_balance",
    description=(
        "Get the signed-in student's current outstanding fee balance in NPR. "
        "This figure is computed by the database from the ledger; use it exactly as given."
    ),
    allowed_roles=ALL_ROLES,
)
async def get_fee_balance(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sid = _require_student(ctx)
    # Balance is derived in SQL, never stored and never computed by the model.
    debit = func.coalesce(
        func.sum(StudentLedgerEntry.amount_npr).filter(
            StudentLedgerEntry.entry_type == LedgerEntryType.DEBIT
        ),
        0,
    )
    credit = func.coalesce(
        func.sum(StudentLedgerEntry.amount_npr).filter(
            StudentLedgerEntry.entry_type == LedgerEntryType.CREDIT
        ),
        0,
    )
    row = (
        await ctx.session.execute(
            select(debit.label("d"), credit.label("c")).where(StudentLedgerEntry.student_id == sid)
        )
    ).one()
    charged, paid = row.d or 0, row.c or 0
    return {
        "currency": "NPR",
        "total_charged": str(charged),
        "total_paid": str(paid),
        "outstanding_balance": str(charged - paid),
        "as_of": datetime.now(UTC).isoformat(),
    }


@registry.register(
    name="get_leave_requests",
    description="List the signed-in student's own leave requests, most recent first.",
    parameters={
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": [s.value for s in LeaveStatus],
                "description": "Optional filter by status.",
            }
        },
    },
    allowed_roles=ALL_ROLES,
)
async def get_leave_requests(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sid = _require_student(ctx)
    stmt = select(LeaveRequest).where(LeaveRequest.student_id == sid)
    if status := args.get("status"):
        try:
            stmt = stmt.where(LeaveRequest.status == LeaveStatus(status))
        except ValueError:
            return {"error": "bad_argument", "message": f"Unknown status: {status}"}
    stmt = stmt.order_by(LeaveRequest.from_date.desc()).limit(20)
    rows = (await ctx.session.execute(stmt)).scalars().all()
    return {
        "count": len(rows),
        "leave_requests": [
            {
                "id": str(r.id),
                "type": r.leave_type.value,
                "status": r.status.value,
                "from_date": r.from_date.isoformat(),
                "to_date": r.to_date.isoformat(),
                "reason": r.reason,
            }
            for r in rows
        ],
    }


@registry.register(
    name="get_complaint_status",
    description="List the signed-in student's own complaints and their current status.",
    allowed_roles=ALL_ROLES,
)
async def get_complaint_status(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sid = _require_student(ctx)
    rows = (
        (
            await ctx.session.execute(
                select(Complaint)
                .where(Complaint.student_id == sid)
                .order_by(Complaint.created_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    return {
        "count": len(rows),
        "complaints": [
            {
                "id": str(r.id),
                "status": r.status.value,
                "category": r.category.value if r.category else None,
                "priority": r.priority.value if r.priority else None,
                "summary": r.summary,
                "submitted_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


# --------------------------------------------------------------------------
# Shared read tools (non-personal data)
# --------------------------------------------------------------------------


@registry.register(
    name="get_mess_information",
    description="Get the mess menu and serving times for a given day of the week.",
    parameters={
        "type": "object",
        "properties": {
            "day_of_week": {
                "type": "integer",
                "description": "0=Sunday through 6=Saturday. Omit for the whole week.",
            }
        },
    },
    allowed_roles=ALL_ROLES,
)
async def get_mess_information(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    stmt = select(MessMenu)
    dow = args.get("day_of_week")
    if dow is not None:
        if not isinstance(dow, int) or not 0 <= dow <= 6:
            return {"error": "bad_argument", "message": "day_of_week must be 0-6."}
        stmt = stmt.where(MessMenu.day_of_week == dow)
    rows = (await ctx.session.execute(stmt.order_by(MessMenu.day_of_week))).scalars().all()
    return {
        "count": len(rows),
        "menu": [
            {
                "day_of_week": r.day_of_week,
                "meal": r.meal_type.value,
                "items": r.items,
                "serving_time": r.serving_time,
            }
            for r in rows
        ],
    }


@registry.register(
    name="search_announcements",
    description="Search currently active hostel announcements and notices.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Optional keyword filter."}},
    },
    allowed_roles=ALL_ROLES,
)
async def search_announcements(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC)
    stmt = select(Announcement).where(
        Announcement.publish_at <= now,
        (Announcement.expires_at.is_(None)) | (Announcement.expires_at >= now),
        # Same audience rule as the announcements API: the assistant must not
        # become a way for students to read staff-only notices.
        Announcement.audience.in_(visible_audiences(ctx.principal.role)),
    )
    if q := args.get("query"):
        stmt = stmt.where(Announcement.title.ilike(f"%{q}%") | Announcement.body.ilike(f"%{q}%"))
    rows = (
        (await ctx.session.execute(stmt.order_by(Announcement.publish_at.desc()).limit(10)))
        .scalars()
        .all()
    )
    return {
        "count": len(rows),
        "announcements": [
            {"title": r.title, "body": r.body, "published_at": r.publish_at.isoformat()}
            for r in rows
        ],
    }


# --------------------------------------------------------------------------
# Staff-only read tools
# --------------------------------------------------------------------------


@registry.register(
    name="get_occupancy_summary",
    description=(
        "Get current hostel occupancy: total beds, occupied beds and vacancy count. "
        "Staff only. Figures are counted by the database."
    ),
    allowed_roles=STAFF_ROLES,
)
async def get_occupancy_summary(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    total_beds = (await ctx.session.execute(select(func.count(Bed.id)))).scalar_one()
    occupied = (
        await ctx.session.execute(
            select(func.count(BedAssignment.id)).where(
                BedAssignment.status == AssignmentStatus.ACTIVE
            )
        )
    ).scalar_one()
    return {
        "total_beds": int(total_beds),
        "occupied_beds": int(occupied),
        "vacant_beds": int(total_beds) - int(occupied),
        "occupancy_rate_percent": round(100 * occupied / total_beds, 1) if total_beds else 0.0,
        "as_of": datetime.now(UTC).isoformat(),
    }


# --------------------------------------------------------------------------
# Document search (feeds the assistant's policy answers)
# --------------------------------------------------------------------------


@registry.register(
    name="search_hostel_documents",
    description=(
        "Search official hostel documents (rules, fee/leave/mess policies, notices) "
        "for a question about policy. Returns passages with their source, which you "
        "must cite. Use this for any rules question rather than answering from memory."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The policy question to search for."}
        },
        "required": ["query"],
    },
    allowed_roles=ALL_ROLES,
)
async def search_hostel_documents(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    query = (args.get("query") or "").strip()
    if not query:
        return {"error": "bad_argument", "message": "A query is required."}

    from app.ai.providers.registry import get_embedding_provider
    from app.ai.services.embeddings import EmbeddingService
    from app.ai.services.retrieval import RetrievalService

    embeddings = EmbeddingService(get_embedding_provider())
    vector = await embeddings.embed_query(
        session=ctx.session, text=query, user_id=ctx.principal.user_id
    )
    chunks = await RetrievalService(embedding_model=embeddings.model_name).retrieve(
        session=ctx.session, query=query, query_vector=vector, top_k=5
    )
    if not chunks:
        return {
            "found": False,
            "message": "No hostel document covers this. Say so rather than guessing.",
        }
    return {
        "found": True,
        "passages": [
            {
                "source": c.source_label,
                "document_title": c.document_title,
                "page_number": c.page_number,
                "section": c.section_path,
                "text": c.text,
            }
            for c in chunks
        ],
    }


# --------------------------------------------------------------------------
# Write tools -- never auto-executed; the UI confirms with the user first
# --------------------------------------------------------------------------


@registry.register(
    name="create_complaint",
    description=(
        "File a new complaint on behalf of the signed-in student. Only call this "
        "after the student has clearly confirmed they want it filed."
    ),
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The complaint in the student's own words.",
            }
        },
        "required": ["text"],
    },
    allowed_roles=ALL_ROLES,
    is_write=True,
)
async def create_complaint(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sid = _require_student(ctx)
    text = (args.get("text") or "").strip()
    if len(text) < 10:
        return {"error": "bad_argument", "message": "The complaint text is too short."}

    from app.services.complaints import ComplaintService

    complaint = await ComplaintService(ctx.session).create(student_id=sid, text=text)
    return {
        "created": True,
        "complaint_id": str(complaint.id),
        "status": complaint.status.value,
        "message": "Complaint filed. Staff will review it.",
    }


@registry.register(
    name="create_leave_request",
    description=(
        "Submit a leave request for the signed-in student. Only call this after the "
        "student has confirmed the dates and reason."
    ),
    parameters={
        "type": "object",
        "properties": {
            "leave_type": {"type": "string", "enum": [t.value for t in LeaveType]},
            "from_date": {"type": "string", "description": "Start date, YYYY-MM-DD."},
            "to_date": {"type": "string", "description": "End date, YYYY-MM-DD."},
            "reason": {"type": "string"},
        },
        "required": ["leave_type", "from_date", "to_date", "reason"],
    },
    allowed_roles=ALL_ROLES,
    is_write=True,
)
async def create_leave_request(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sid = _require_student(ctx)
    try:
        leave_type = LeaveType(args["leave_type"])
        from_date = date.fromisoformat(args["from_date"])
        to_date = date.fromisoformat(args["to_date"])
    except (KeyError, ValueError) as exc:
        return {"error": "bad_argument", "message": f"Invalid arguments: {exc}"}

    if to_date < from_date:
        return {"error": "bad_argument", "message": "End date cannot precede start date."}

    reason = (args.get("reason") or "").strip()
    if len(reason) < 5:
        return {"error": "bad_argument", "message": "A reason is required."}

    leave = LeaveRequest(
        student_id=sid,
        leave_type=leave_type,
        from_date=from_date,
        to_date=to_date,
        reason=reason,
        status=LeaveStatus.PENDING,
    )
    ctx.session.add(leave)
    await ctx.session.flush()
    return {
        "created": True,
        "leave_request_id": str(leave.id),
        "status": leave.status.value,
        "message": "Leave request submitted for warden approval.",
    }
