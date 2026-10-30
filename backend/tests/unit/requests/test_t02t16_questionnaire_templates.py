"""T-02-T16 (TASK-2323; T-02 §3.5; DEC-1369): organizer templates parse from CSV, XLSX and JSON
to the same template; problems are codes with their row, never the cell; a formula cell is read
as its cached value; and the dry-run change list matches questions by key."""

from __future__ import annotations

import io
import json

import pytest
from openpyxl import Workbook

from abacus.modules.requests import questionnaire_templates as t

ROWS = [
    ("Income", "wallet", "w2", "yes_no", "Did you receive a W-2?", "", "", ""),
    ("Income", "wallet", "w2_upload", "upload_if_yes", "Upload your W-2", "", "w2", "yes"),
    ("Life events", "", "moved", "yes_no", "Did you move in 2025?", "", "", ""),
]


def _csv(rows: list[tuple[str, ...]] = ROWS) -> bytes:
    lines = [",".join(t.COLUMNS)] + [",".join(r) for r in rows]
    return ("\n".join(lines) + "\n").encode()


def test_csv_xlsx_and_json_give_the_same_template() -> None:
    from_csv = t.parse(_csv(), "csv")
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(list(t.COLUMNS))
    for r in ROWS:
        sheet.append(list(r))
    out = io.BytesIO()
    book.save(out)
    from_xlsx = t.parse(out.getvalue(), "xlsx")
    from_json = t.parse(json.dumps(from_csv.content()).encode(), "json")
    assert from_csv == from_xlsx == from_json
    assert [g.name for g in from_csv.sections] == ["Income", "Life events"]
    assert from_csv.questions()["w2_upload"].conditional_on == "w2"


def test_problems_are_codes_with_their_row() -> None:
    bad = [
        ("Income", "", "W 2", "yes_no", "Wording", "", "", ""),
        ("Income", "", "x", "essay", "Wording", "", "", ""),
        ("Income", "", "y", "yes_no", "Wording", "", "later", ""),
    ]
    with pytest.raises(t.TemplateInvalid) as raised:
        t.parse(_csv(bad), "csv")
    assert raised.value.problems == ["row 2: key", "row 3: type", "row 4: conditional_on"]
    with pytest.raises(t.TemplateInvalid) as missing:
        t.parse(b"section,key\nIncome,w2\n", "csv")
    assert missing.value.problems == ["missing_column: type", "missing_column: client_wording"]


def test_a_formula_cell_is_its_cached_value_never_a_formula() -> None:
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(list(t.COLUMNS))
    sheet.append(["Income", "", "w2", "yes_no", '=HYPERLINK("x")', "", "", ""])
    out = io.BytesIO()
    book.save(out)
    # Never recalculated: a formula with no cached value reads as empty, a refused wording.
    with pytest.raises(t.TemplateInvalid) as raised:
        t.parse(out.getvalue(), "xlsx")
    assert raised.value.problems == ["row 2: client_wording"]


def test_the_change_list_matches_by_key() -> None:
    before = t.parse(_csv(), "csv")
    after = t.parse(
        _csv(
            [
                ("Income", "wallet", "w2", "yes_no", "Did you receive a W-2 in 2025?", "", "", ""),
                ("Life events", "", "moved", "yes_no", "Did you move in 2025?", "", "", ""),
                ("Life events", "", "baby", "yes_no", "Did you have a child?", "", "", ""),
            ]
        ),
        "csv",
    )
    changes = t.changes_between(before, after)
    assert (changes.added, changes.changed, changes.removed) == (
        ("baby",),
        ("w2",),
        ("w2_upload",),
    )
    assert t.changes_between(None, before).added == ("moved", "w2", "w2_upload")


def test_not_a_file_of_the_format_is_refused() -> None:
    for content, fmt, code in ((b"{", "json", "not_json"), (b"x", "xlsx", "not_xlsx")):
        with pytest.raises(t.TemplateInvalid) as raised:
            t.parse(content, fmt)  # type: ignore[arg-type]  # each format in turn
        assert raised.value.problems == [code]
