"""Google Gemini provider -- the ONLY module permitted to import the SDK.

Responsibilities kept here on purpose:
  * SDK construction and credential handling
  * error classification and bounded retry with backoff + jitter
  * structured output via response_schema + Pydantic revalidation
  * tool-call translation to/from the provider-neutral shapes in base.py

Everything above this layer works with LLMProvider / EmbeddingProvider.
"""

from __future__ import annotations

import asyncio
import json
import math
import random
from collections.abc import Awaitable, Callable
from typing import Any

from google import genai  # noqa: TID251 -- this module is the designated boundary
from google.genai import types  # noqa: TID251
from pydantic import BaseModel, ValidationError

from app.ai.providers.base import (
    Embedding,
    EmbeddingTaskType,
    StructuredResult,
    TextResult,
    TokenUsage,
    ToolCall,
    ToolSpec,
    ToolTurnResult,
)
from app.core.config import AISettings, get_settings
from app.core.errors import AIUnavailableError
from app.core.logging import get_logger
from app.models.enums import AIErrorCategory

log = get_logger("ai.gemini")


class GeminiError(Exception):
    """Internal: carries a classified category for telemetry and retry policy."""

    def __init__(self, message: str, category: AIErrorCategory, *, retryable: bool) -> None:
        super().__init__(message)
        self.category = category
        self.retryable = retryable


def classify_error(exc: Exception) -> GeminiError:
    """Map an SDK/transport exception to a category and a retry decision.

    Only transient classes are retryable. A 400 or a 403 is a bug or a
    misconfiguration -- retrying it wastes quota and delays the real error.
    """
    name = type(exc).__name__
    text = str(exc).lower()
    status = getattr(exc, "code", None) or getattr(exc, "status_code", None)

    if isinstance(exc, asyncio.TimeoutError) or "timeout" in text or "deadline" in text:
        return GeminiError(str(exc), AIErrorCategory.TIMEOUT, retryable=True)
    if status == 429 or "resource_exhausted" in text or "rate limit" in text or "quota" in text:
        return GeminiError(str(exc), AIErrorCategory.RATE_LIMITED, retryable=True)
    if status in (500, 502, 503, 504) or "unavailable" in text or "internal error" in text:
        return GeminiError(str(exc), AIErrorCategory.UNAVAILABLE, retryable=True)
    if (
        status in (401, 403)
        or "api key" in text
        or "permission" in text
        or "unauthenticated" in text
    ):
        return GeminiError(str(exc), AIErrorCategory.AUTH, retryable=False)
    if "safety" in text or "blocked" in text or "recitation" in text:
        return GeminiError(str(exc), AIErrorCategory.SAFETY_BLOCKED, retryable=False)
    if status == 400 or "invalid" in text:
        return GeminiError(str(exc), AIErrorCategory.BAD_REQUEST, retryable=False)
    return GeminiError(f"{name}: {exc}", AIErrorCategory.UNKNOWN, retryable=False)


class _GeminiBase:
    def __init__(self, settings: AISettings | None = None) -> None:
        self._settings = settings or get_settings().ai
        if not self._settings.is_configured:
            # Reached only if something bypassed startup validation.
            raise AIUnavailableError(
                "Gemini provider constructed without GEMINI_API_KEY configured."
            )
        key = self._settings.gemini_api_key
        assert key is not None
        self._client = genai.Client(
            api_key=key.get_secret_value(),
            http_options=types.HttpOptions(
                timeout=int(self._settings.gemini_timeout_seconds * 1000)
            ),
        )

    async def _with_retry[T](
        self, fn: Callable[[], Awaitable[T]], *, operation: str
    ) -> tuple[T, int]:
        """Bounded retry with exponential backoff and full jitter.

        Returns (result, retry_count). The loop is strictly bounded by
        GEMINI_MAX_RETRIES -- there is no unbounded retry path anywhere.
        """
        max_retries = self._settings.gemini_max_retries
        last: GeminiError | None = None

        for attempt in range(max_retries + 1):
            try:
                return await fn(), attempt
            except Exception as exc:  # noqa: BLE001 - classified immediately below
                err = classify_error(exc)
                last = err
                if not err.retryable or attempt >= max_retries:
                    break
                # Full jitter: base * 2^attempt, randomised to avoid thundering herd.
                delay = random.uniform(0, min(8.0, 0.5 * math.pow(2, attempt)))  # noqa: S311
                log.warning(
                    "gemini_retry",
                    operation=operation,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    category=err.category.value,
                    delay_seconds=round(delay, 2),
                )
                await asyncio.sleep(delay)

        assert last is not None
        log.error(
            "gemini_failed", operation=operation, category=last.category.value, error=str(last)
        )
        raise last


