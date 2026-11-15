"""A-08-T09 (TASK-8048; ADR-400, P-58; SPEC-657 AC-0.7, AC-1.3; DEC-5033): the JE fields.

An export that carries posted-by, entered-at, source and approver columns fills them; one that
does not reads them as unavailable and parses exactly as before; the source column maps to manual
or system only; and no value in the JE columns can break a parse (Hypothesis). The migration adds
nullable columns only: no row of the immutable ledger is rewritten.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from abacus.modules.connections.gl_formats import GL_FORMATS, JE_FIELDS
from abacus.modules.connections.gl_parse import parse_gl_to_file, read_entries

_BASE = ["Account", "Date", "Type", "Document Number", "Name", "Memo", "Debit", "Credit"]
_JE = ["Created By", "Date Created", "Source", "Approved By"]
_MIGRATION = Path(__file__).parents[3] / "migrations" / "versions" / "0888_gl_je_fields.py"


def _netsuite(je: list[list[str]] | None) -> bytes:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["Granite Peak Outdoor Supply, Inc."])
    w.writerow(["General Ledger"])
    w.writerow(["Jul 2025 - Jun 2026"])
    w.writerow([])
    w.writerow(_BASE + (_JE if je is not None else []))
    rows = [
        [
            "2100 - Accrued interest",
            "06/30/2026",
            "Journal",
            "JE-26-17994",
            "",
            "Accrue Q4 interest",
            "",
            "100000.00",
        ],
        [
            "7100 - Interest expense",
            "06/30/2026",
            "Journal",
            "JE-26-17994",
            "",
            "Accrue Q4 interest",
            "100000.00",
            "",
        ],
    ]
    for i, row in enumerate(rows):
        w.writerow(row + (je[i] if je is not None else []))
    return out.getvalue().encode("utf-8")


def _parse(content: bytes, tmp: Path):  # noqa: ANN202 -- the summary and the entries
    out = tmp / "entries.csv"
    summary = parse_gl_to_file(
        content, "netsuite_gl_csv", date(2025, 7, 1), date(2026, 6, 30), str(out)
    )
    return summary, list(read_entries(str(out)))


def test_ac0_7_an_export_with_the_columns_fills_them(tmp_path: Path) -> None:
    je = [["s.baptiste", "06/30/2026 09:15 AM", "Manual", "h.leclerc"]] * 2
    summary, entries = _parse(_netsuite(je), tmp_path)
    assert summary.je_fields_available == frozenset(JE_FIELDS)
    first = entries[0]
    assert (first.posted_by, first.source, first.approver) == ("s.baptiste", "manual", "h.leclerc")
    assert first.entered_at == datetime(2026, 6, 30, 9, 15)


def test_ac1_3_an_export_without_them_reads_unavailable_and_parses_as_before(
    tmp_path: Path,
) -> None:
    summary, entries = _parse(_netsuite(None), tmp_path)
    assert summary.je_fields_available == frozenset()
    assert summary.line_count == 2 and summary.total_debit == summary.total_credit
    assert all(e.posted_by is None and e.source is None and e.entered_at is None for e in entries)


def test_the_formats_that_cannot_carry_them_map_nothing() -> None:
    assert GL_FORMATS["xero_gl_xlsx"].je_headers == {}
    assert GL_FORMATS["qbd_gl_xlsx"].je_headers == {}  # last modified by is not the creator
    assert set(GL_FORMATS["netsuite_gl_csv"].je_headers) == set(JE_FIELDS)


_cell = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=200)


@settings(
    max_examples=150, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None
)
@given(values=st.lists(st.lists(_cell, min_size=4, max_size=4), min_size=2, max_size=2))
def test_no_je_column_value_breaks_a_parse(tmp_path: Path, values: list[list[str]]) -> None:
    summary, entries = _parse(_netsuite(values), tmp_path)
    assert summary.line_count == 2
    for e in entries:
        assert e.source in (None, "manual", "system")
        assert e.posted_by is None or 1 <= len(e.posted_by) <= 120
        assert e.approver is None or 1 <= len(e.approver) <= 120


def test_ac0_7_the_migration_is_expand_only() -> None:
    text = _MIGRATION.read_text(encoding="utf-8")
    upgrade = text.split("def upgrade", 1)[1].split("def downgrade", 1)[0]
    assert "UPDATE " not in upgrade and "DELETE " not in upgrade
    assert upgrade.count("ADD COLUMN") == 5
    assert "NOT NULL DEFAULT '{{}}'" in upgrade  # every earlier snapshot reads unavailable
