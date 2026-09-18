"""Structure-aware chunking.

Splits on heading and clause boundaries rather than a fixed character window, so
a numbered hostel rule is not cut in half -- which would make it unciteable and
degrade retrieval for exactly the queries students ask most.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

# Characters per token, by script. Latin text averages ~4 chars/token; Devanagari
# tokenizes far less efficiently (~1.5-2 chars/token), so a chunk sized with the
# Latin ratio can be 2-3x its assumed token count in Nepali. Underestimating here
# pushes chunks past the embedding model's input limit, so the Devanagari ratio is
# deliberately conservative.
CHARS_PER_TOKEN = 4
DEVANAGARI_CHARS_PER_TOKEN = 1.5
DEFAULT_CHUNK_TOKENS = 600
DEFAULT_OVERLAP_RATIO = 0.15

# Headings are short by nature. Without this bound, a regex like "RULE \\d+" also
# matches a full rule paragraph that merely starts with "Rule 5.", fragmenting the
# document into one-sentence chunks that carry too little context to retrieve well.
MAX_HEADING_CHARS = 120

_HEADING = re.compile(
    r"^\s*(?:"
    r"#{1,6}\s+.+"  # markdown heading
    r"|(?:CHAPTER|SECTION|ARTICLE|RULE|अनुसूची|दफा|नियम)\s+[\dIVXक-ह]+.*"
    r"|\d+(?:\.\d+)*\s+[A-Zऀ-ॿ].{0,100}"
    r")\s*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(slots=True)
class Chunk:
    index: int
    text: str
    page_number: int | None
    section_path: str | None
    token_count: int
    content_hash: str


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _devanagari_ratio(text: str) -> float:
    if not text:
        return 0.0
    devanagari = sum(1 for ch in text if "\u0900" <= ch <= "\u097f")
    return devanagari / len(text)


def _approx_tokens(text: str) -> int:
    """Estimate tokens, weighting by how much of the text is Devanagari."""
    ratio = _devanagari_ratio(text)
    chars_per_token = ratio * DEVANAGARI_CHARS_PER_TOKEN + (1 - ratio) * CHARS_PER_TOKEN
    return max(1, int(len(text) / chars_per_token))


def _is_heading(para: str) -> bool:
    return len(para) <= MAX_HEADING_CHARS and bool(_HEADING.match(para))


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_text(
    text: str,
    *,
    page_number: int | None = None,
    start_index: int = 0,
    max_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap_ratio: float = DEFAULT_OVERLAP_RATIO,
) -> list[Chunk]:
    """Chunk one page/section of text, tracking the current heading as section_path."""
    if not text.strip():
        return []

    # Size the character window using the script actually present, so a Nepali
    # page yields chunks that really are ~max_tokens rather than 2-3x that.
    ratio = _devanagari_ratio(text)
    chars_per_token = ratio * DEVANAGARI_CHARS_PER_TOKEN + (1 - ratio) * CHARS_PER_TOKEN
    max_chars = int(max_tokens * chars_per_token)
    overlap_chars = int(max_chars * overlap_ratio)

    chunks: list[Chunk] = []
    current: list[str] = []
    current_len = 0
    section: str | None = None
    idx = start_index

    def flush(*, carry_overlap: bool) -> None:
        """Emit the accumulated text as a chunk.

        `carry_overlap` is True only when we split because the chunk grew too
        large -- there the overlap keeps a rule that straddles the boundary
        retrievable. On a heading boundary the split is semantic, so carrying
        text forward would duplicate content across chunks instead.
        """
        nonlocal current, current_len, idx
        if not current:
            return
        body = "\n\n".join(current).strip()
        current, current_len = [], 0
        if not body:
            return
        chunks.append(
            Chunk(
                index=idx,
                text=body,
                page_number=page_number,
                section_path=section,
                token_count=_approx_tokens(body),
                content_hash=_hash(body),
            )
        )
        idx += 1
        if carry_overlap and overlap_chars:
            # Never carry more than half the chunk, so a small chunk cannot be
            # duplicated wholesale into its successor.
            tail_len = min(overlap_chars, len(body) // 2)
            if tail_len > 0:
                tail = body[-tail_len:]
                current = [tail]
                current_len = len(tail)

    for para in _split_paragraphs(text):
        if _is_heading(para):
            flush(carry_overlap=False)
            section = para.strip().lstrip("#").strip()

        if current_len + len(para) > max_chars and current:
            flush(carry_overlap=True)

        # A single oversized paragraph is split on sentence boundaries.
        if len(para) > max_chars:
            for sentence in re.split(r"(?<=[.!?\u0964])\s+", para):
                if current_len + len(sentence) > max_chars and current:
                    flush(carry_overlap=True)
                current.append(sentence)
                current_len += len(sentence)
            continue

        current.append(para)
        current_len += len(para)

    flush(carry_overlap=False)
    return chunks
