"""Verifying the upload reviewer's quotes by code (SPEC-030 AC-3; ADR-066; TASK-058 D2).
PROTECTED.

A quote counts only if it is really in the document where the model says: in the extracted text
of that PDF page, or the text of that spreadsheet cell, after Unicode (NFKC), case-insensitive and
whitespace normalisation; a quote joining several lines of one page counts when every line is
there. The extraction (SPEC-029) is the source of truth; the model's word never is.

P-03-T06: an adapter. The comparisons are evidence's citation rules (`evidence.api`), the same
ones its v2 verifiers apply, so this module keeps only the reviewer's shapes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from abacus.modules.agents.handoff import DocumentCitation, VerifiedDocumentCitation
from abacus.modules.evidence.api import (
    citation_cell_reason,
    citation_cell_text,
    column_letters,
    normalised_text,
    page_quote_reason,
)

__all__ = ["column_letters", "normalised", "sheet_lines", "verify"]


def normalised(text: str) -> str:
    return normalised_text(text)


def sheet_lines(rows: Sequence[Sequence[str]]) -> list[str]:
    """TASK-067: each non-empty cell with its reference ("A1: Total | G1: 1,650.00"), row by row
    from row 1, so a model cites the cells it was shown and code finds them where it says."""
    lines: list[str] = []
    for r, row in enumerate(rows, start=1):
        cells = [f"{column_letters(c)}{r}: {v}" for c, v in enumerate(row) if v.strip()]
        if cells:
            lines.append(" | ".join(cells))
    return lines


def verify(
    citations: Sequence[DocumentCitation],
    pages: Mapping[int, str],
    sheets: Mapping[str, Sequence[Sequence[str]]],
) -> list[VerifiedDocumentCitation]:
    """Each citation, verified against the extraction's pages (by number) and sheets (by name;
    a CSV's single table is named "")."""
    results: list[VerifiedDocumentCitation] = []
    for c in citations:
        reason: str | None
        if c.page is not None:
            reason = page_quote_reason(pages, c.page, c.quote)
        else:
            rows = sheets.get(c.sheet or "")
            if rows is None and len(sheets) == 1:
                rows = next(iter(sheets.values()))  # one sheet: its name may be left out
            cell = citation_cell_text(rows, c.cell or "") if rows is not None else None
            reason = citation_cell_reason(cell, None, c.quote, None, quote_rule="lines")
        results.append(
            VerifiedDocumentCitation(c.page, c.sheet, c.cell, c.quote, reason is None, reason)
        )
    return results
