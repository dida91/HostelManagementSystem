"""The security properties that make LLM tool-calling safe here."""

from __future__ import annotations

import uuid

import pytest

import app.ai.tools.hostel_tools  # noqa: F401  -- registers tools
from app.ai.tools.registry import Principal, ToolContext, registry
from app.core.errors import PermissionDeniedError
from app.models.enums import UserRole


def _student() -> Principal:
    return Principal(user_id=uuid.uuid4(), role=UserRole.STUDENT, student_id=uuid.uuid4())


def _warden() -> Principal:
    return Principal(user_id=uuid.uuid4(), role=UserRole.WARDEN)


def test_no_self_scoped_tool_accepts_an_identity_argument() -> None:
    """The model must not be able to name whose data it wants.

    If any self-scoped tool grew a student_id/user_id parameter, a prompt
    injection could request another resident's fees or room.
    """
    for spec in registry.specs_for(_student()):
        props = set((spec.parameters or {}).get("properties", {}))
        offending = {p for p in props if "student" in p.lower() or "user" in p.lower()}
        offending |= {p for p in props if p.endswith("_id")}
        assert not offending, f"{spec.name} exposes identity parameter(s): {offending}"


def test_staff_only_tools_are_not_declared_to_students() -> None:
    student_tools = {s.name for s in registry.specs_for(_student())}
    warden_tools = {s.name for s in registry.specs_for(_warden())}
    assert "get_occupancy_summary" in warden_tools
    assert "get_occupancy_summary" not in student_tools


@pytest.mark.asyncio
async def test_execute_rejects_tool_outside_caller_role() -> None:
    """Defence in depth: even if a model hallucinates a tool it was never
    given, execution is refused."""
    ctx = ToolContext(session=None, principal=_student())  # type: ignore[arg-type]
    with pytest.raises(PermissionDeniedError):
        await registry.execute(name="get_occupancy_summary", arguments={}, ctx=ctx)


@pytest.mark.asyncio
async def test_unknown_tool_is_reported_not_raised() -> None:
    ctx = ToolContext(session=None, principal=_student())  # type: ignore[arg-type]
    result = await registry.execute(name="drop_all_tables", arguments={}, ctx=ctx)
    assert result["error"] == "unknown_tool"
