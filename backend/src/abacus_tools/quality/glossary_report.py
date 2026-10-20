"""Glossary report: terms and "Don't use" entries per section of docs/product/glossary.md.

Run: python3 -I backend/src/abacus_tools/quality/glossary_report.py [path-to-glossary]

Reads only the standard library. For every "## " section it counts the rows of each table whose
first column is "Term" and the comma-separated entries in that table's "Don't use" column
(an em dash means none), then prints the totals. Always exits 0.
"""

from __future__ import annotations

import sys
from pathlib import Path

GLOSSARY = Path(__file__).resolve().parents[4] / "docs" / "product" / "glossary.md"
NONE = {"", "—", "-"}


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def count_sections(text: str) -> list[tuple[str, int, int]]:
    """Return (section title, term count, don't-use entry count) for every "## " section."""
    sections: list[tuple[str, int, int]] = []
    title: str | None = None
    terms = bans = 0
    dont_use_col: int | None = None
    in_term_table = False
    for line in text.splitlines():
        if line.startswith("## "):
            if title is not None:
                sections.append((title, terms, bans))
            title, terms, bans = line[3:].strip(), 0, 0
            dont_use_col, in_term_table = None, False
        elif not line.startswith("|"):
            dont_use_col, in_term_table = None, False
        elif dont_use_col is None and not in_term_table:
            header = _cells(line)
            in_term_table = header[0] == "Term" and "Don't use" in header
            if in_term_table:
                dont_use_col = header.index("Don't use")
        elif in_term_table and dont_use_col is not None and not set(line) <= set("|-: "):
            cells = _cells(line)
            terms += 1
            if dont_use_col < len(cells):
                bans += sum(1 for e in cells[dont_use_col].split(",") if e.strip() not in NONE)
    if title is not None:
        sections.append((title, terms, bans))
    return sections


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else GLOSSARY
    rows = count_sections(path.read_text(encoding="utf-8"))
    width = max([len(r[0]) for r in rows] + [7])
    print(f"{'Section':<{width}}  Terms  Don't use")
    for name, terms, bans in rows:
        print(f"{name:<{width}}  {terms:>5}  {bans:>9}")
    total_terms = sum(r[1] for r in rows)
    total_bans = sum(r[2] for r in rows)
    print(f"{'Total':<{width}}  {total_terms:>5}  {total_bans:>9}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
