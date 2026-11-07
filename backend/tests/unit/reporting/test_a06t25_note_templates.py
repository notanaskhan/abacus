"""A-06-T25 (DEC-2389): note templates parse as hostile content, and code fills their figures."""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.methodology.note_templates import parse_notes
from abacus.modules.reporting.compute.fs_draft import (
    DraftLine,
    DraftNote,
    DraftValue,
    NoteInput,
    content_hash,
    references_of,
    render_notes,
)

_LINES = (
    DraftLine(
        "net_assets",
        "assets",
        "investments",
        "Investments",
        0,
        None,
        (
            DraftValue(2025, Decimal("16500000.00"), "tb_linked"),
            DraftValue(2024, Decimal("13940000.00"), "tb_linked"),
        ),
    ),
    DraftLine(
        "net_assets",
        "assets",
        "fees",
        "Fees",
        1,
        None,
        (DraftValue(2025, Decimal("-64.38"), "tb_linked"),),
    ),
)


def test_ac_notes_parse_in_number_order() -> None:
    content = b"number,title,body,line_keys\n2,Tax Status,,\n1,Plan,Text,investments;notes\n"
    notes, problems = parse_notes(content)
    assert problems == []
    assert [n["number"] for n in notes] == [1, 2]
    assert notes[0]["line_keys"] == ["investments", "notes"]


def test_ac_problems_name_where_they_are_never_the_cell() -> None:
    content = b"number,title,body,line_keys\n0,,,\n1,Plan,,bad key\n1,Plan again,,\n"
    _notes, problems = parse_notes(content)
    assert problems == [
        "row 2: number",
        "row 2: title",
        "row 3: line_keys",
        "row 4: duplicate_number",
    ]
    assert parse_notes(b"\xff\xfe")[1] == ["not_csv"]
    assert parse_notes(b"number,title,body,line_keys\n")[1] == ["empty"]


def test_ac_a_line_named_by_two_notes_carries_both() -> None:
    notes = (
        NoteInput(4, "B", "", ("investments",)),
        NoteInput(3, "A", "", ("Investments", "fees")),
    )
    assert references_of(notes) == {"investments": "Notes 3, 4", "fees": "Note 3"}


def test_ac_code_fills_the_years_figure_and_names_what_it_cannot() -> None:
    note = NoteInput(3, "A", "Total {{investments}}, fees {{fees}}, other {{ nope }}.", ())
    (drafted,) = render_notes((note,), _LINES, 2025)
    assert drafted.body == "Total 16,500,000, fees (64.38), other {{ nope }}."
    assert drafted.unresolved == ("nope",)
    (prior,) = render_notes((note,), _LINES, 2024)
    assert prior.body.startswith("Total 13,940,000, fees {{fees}}")


def test_ac_notes_change_the_hash_and_no_notes_keep_it() -> None:
    assert content_hash(_LINES) == content_hash(_LINES, ())
    assert content_hash(_LINES) != content_hash(_LINES, (DraftNote(1, "A", "", ()),))
