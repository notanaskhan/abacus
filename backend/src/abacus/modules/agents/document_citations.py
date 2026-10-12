"""Verifying the upload reviewer's quotes by code (SPEC-030 AC-3; ADR-066; TASK-058 D2).
PROTECTED.

A quote counts only if it is really in the document where the model says: in the extracted text
of that PDF page, or the text of that spreadsheet cell, after Unicode (NFKC), case-insensitive and
whitespace normalisation. The extraction (SPEC-029) is the source of truth; the model's word
never is.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence

from abacus.modules.agents.handoff import DocumentCitation, VerifiedDocumentCitation

_COLUMN = re.compile(r"^([A-Z]{1,3})([1-9][0-9]*)$")


def normalised(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    kept = "".join(
        c for c in folded if unicodedata.category(c) not in ("Cf", "Cc") or c in "\n\t "
    )
    return " ".join(kept.split())


def _column_index(letters: str) -> int:
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter) - ord("A") + 1)
    return index - 1


def _cell_text(rows: Sequence[Sequence[str]], cell: str) -> str | None:
    found = _COLUMN.match(cell)
    if found is None:
        return None
    column, row = _column_index(found.group(1)), int(found.group(2)) - 1
    if row >= len(rows) or column >= len(rows[row]):
        return None
    return rows[row][column]


def verify(
    citations: Sequence[DocumentCitation],
    pages: Mapping[int, str],
    sheets: Mapping[str, Sequence[Sequence[str]]],
) -> list[VerifiedDocumentCitation]:
    """Each citation, verified against the extraction's pages (by number) and sheets (by name;
    a CSV's single table is named "")."""
    results: list[VerifiedDocumentCitation] = []
    for c in citations:
        quote = normalised(c.quote)
        reason: str | None
        if c.page is not None:
            text = pages.get(c.page)
            reason = (
                "page_not_found"
                if text is None
                else (None if quote and quote in normalised(text) else "quote_not_found")
            )
        else:
            rows = sheets.get(c.sheet or "")
            if rows is None and len(sheets) == 1:
                rows = next(iter(sheets.values()))  # one sheet: its name may be left out
            cell = _cell_text(rows, c.cell or "") if rows is not None else None
            reason = (
                "cell_not_found"
                if cell is None
                else (None if quote and quote in normalised(cell) else "quote_not_found")
            )
        results.append(
            VerifiedDocumentCitation(c.page, c.sheet, c.cell, c.quote, reason is None, reason)
        )
    return results
