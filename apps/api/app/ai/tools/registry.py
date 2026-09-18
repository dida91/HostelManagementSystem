"""Backend tool registry for Gemini function calling.

THE core security property of this module:

  Self-scoped tools declare NO identity parameter. The model physically cannot
  pass a student_id, so it cannot ask for another student's data. The executor
  injects the authenticated principal from the request context.

Combined with per-tool role requirements checked before execution, a prompt
injection in a document -- or a jailbroken conversation -- cannot escalate
privilege or cross tenancy, because authorization never consults the model.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.base import ToolSpec
from app.core.errors import PermissionDeniedError
from app.core.logging import get_logger
from app.models.enums import UserRole

log = get_logger("ai.tools")


@dataclass(slots=True)
class Principal:
    """The authenticated caller. Never derived from model output."""

    user_id: uuid.UUID
    role: UserRole
    student_id: uuid.UUID | None = None


@dataclass(slots=True)
class ToolContext:
    session: AsyncSession
    principal: Principal


ToolHandler = Callable[[ToolContext, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(slots=True)
class RegisteredTool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    allowed_roles: frozenset[UserRole]
    # Write tools are never auto-executed; the UI must confirm with the user first.
    is_write: bool = False

    def to_spec(self) -> ToolSpec:
        return ToolSpec(name=self.name, description=self.description, parameters=self.parameters)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        *,
        name: str,
        description: str,
        parameters: dict[str, Any] | None = None,
        allowed_roles: set[UserRole],
        is_write: bool = False,
    ) -> Callable[[ToolHandler], ToolHandler]:
        def decorator(handler: ToolHandler) -> ToolHandler:
            self._tools[name] = RegisteredTool(
                name=name,
                description=description,
                parameters=parameters or {"type": "object", "properties": {}},
                handler=handler,
                allowed_roles=frozenset(allowed_roles),
                is_write=is_write,
            )
            return handler

        return decorator

    def specs_for(self, principal: Principal, *, include_writes: bool = True) -> list[ToolSpec]:
        """Tools this caller may use.

        Filtering happens BEFORE the model runs: a tool the caller cannot use is
        never even declared to it, so the model cannot be talked into calling it.
        """
        return [
            t.to_spec()
            for t in self._tools.values()
            if principal.role in t.allowed_roles and (include_writes or not t.is_write)
        ]

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def all_names(self) -> list[str]:
        return sorted(self._tools)

    async def execute(
        self, *, name: str, arguments: dict[str, Any], ctx: ToolContext
    ) -> dict[str, Any]:
        """Execute a tool after authorization. Re-checked here even though
        specs_for already filtered: defence in depth against a model that
        hallucinates a tool name it was never given."""
        tool = self._tools.get(name)
        if tool is None:
            log.warning("tool_unknown", tool=name, role=ctx.principal.role.value)
            return {"error": "unknown_tool", "message": f"No such tool: {name}"}

        if ctx.principal.role not in tool.allowed_roles:
            log.warning(
                "tool_denied",
                tool=name,
                role=ctx.principal.role.value,
                user_id=str(ctx.principal.user_id),
            )
            raise PermissionDeniedError(f"Role {ctx.principal.role.value} may not call {name}.")

        if tool.is_write:
            log.info("tool_write_executed", tool=name, user_id=str(ctx.principal.user_id))

        try:
            result = await tool.handler(ctx, arguments)
        except PermissionDeniedError:
            raise
        except Exception as exc:  # noqa: BLE001 - surfaced to the model as a failure, not a crash
            log.error("tool_failed", tool=name, error=str(exc), exc_info=True)
            # The model is told the tool failed so it says so rather than
            # inventing a value. Internal detail is not included.
            return {"error": "tool_failed", "message": "This information could not be retrieved."}

        log.info("tool_executed", tool=name, user_id=str(ctx.principal.user_id))
        return result


registry = ToolRegistry()
