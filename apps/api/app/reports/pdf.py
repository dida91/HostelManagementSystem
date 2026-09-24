"""PDF rendering (A4 landscape), one section per table.

Residents write in Nepali as often as English. Devanagari is drawn with a
Devanagari font and shaped by HarfBuzz (reportlab + uharfbuzz), so conjuncts
and vowel signs come out right; Latin text stays in Helvetica. Mixed text is
split into script runs because the Devanagari font carries no Latin letters.
If the font file is missing, the PDF says so rather than printing boxes
silently -- the Excel export always carries the exact text.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import get_settings
from app.core.logging import get_logger
from app.reports.model import Column, Report
from app.reports.model import Table as ReportTable

log = get_logger("reports.pdf")

DEVANAGARI_FONT = "HostelDevanagari"
# Devanagari + Vedic extensions, plus the joiners that live inside words.
_DEVANAGARI_RUN = re.compile(r"[ऀ-ॿ꣠-ꣿ᳐-᳿‌‍]+")
_MAX_CELL_CHARS = 400
_PAGE = landscape(A4)
_MARGIN = 12 * mm


@lru_cache(maxsize=1)
def _devanagari_available() -> bool:
    path = Path(get_settings().report_devanagari_font)
    if not path.is_file():
        log.warning("devanagari_font_missing", path=str(path))
        return False
    try:
        pdfmetrics.registerFont(TTFont(DEVANAGARI_FONT, str(path)))
    except Exception as exc:  # noqa: BLE001 - a bad font must not break reports
        log.warning("devanagari_font_unusable", path=str(path), error=str(exc))
        return False
    return True


def _markup(text: str) -> str:
    """Escape for Paragraph markup and switch fonts for Devanagari runs."""
    if not _devanagari_available() or not _DEVANAGARI_RUN.search(text):
        return escape(text)
    out, last = [], 0
    for match in _DEVANAGARI_RUN.finditer(text):
        out.append(escape(text[last : match.start()]))
        out.append(f'<font name="{DEVANAGARI_FONT}">{escape(match.group())}</font>')
        last = match.end()
    out.append(escape(text[last:]))
    return "".join(out)


def _display(value: Any, column: Column) -> str:
    if value is None or value == "":
        return ""
    if column.kind == "money":
        return f"{Decimal(value):,.2f}"
    if column.kind == "percent":
        return f"{float(value):.1f}%"
    if column.kind == "datetime" and isinstance(value, datetime):
        return f"{value:%Y-%m-%d %H:%M}"
    if column.kind == "date" and isinstance(value, date | datetime):
        return f"{value:%Y-%m-%d}"
    text = " ".join(str(value).split())
    return text if len(text) <= _MAX_CELL_CHARS else text[: _MAX_CELL_CHARS - 1] + "…"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    cell = ParagraphStyle("cell", parent=base["BodyText"], fontSize=7.5, leading=9.5)
    return {
        "title": ParagraphStyle("title", parent=base["Title"], alignment=0, fontSize=16),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], textColor=colors.grey),
        "heading": ParagraphStyle("heading", parent=base["Heading2"], fontSize=11.5),
        "cell": cell,
        "num": ParagraphStyle("num", parent=cell, alignment=TA_RIGHT),
        "head": ParagraphStyle(
            "head", parent=cell, fontName="Helvetica-Bold", textColor=colors.white
        ),
        "note": ParagraphStyle("note", parent=base["Italic"], fontSize=8, textColor=colors.grey),
    }


def _table_flowable(table: ReportTable, styles: dict[str, ParagraphStyle]) -> Table:
    numeric = [c.kind in {"money", "int", "percent"} for c in table.columns]
    data: list[list[Any]] = [[Paragraph(escape(c.header), styles["head"]) for c in table.columns]]
    body_rows = table.rows + ([table.totals] if table.totals is not None else [])
    for row in body_rows:
        data.append(
            [
                Paragraph(
                    _markup(_display(value, column)),
                    styles["num"] if is_num else styles["cell"],
                )
                for value, column, is_num in zip(row, table.columns, numeric, strict=True)
            ]
        )

    available = _PAGE[0] - 2 * _MARGIN
    total_units = sum(c.width for c in table.columns)
    widths = [available * c.width / total_units for c in table.columns]

    commands: list[tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F5130")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D0D5DD")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i in range(1, len(table.rows) + 1):
        if i % 2 == 0:
            commands.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F4F6F5")))
    if table.totals is not None:
        commands += [
            ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ]
    flowable = Table(data, colWidths=widths, repeatRows=1)
    flowable.setStyle(TableStyle(commands))
    return flowable


def render_pdf(report: Report) -> bytes:
    buffer = BytesIO()
    styles = _styles()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=_PAGE,
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=_MARGIN,
        bottomMargin=_MARGIN + 4 * mm,
        title=report.title,
        author="Kutumba 1 Girls Hostel",
    )

    story: list[Any] = [
        Paragraph(escape(report.title), styles["title"]),
        Paragraph(
            escape(f"{report.subtitle}  |  Generated {report.generated_at:%d %b %Y %H:%M %Z}"),
            styles["subtitle"],
        ),
        Spacer(1, 5 * mm),
    ]
    for table in report.tables:
        story.append(Paragraph(escape(table.title), styles["heading"]))
        if table.rows:
            story.append(_table_flowable(table, styles))
        else:
            story.append(Paragraph("No records.", styles["note"]))
        story.append(Spacer(1, 6 * mm))

    notes = list(report.notes)
    if not _devanagari_available():
        notes.append(
            "Nepali (Devanagari) text cannot be shown in this PDF because the configured "
            "font is missing on the server. The Excel export contains the exact text."
        )
    story += [Paragraph(escape(note), styles["note"]) for note in notes]

    def _footer(canvas: Canvas, document: SimpleDocTemplate) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.grey)
        canvas.drawString(_MARGIN, 7 * mm, f"Kutumba 1 Girls Hostel | {report.title}")
        canvas.drawRightString(_PAGE[0] - _MARGIN, 7 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
