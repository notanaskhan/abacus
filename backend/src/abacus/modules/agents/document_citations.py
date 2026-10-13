"""Verifying the upload reviewer's quotes by code (SPEC-030 AC-3; ADR-066; TASK-058 D2).
PROTECTED.

A quote counts only if it is really in the document where the model says: in the extracted text
of that PDF page, or the text of that spreadsheet cell, after Unicode (NFKC), case-insensitive and
whitespace normalisation; a quote joining several lines of one page counts when every line is
there. The extraction (SPEC-029) is the source of truth; the model's word never is.
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


def column_letters(index: int) -> str:
    """0 → A, 25 → Z, 26 → AA (the inverse of `_column_index`)."""
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(ord("A") + rest) + letters
    return letters


def sheet_lines(rows: Sequence[Sequence[str]]) -> list[str]:
    """TASK-067: each non-empty cell with its reference ("A1: Total | G1: 1,650.00"), row by row
    from row 1, so a model cites the cells it was shown and code finds them where it says."""
    lines: list[str] = []
    for r, row in enumerate(rows, start=1):
        cells = [f"{column_letters(c)}{r}: {v}" for c, v in enumerate(row) if v.strip()]
        if cells:
            lines.append(" | ".join(cells))
    return lines


def _cell_text(rows: Sequence[Sequence[str]], cell: str) -> str | None:
    found = _COLUMN.match(cell)
    if found is None:
        return None
    column, row = _column_index(found.group(1)), int(found.group(2)) - 1
    if row >= len(rows) or column >= len(rows[row]):
        return None
    return rows[row][column]


def _found(quote: str, text: str) -> bool:
    """Every line of the quote appears in the text (a quote may join lines from one page)."""
    parts = [normalised(line) for line in quote.splitlines() if normalised(line)]
    haystack = normalised(text)
    return bool(parts) and all(part in haystack for part in parts)


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
            text = pages.get(c.page)
            reason = (
                "page_not_found"
                if text is None
                else (None if _found(c.quote, text) else "quote_not_found")
            )
        else:
            rows = sheets.get(c.sheet or "")
            if rows is None and len(sheets) == 1:
                rows = next(iter(sheets.values()))  # one sheet: its name may be left out
            cell = _cell_text(rows, c.cell or "") if rows is not None else None
            reason = (
                "cell_not_found"
                if cell is None
                else (None if _found(c.quote, cell) else "quote_not_found")
            )
        results.append(
            VerifiedDocumentCitation(c.page, c.sheet, c.cell, c.quote, reason is None, reason)
        )
    return results
