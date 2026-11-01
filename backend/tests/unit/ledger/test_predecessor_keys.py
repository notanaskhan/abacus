"""A predecessor auditor's mapping sheet as the prior year (TASK-2718; DEC-1769; ADR-050):
`ledger.compute.mapping.predecessor_keys`, pure."""

from __future__ import annotations

import pytest

from abacus.modules.ledger.compute.mapping import PredecessorColumns, predecessor_keys

LINES = {
    "Cash": "cash",
    "cash": "cash",
    "PP&E, net": "ppe_net",
    "ppe_net": "ppe_net",
    "Revolver — Front Range Bank": "revolver",
    "revolver": "revolver",
}


def test_codes_read_normalised_and_lines_by_label_or_key_folded() -> None:
    rows = [
        ("", "", ""),
        ("Account No.", "Description", "FS Line"),
        ("1010", "Front Range Bank operating", "CASH"),
        ("16-10", "Equipment", "PP&E,  Net"),
        ("2310", "Revolver", "revolver"),
        ("2320", "Revolver fees", "Revolver - Front Range Bank"),
    ]
    assert predecessor_keys(rows, LINES) == {
        "1010": "cash",
        "1610": "ppe_net",
        "2310": "revolver",
        "2320": "revolver",
    }


def test_a_line_the_version_does_not_name_or_a_blank_code_is_left_out() -> None:
    rows = [
        ("Account", "Mapped to"),
        ("1900", "Deferred charges"),
        ("", "Cash"),
        ("1010", ""),
        ("1020",),  # a short row: no FS-line cell
        ("1030", "cash"),
    ]
    assert predecessor_keys(rows, LINES) == {"1030": "cash"}


def test_the_first_matching_header_wins_for_each_column() -> None:
    rows = [("Code", "Account", "Mapping", "FS line"), ("1010", "9999", "cash", "ppe_net")]
    assert predecessor_keys(rows, LINES) == {"1010": "cash"}


@pytest.mark.parametrize(
    ("rows", "reason"),
    [
        ([], "empty"),
        ([("", " ")], "empty"),
        ([("Account", "Description"), ("1010", "Cash")], "columns"),
        ([("Description", "FS line"), ("Cash", "cash")], "columns"),
    ],
)
def test_a_sheet_without_both_columns_is_refused(rows: list[tuple[str, ...]], reason: str) -> None:
    with pytest.raises(PredecessorColumns, match=f"^{reason}$"):
        predecessor_keys(rows, LINES)


def test_a_row_shorter_than_the_code_column_is_skipped() -> None:
    rows = [("FS line", "Account"), ("cash",), ("cash", "1010")]
    assert predecessor_keys(rows, LINES) == {"1010": "cash"}
