"""A-06-T23 (TASK-3258; SPEC-642; DEC-2238): AUD-17's sign-off matrix and EP involvement.

Row acceptance: "The Northwind matrix returns 26 = 6 + 3 + 7 + 6 + 4 rows with footer Prepared
25, Reviewed 24, Partner 8 of 13, EQR 0 of 6 and one Changed after sign-off." The seeded figures
are A-06-T21's and the journey's; here the footer arithmetic and the cell rules are pinned.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from abacus.modules.assurance.review_matrix import Cell, Row, footer_of, initials, reviewed

AT = datetime(2026, 10, 2, 13, 58, tzinfo=UTC)


def _cell(level: int, state: str) -> Cell:
    signed = state in ("signed", "stale")
    return Cell(
        level,
        state,  # type: ignore[arg-type] -- boto3 ships no stubs
        "MD" if signed else None,
        uuid4() if signed else None,
        AT if signed else None,
        2 if signed else None,
        "7c41a9e2" if signed else None,
    )


def _row(*states: str) -> Row:
    return Row(
        "workpaper",
        uuid4(),
        "EBP-04",
        "Contributions",
        "fieldwork",
        tuple(_cell(i + 1, s) for i, s in enumerate(states)),
    )


def test_footer_counts_signed_levels_and_required_partner_and_eqr_columns() -> None:
    rows = (
        _row("signed", "stale", "pending", "signed", "pending"),
        _row("signed", "signed", "signed", "pending", "not_required"),
        _row("pending", "pending", "not_required", "not_required", "not_required"),
    )
    f = footer_of(rows)
    # DEC-2397: the first row's L2 is stale and its L3 pending, so it isn't reviewed.
    assert (f.prepared, f.reviewed) == (2, 1)
    assert (f.partner_signed, f.partner_required) == (1, 2)
    assert (f.eqr_signed, f.eqr_required) == (0, 1)
    assert f.changed_after_sign_off == 1


def test_a_stale_cell_still_counts_as_signed_and_flags_its_row() -> None:
    f = footer_of((_row("stale", "not_required", "not_required", "not_required", "not_required"),))
    assert (f.prepared, f.changed_after_sign_off) == (1, 1)


def test_reviewed_is_every_required_review_level_current_as_the_handoff_counts() -> None:
    """AUD-17's drawn rows (TASK-3398, DEC-2397): the manager's review in L3 with L2 "—" counts,
    a row needing no L2 or L3 counts once prepared, a stale L2 doesn't, nor an unprepared row."""
    rows = {
        "Trial Balance": _row("signed", "not_required", "signed", "not_required", "not_required"),
        "Eligibility": _row("signed", "signed", "signed", "signed", "not_required"),
        "Findings": _row("signed", "not_required", "not_required", "signed", "pending"),
        "Contributions": _row("signed", "stale", "pending", "pending", "not_required"),
        "Checklist": _row("pending", "not_required", "not_required", "pending", "not_required"),
    }
    assert [k for k, r in rows.items() if reviewed(r)] == [
        "Trial Balance",
        "Eligibility",
        "Findings",
    ]
    assert footer_of(tuple(rows.values())).reviewed == 3


def test_initials_are_first_and_last_name() -> None:
    assert initials("Margaret Okonkwo") == "MO"
    assert initials("Ana Cruz") == "AC"
    assert initials("Thomas") == "TH"
    assert initials("") == "?"
