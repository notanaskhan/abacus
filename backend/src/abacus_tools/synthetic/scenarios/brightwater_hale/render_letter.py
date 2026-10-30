"""The renderer's golden letter (P-11-T02; ADR-320; SPEC-520 AC-30): a synthetic three-page
engagement letter from Brightwater Hale LLP to Copperleaf Coffee Roasters, Inc., as fixed blocks
and a fixed `as_of`, so the byte-stability harness renders the same inputs in every container.

Synthetic wording only: firm templates are database content (ADR-320 §2); this module is the
scenario's test fixture, not a template, and nothing in the product imports it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape

AS_OF = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)  # E0, Mon Sep 14, 2026, 9:24 AM CT
CONTENT_HASH = "sha256:golden-letter-v1"
TITLE = "Engagement letter · Copperleaf Coffee Roasters, Inc."

_SCOPE = (
    "We will compile the monthly financial statements of Copperleaf Coffee Roasters, Inc. from "
    "the information management provides, close the books each month and prepare the year-end "
    "adjusting entries. A compilation provides no assurance on the financial statements."
)
_RESPONSIBILITIES = (
    "Management is responsible for the financial statements, for the selection of accounting "
    "policies, for internal control and for providing complete and accurate records on time."
)
_FEES = (
    "Our fee is a fixed monthly amount of 2,400.00, billed on the first business day of each "
    "month. Work outside this scope is agreed in writing before it starts."
)
_TERM = (
    "This agreement runs from the date you sign it until either party ends it by thirty days' "
    "written notice. Records we keep are retained under our firm's retention policy."
)

# Three pages: each section is long enough, and page breaks fix where pages end.
SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("1. Scope of services", (_SCOPE,) * 6),
    ("2. Responsibilities", (_RESPONSIBILITIES,) * 6),
    ("3. Fees and term", (_FEES, _TERM) * 3),
)


# (kind, text, level): the renderer's harness maps these onto its DOCX blocks (abacus_tools never
# imports a module's internals, ADR-101).
Block = tuple[str, str, int]


def blocks() -> tuple[Block, ...]:
    out: list[Block] = [("heading", TITLE, 1)]
    for i, (heading, paragraphs) in enumerate(SECTIONS):
        if i > 0:
            out.append(("page_break", "", 1))
        out.append(("heading", heading, 2))
        out.extend(("paragraph", p, 1) for p in paragraphs)
    return tuple(out)


CSS = """
@page { size: Letter; margin: 1in; }
body { font-family: "Arimo"; font-size: 11pt; line-height: 1.45; color: #2b1f17; }
h1 { font-family: "Gelasio"; font-weight: 500; font-size: 16pt; margin: 0 0 12pt; }
h2 { font-family: "Gelasio"; font-weight: 700; font-size: 12.5pt; margin: 14pt 0 6pt; }
p { margin: 0 0 8pt; }
.page-break { break-before: page; }
.figure { font-family: "Geist Mono"; }
"""


def html(head: str) -> str:
    """The letter as HTML from a code-owned layout: every text node escaped (ADR-052)."""
    parts = [f"<!DOCTYPE html><html lang='en'><head>{head}</head><body>"]
    parts.append(f"<h1>{escape(TITLE)}</h1>")
    for i, (heading, paragraphs) in enumerate(SECTIONS):
        cls = " class='page-break'" if i > 0 else ""
        parts.append(f"<h2{cls}>{escape(heading)}</h2>")
        parts.extend(f"<p>{escape(p)}</p>" for p in paragraphs)
    parts.append("</body></html>")
    return "".join(parts)
