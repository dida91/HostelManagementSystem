"""Format-neutral report structure."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

ColumnKind = Literal["text", "int", "money", "date", "datetime", "percent"]


@dataclass(frozen=True, slots=True)
class Column:
    header: str
    kind: ColumnKind = "text"
    # Relative width in characters; both renderers scale from it.
    width: int = 14


@dataclass(slots=True)
class Table:
    title: str
    columns: list[Column]
    rows: list[list[Any]]
    # Optional footer row (same length as columns; None for blank cells).
    totals: list[Any] | None = None


@dataclass(slots=True)
class Report:
    title: str
    subtitle: str
    # Timezone-aware, in the hostel's timezone.
    generated_at: datetime
    tables: list[Table]
    notes: list[str] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return sum(len(t.rows) for t in self.tables)
