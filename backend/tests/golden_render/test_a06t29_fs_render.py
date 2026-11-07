"""A-06-T29 (TASK-6020; DEC-2615): the financial statements through WeasyPrint.

Image-bound like `test_p11t07_render_core.py`: `make golden-render` runs this file inside the
backend image (no network). The row's acceptance: two renders of Northwind v3 are byte-identical
and the client copy carries DRAFT, on every page; a preparation engagement's pages each carry
"No assurance is provided." (AR-C 70, R-19).
"""

from __future__ import annotations

import io
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Final

import pdfplumber

from abacus.modules.reporting.fs_render import NO_ASSURANCE, Heading, Line, Note, compose_body
from abacus.modules.reporting.render.core import RenderInput, render

AS_OF: Final = datetime(2026, 10, 2, 14, 10, tzinfo=UTC)
MARK_SIZE: Final = 36.0  # the watermark is ~64 pt, everything else far smaller
NORTHWIND: Final = Heading(
    "Northwind Robotics 401(k) Plan", date(2025, 12, 31), preparation=False, plan=True
)
LINES: Final = [
    Line(
        "net_assets",
        "Investments at fair value",
        0,
        {2025: Decimal("16812400.00"), 2024: Decimal("15900000.00")},
    ),
    Line("net_assets", "Contributions receivable", 1, {2025: Decimal("48600.00")}),
    Line("net_assets", "Net assets available for benefits", 2, {2025: Decimal("16861000.00")}),
    Line("changes", "Benefits paid to participants", 3, {2025: Decimal("-797800.00")}),
]
NOTES: Final = [Note(1, "Description of the Plan", "The plan is a defined contribution plan.")]


def _input(heading: Heading = NORTHWIND) -> RenderInput:
    return RenderInput(
        layout_key="financial_statements",
        blocks=compose_body(heading, LINES, NOTES),
        values={},
        title="Financial statements",
        as_of=AS_OF,
        mode="draft",
        content_hash="f" * 64,
    )


def _pages(pdf: bytes) -> list[tuple[str, str]]:
    """Each page's text and its display-size characters (the diagonal mark)."""
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        return [
            (
                page.extract_text() or "",
                "".join(
                    str(c["text"])
                    for c in sorted(page.chars, key=lambda c: float(c["x0"]))
                    if float(c["size"]) >= MARK_SIZE
                ),
            )
            for page in document.pages
        ]


def test_ac_two_renders_of_northwind_v3_are_byte_identical() -> None:
    first, second = render(_input()), render(_input())
    assert first.pdf == second.pdf and first.render_hash == second.render_hash
    assert first.page_count >= 3  # two statements and the notes, each from a new page


def test_ac_every_page_of_the_client_draft_carries_draft() -> None:
    pages = _pages(render(_input()).pdf)
    assert pages and all(mark == "DRAFT" for _text, mark in pages)


def test_ar_c_70_every_page_says_no_assurance_is_provided() -> None:
    heading = Heading(NORTHWIND.entity_name, NORTHWIND.period_end, preparation=True, plan=True)
    pages = _pages(render(_input(heading)).pdf)
    assert pages and all(NO_ASSURANCE in text for text, _mark in pages)
    assert not any(NO_ASSURANCE in text for text, _mark in _pages(render(_input()).pdf))
