from __future__ import annotations

from app.ai.services.chunking import MAX_HEADING_CHARS, chunk_text


def test_empty_text_yields_no_chunks() -> None:
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_headings_split_sections_without_duplication() -> None:
    doc = "# Rules\n\n## Rule 1\n\nBe on time.\n\n## Rule 2\n\nBe quiet."
    chunks = chunk_text(doc)
    assert [c.section_path for c in chunks] == ["Rules", "Rule 1", "Rule 2"]
    # Content of one section must not leak into the next.
    assert "Be on time" not in chunks[2].text


def test_long_rule_paragraph_is_not_treated_as_heading() -> None:
    """A paragraph starting 'Rule 5.' is body text, not a section break."""
    long_rule = "Rule 5. " + "x" * 400
    assert len(long_rule) > MAX_HEADING_CHARS
    chunks = chunk_text("Section A\n\n" + long_rule)
    assert len(chunks) == 1


def test_oversized_document_splits_with_overlap() -> None:
    big = "\n\n".join(f"Paragraph {i} " + "y" * 300 for i in range(20))
    chunks = chunk_text(big, max_tokens=200)
    assert len(chunks) > 1
    # Consecutive chunks share a tail so a rule spanning the boundary is retrievable.
    assert chunks[1].text[:30] in chunks[0].text


def test_chunk_hashes_are_stable_and_distinct() -> None:
    a = chunk_text("# H\n\nSame body text here.")
    b = chunk_text("# H\n\nSame body text here.")
    assert [c.content_hash for c in a] == [c.content_hash for c in b]
    c = chunk_text("# H\n\nDifferent body.")
    assert a[0].content_hash != c[0].content_hash


def test_devanagari_headings_recognised() -> None:
    doc = "दफा ३\n\nखाना बिहान ७ बजे उपलब्ध हुनेछ।"
    chunks = chunk_text(doc)
    assert chunks[0].section_path == "दफा ३"
