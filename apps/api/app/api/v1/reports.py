"""Report exports (Excel or PDF).

Every export is audit-logged: these files carry residents' personal data out
of the system, so who took which report, when, is always recorded. Bulk
personal data (the resident register, fees) is limited to the warden.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import CurrentUser, SessionDep, require_roles
from app.core.clock import hostel_today
from app.core.errors import ValidationFailedError
from app.models.enums import StudentStatus, UserRole
from app.reports.model import Report
from app.reports.pdf import render_pdf
from app.reports.xlsx import render_xlsx
from app.services.audit import record_audit
from app.services.reports import ReportService

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(require_roles(UserRole.STAFF, UserRole.WARDEN, UserRole.SUPER_ADMIN))],
)
WardenOnly = Depends(require_roles(UserRole.WARDEN, UserRole.SUPER_ADMIN))

Format = Literal["xlsx", "pdf"]
MEDIA_TYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}
MAX_RANGE_DAYS = 366


def _date_range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    """Default: the last 30 days, in hostel time."""
    date_to = date_to or hostel_today()
    date_from = date_from or date_to - timedelta(days=29)
    if date_from > date_to:
        raise ValidationFailedError("date_from cannot be after date_to.")
    if (date_to - date_from).days >= MAX_RANGE_DAYS:
        raise ValidationFailedError("A report can cover at most one year.")
    return date_from, date_to


async def _export(
    session: SessionDep,
    user: CurrentUser,
    *,
    name: str,
    report: Report,
    fmt: Format,
    filters: dict[str, Any],
) -> Response:
    render = render_xlsx if fmt == "xlsx" else render_pdf
    # Rendering is CPU-bound; keep it off the event loop.
    content = await asyncio.to_thread(render, report)
    record_audit(
        session,
        actor_id=user.id,
        action="report.export",
        entity_type="report",
        entity_id=name,
        after={"format": fmt, "filters": filters, "rows": report.row_count},
    )
    filename = f"{name}-{report.generated_at:%Y-%m-%d}.{fmt}"
    return Response(
        content=content,
        media_type=MEDIA_TYPES[fmt],
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            # Personal data: never cached by the browser or a proxy.
            "Cache-Control": "no-store",
        },
    )


@router.get("/students", dependencies=[WardenOnly], response_class=Response)
async def students_report(
    user: CurrentUser,
    session: SessionDep,
    format: Format = Query(default="xlsx"),  # noqa: A002 - the public query parameter name
    status_filter: StudentStatus | None = Query(default=None, alias="status"),
) -> Response:
    """Resident register: contact, college, room and guardian details."""
    report = await ReportService(session).students(status=status_filter)
    return await _export(
        session,
        user,
        name="residents",
        report=report,
        fmt=format,
        filters={"status": status_filter},
    )


@router.get("/occupancy", response_class=Response)
async def occupancy_report(
    user: CurrentUser,
    session: SessionDep,
    format: Format = Query(default="xlsx"),  # noqa: A002
) -> Response:
    """Every room with beds, occupancy, rate and current residents."""
    report = await ReportService(session).occupancy()
    return await _export(session, user, name="occupancy", report=report, fmt=format, filters={})


@router.get("/fees", dependencies=[WardenOnly], response_class=Response)
async def fees_report(
    user: CurrentUser,
    session: SessionDep,
    format: Format = Query(default="xlsx"),  # noqa: A002
    period: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
) -> Response:
    """Balances per resident, plus the invoices of one billing month (or all
    unpaid invoices when no month is given)."""
    report = await ReportService(session).fees(billing_period=period)
    return await _export(
        session, user, name="fees", report=report, fmt=format, filters={"period": period}
    )


@router.get("/complaints", response_class=Response)
async def complaints_report(
    user: CurrentUser,
    session: SessionDep,
    format: Format = Query(default="xlsx"),  # noqa: A002
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> Response:
    """Complaints filed in a date range (default: last 30 days), by category
    and in detail. Resident identities are not included."""
    start, end = _date_range(date_from, date_to)
    report = await ReportService(session).complaints(date_from=start, date_to=end)
    return await _export(
        session,
        user,
        name="complaints",
        report=report,
        fmt=format,
        filters={"date_from": start, "date_to": end},
    )


@router.get("/leave", response_class=Response)
async def leave_report(
    user: CurrentUser,
    session: SessionDep,
    format: Format = Query(default="xlsx"),  # noqa: A002
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> Response:
    """Leave overlapping a date range (default: last 30 days)."""
    start, end = _date_range(date_from, date_to)
    report = await ReportService(session).leave(date_from=start, date_to=end)
    return await _export(
        session,
        user,
        name="leave",
        report=report,
        fmt=format,
        filters={"date_from": start, "date_to": end},
    )