class GeminiProvider(_GeminiBase):
    """LLMProvider implementation."""

    @staticmethod
    def _usage(response: Any) -> TokenUsage:
        meta = getattr(response, "usage_metadata", None)
        if meta is None:
            return TokenUsage()
        return TokenUsage(
            input_tokens=getattr(meta, "prompt_token_count", None),
            output_tokens=getattr(meta, "candidates_token_count", None),
        )

    async def generate_text(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
    ) -> TextResult:
        target = model or self._settings.gemini_text_model
        cfg = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        async def _call() -> Any:
            return await self._client.aio.models.generate_content(
                model=target, contents=prompt, config=cfg
            )

        response, retries = await self._with_retry(_call, operation="generate_text")
        return TextResult(
            text=response.text or "", model=target, usage=self._usage(response), retry_count=retries
        )

    async def generate_structured[T: BaseModel](
        self,
        *,
        prompt: str,
        schema: type[T],
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> StructuredResult[T]:
        """Schema-constrained generation.

        The schema is enforced by the API AND revalidated with Pydantic. On a
        validation failure we make exactly one bounded repair attempt that feeds
        the validation error back to the model; if that also fails the operation
        errors rather than persisting malformed data.
        """
        target = model or self._settings.gemini_text_model
        cfg = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
        )

        async def _call(contents: str) -> Any:
            async def _inner() -> Any:
                return await self._client.aio.models.generate_content(
                    model=target, contents=contents, config=cfg
                )

            return await self._with_retry(_inner, operation="generate_structured")

        response, retries = await _call(prompt)
        raw_text = response.text or ""
        try:
            payload = json.loads(raw_text)
            return StructuredResult(
                data=schema.model_validate(payload),
                model=target,
                raw=payload,
                usage=self._usage(response),
                retry_count=retries,
            )
        except (json.JSONDecodeError, ValidationError) as first_error:
            log.warning(
                "gemini_schema_invalid_retrying",
                model=target,
                schema=schema.__name__,
                error=str(first_error)[:500],
            )
            repair_prompt = (
                f"{prompt}\n\n"
                "Your previous response did not satisfy the required JSON schema.\n"
                f"Validation error: {first_error}\n"
                "Return ONLY valid JSON matching the schema exactly."
            )
            response2, retries2 = await _call(repair_prompt)
            try:
                payload2 = json.loads(response2.text or "")
                return StructuredResult(
                    data=schema.model_validate(payload2),
                    model=target,
                    raw=payload2,
                    usage=self._usage(response2),
                    retry_count=retries + retries2 + 1,
                )
            except (json.JSONDecodeError, ValidationError) as second_error:
                log.error(
                    "gemini_schema_invalid_final",
                    model=target,
                    schema=schema.__name__,
                    error=str(second_error)[:500],
                )
                raise GeminiError(
                    f"Response failed schema validation twice: {second_error}",
                    AIErrorCategory.SCHEMA_INVALID,
                    retryable=False,
                ) from second_error

    async def generate_with_tools(
        self,
        *,
        history: list[dict[str, Any]],
        tools: list[ToolSpec],
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> ToolTurnResult:
        """One assistant turn with tool declarations.

        Automatic function calling is DISABLED: the SDK must not execute
        anything. Tool calls are returned to our executor, which applies
        authentication, authorization and ownership checks before any backend
        operation runs.
        """
        target = model or self._settings.gemini_text_model
        declarations = [
            types.FunctionDeclaration(
                name=t.name, description=t.description, parameters=t.parameters
            )
            for t in tools
        ]
        cfg = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            tools=[types.Tool(function_declarations=declarations)] if declarations else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        contents = [self._to_content(m) for m in history]

        async def _call() -> Any:
            return await self._client.aio.models.generate_content(
                model=target, contents=contents, config=cfg
            )

        response, _ = await self._with_retry(_call, operation="generate_with_tools")

        calls: list[ToolCall] = []
        for candidate in getattr(response, "candidates", None) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", None) or []:
                fc = getattr(part, "function_call", None)
                if fc is not None:
                    calls.append(ToolCall(name=fc.name, arguments=dict(fc.args or {})))

        text: str | None = None
        if not calls:
            try:
                text = response.text
            except Exception:  # pragma: no cover - SDK raises when no text part exists
                text = None

        return ToolTurnResult(
            text=text, tool_calls=calls, model=target, usage=self._usage(response)
        )

    @staticmethod
    def _to_content(message: dict[str, Any]) -> types.Content:
        """Translate our neutral message dicts into SDK Content objects."""
        role = message.get("role", "user")
        if role == "tool":
            return types.Content(
                role="user",
                parts=[
                    types.Part.from_function_response(
                        name=message["name"], response=message.get("response") or {}
                    )
                ],
            )
        if role == "assistant_tool_call":
            return types.Content(
                role="model",
                parts=[
                    types.Part.from_function_call(
                        name=message["name"], args=message.get("arguments") or {}
                    )
                ],
            )
        return types.Content(
            role="model" if role == "assistant" else "user",
            parts=[types.Part.from_text(text=message.get("content") or "")],
        )

    async def count_tokens(self, *, text: str, model: str | None = None) -> int:
        target = model or self._settings.gemini_text_model
        result = await self._client.aio.models.count_tokens(model=target, contents=text)
        return int(result.total_tokens or 0)


class GeminiEmbeddingProvider(_GeminiBase):
    """EmbeddingProvider implementation.

    Task type matters: documents are embedded as RETRIEVAL_DOCUMENT and queries
    as RETRIEVAL_QUERY. Using one type for both measurably degrades retrieval.
    """

    # Conservative batch size: the API caps request size, and smaller batches
    # keep a single transient failure from invalidating a large unit of work.
    BATCH_SIZE = 32

    # Per-model input token ceilings. Exceeding these is a hard API error, so we
    # catch it here with a clear message instead of a generic 400 mid-ingestion.
    INPUT_TOKEN_LIMITS = {
        "gemini-embedding-001": 2048,
        "gemini-embedding-2": 8192,
    }

    @property
    def input_token_limit(self) -> int:
        for prefix, limit in self.INPUT_TOKEN_LIMITS.items():
            if self.model_name.startswith(prefix):
                return limit
        return 2048  # safest assumption for an unrecognised model

    @property
    def model_name(self) -> str:
        return self._settings.gemini_embedding_model

    @property
    def dimensions(self) -> int:
        return self._settings.gemini_embedding_dim

    @staticmethod
    def _normalize(values: list[float]) -> list[float]:
        """Renormalise to unit length.

        Required when using Matryoshka truncation (output_dimensionality < 3072):
        truncated vectors are no longer unit-norm, and cosine distance in
        pgvector assumes they are.
        """
        norm = math.sqrt(sum(v * v for v in values))
        return values if norm == 0 else [v / norm for v in values]

    async def _embed(self, texts: list[str], task_type: EmbeddingTaskType) -> list[Embedding]:
        cfg = types.EmbedContentConfig(task_type=task_type, output_dimensionality=self.dimensions)
        out: list[Embedding] = []

        for start in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[start : start + self.BATCH_SIZE]

            async def _call(b: list[str] = batch) -> Any:
                return await self._client.aio.models.embed_content(
                    model=self.model_name, contents=b, config=cfg
                )

            response, _ = await self._with_retry(_call, operation="embed_content")
            for item in response.embeddings or []:
                vals = list(item.values or [])
                if len(vals) != self.dimensions:
                    raise GeminiError(
                        f"Embedding dimension mismatch: got {len(vals)}, "
                        f"expected {self.dimensions}",
                        AIErrorCategory.BAD_REQUEST,
                        retryable=False,
                    )
                out.append(
                    Embedding(
                        values=self._normalize(vals), model=self.model_name, dim=self.dimensions
                    )
                )
        return out

    def _check_input_lengths(self, texts: list[str]) -> None:
        """Reject over-long inputs before spending an API call.

        Uses the same script-aware estimate as the chunker, so Devanagari text is
        not silently assumed to be 4 chars/token.
        """
        from app.ai.services.chunking import _approx_tokens

        limit = self.input_token_limit
        for i, text in enumerate(texts):
            estimated = _approx_tokens(text)
            if estimated > limit:
                raise GeminiError(
                    f"Input {i} is approximately {estimated} tokens, over the "
                    f"{limit}-token limit for {self.model_name}. Reduce the chunk size.",
                    AIErrorCategory.BAD_REQUEST,
                    retryable=False,
                )

    async def embed_documents(self, texts: list[str]) -> list[Embedding]:
        if not texts:
            return []
        return await self._embed(texts, "RETRIEVAL_DOCUMENT")

    async def embed_query(self, text: str) -> Embedding:
        result = await self._embed([text], "RETRIEVAL_QUERY")
        return result[0]
