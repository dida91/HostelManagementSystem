"""AI Hostel Assistant: bounded tool-calling loop.

Flow per user turn:
    model -> (tool calls) -> backend validates + executes -> results -> model
    ... repeated until the model answers or the iteration cap is hit.

The loop is strictly bounded by GEMINI_MAX_TOOL_ITERATIONS. Authorization is
applied by the registry on every call, so no model output can widen access.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts import assistant as prompts
from app.ai.providers.base import LLMProvider
from app.ai.services.rag import RagService
from app.ai.telemetry.tracing import ai_span
from app.ai.tools.registry import Principal, ToolContext, registry
from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("ai.chat")

OPERATION = "assistant.chat"


@dataclass
class AssistantTurn:
    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    iterations: int = 0
    ai_operation_id: uuid.UUID | None = None


class AssistantService:
    def __init__(self, *, provider: LLMProvider, rag: RagService | None = None) -> None:
        self._provider = provider
        self._rag = rag
        self._settings = get_settings().ai

    async def respond(
        self,
        *,
        session: AsyncSession,
        principal: Principal,
        message: str,
        history: list[dict[str, Any]] | None = None,
        allow_writes: bool = False,
    ) -> AssistantTurn:
        """Produce one assistant turn.

        `allow_writes=False` by default: write tools are proposed to the user for
        confirmation in the UI rather than executed inside the model loop.
        """
        model = self._settings.gemini_text_model
        specs = registry.specs_for(principal, include_writes=allow_writes)
        ctx = ToolContext(session=session, principal=principal)

        conversation: list[dict[str, Any]] = list(history or [])
        conversation.append({"role": "user", "content": message})

        executed: list[dict[str, Any]] = []
        citations: list[dict[str, Any]] = []
        max_iters = self._settings.gemini_max_tool_iterations
        final_text = ""
        iterations = 0

        async with ai_span(
            operation=OPERATION,
            model=model,
            session=session,
            user_id=principal.user_id,
            prompt_version=prompts.ASSISTANT_VERSION,
        ) as span:
            for iteration in range(max_iters):
                iterations = iteration + 1
                turn = await self._provider.generate_with_tools(
                    history=conversation,
                    tools=specs,
                    system=prompts.ASSISTANT_SYSTEM,
                    model=model,
                    temperature=0.2,
                )
                span.record_usage(turn.usage.input_tokens, turn.usage.output_tokens)

                if not turn.wants_tools:
                    final_text = turn.text or ""
                    break

                for call in turn.tool_calls:
                    span.tool_calls += 1
                    result = await registry.execute(
                        name=call.name, arguments=call.arguments, ctx=ctx
                    )
                    executed.append(
                        {
                            "name": call.name,
                            "arguments": call.arguments,
                            "ok": "error" not in result,
                        }
                    )
                    conversation.append(
                        {
                            "role": "assistant_tool_call",
                            "name": call.name,
                            "arguments": call.arguments,
                        }
                    )
                    conversation.append({"role": "tool", "name": call.name, "response": result})
            else:
                # Cap reached without a final answer. We do NOT keep looping.
                log.warning(
                    "assistant_iteration_cap",
                    user_id=str(principal.user_id),
                    max_iterations=max_iters,
                )
                final_text = (
                    "I wasn't able to complete that request. "
                    "Please try rephrasing, or contact the warden's office."
                )

            span.retry_count = 0

        return AssistantTurn(
            text=final_text,
            tool_calls=executed,
            citations=citations,
            iterations=iterations,
            ai_operation_id=span.operation_id,
        )
