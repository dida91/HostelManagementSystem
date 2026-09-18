"""Provider-agnostic AI abstractions.

Nothing outside `app/ai/providers/gemini.py` may import the Gemini SDK. The rest
of the application -- services, routers, workers -- depends only on the
protocols defined here, so swapping or adding a provider touches one file.
That rule is enforced mechanically by the banned-import lint rule in
pyproject.toml, not by convention.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

TSchema = TypeVar("TSchema", bound=BaseModel)

EmbeddingTaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY", "SEMANTIC_SIMILARITY"]


@dataclass(slots=True)
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None

    @property
    def total(self) -> int | None:
        if self.input_tokens is None and self.output_tokens is None:
            return None
        return (self.input_tokens or 0) + (self.output_tokens or 0)


@dataclass(slots=True)
class TextResult:
    text: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    retry_count: int = 0


@dataclass(slots=True)
class StructuredResult[T: BaseModel]:
    """A schema-validated model response. `data` has already passed Pydantic
    validation -- callers never parse free text."""

    data: T
    model: str
    raw: dict[str, Any] | None = None
    usage: TokenUsage = field(default_factory=TokenUsage)
    retry_count: int = 0


@dataclass(slots=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class ToolTurnResult:
    """One assistant turn: either a final answer, or tool calls to execute."""

    text: str | None
    tool_calls: list[ToolCall]
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    # The provider's own representation of this turn, kept opaque here. It must
    # be appended to history verbatim: reconstructing a function call from its
    # name and arguments drops provider-internal reasoning signatures, which
    # newer models reject.
    raw_content: Any = None

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


@dataclass(slots=True)
class Embedding:
    values: list[float]
    model: str
    dim: int


@dataclass(slots=True)
class ToolSpec:
    """Provider-neutral description of a callable backend tool."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@runtime_checkable
class LLMProvider(Protocol):
    """Text generation, structured output and tool-calling."""

    async def generate_text(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
    ) -> TextResult: ...

    async def generate_structured[T: BaseModel](
        self,
        *,
        prompt: str,
        schema: type[T],
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> StructuredResult[T]: ...

    async def generate_with_tools(
        self,
        *,
        history: list[dict[str, Any]],
        tools: list[ToolSpec],
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> ToolTurnResult: ...

    async def count_tokens(self, *, text: str, model: str | None = None) -> int: ...


@runtime_checkable
class DocumentUnderstandingProvider(Protocol):
    """Multimodal extraction for documents native text extraction cannot read
    (scans, images, complex layout). Separate from LLMProvider so a provider can
    implement text generation without implementing document understanding."""

    async def extract_document_text(
        self, *, content: bytes, mime_type: str, hint: str | None = None
    ) -> TextResult: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Embedding generation. Kept separate so the embedding model can change
    independently of the text model."""

    @property
    def model_name(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    async def embed_documents(self, texts: list[str]) -> list[Embedding]: ...

    async def embed_query(self, text: str) -> Embedding: ...
