"""A-06-T25 (TASK-3305; DEC-2304): the `fs_draft` and tie-out engines, from the row's acceptance.

Row: "Northwind v3 ties 63 of 63 (24 + 15 + 24), v1 reports 62 of 63 with Benefits paid off 14,850
caused by RJE-1". The full Northwind figures land with A-06-T28's scenario; here the engine rules
hold on a small statement with the same benefit-paid miss.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from abacus.modules.reporting.compute import fs_draft, tie_out


@dataclass(frozen=True)
class _Line:
    key: str
    label: str
    cy: Decimal
    py: Decimal | None


@dataclass(frozen=True)
class _Group:
    key: str
    label: str
    class_: str
    lines: tuple[_Line, ...]
    cy: Decimal
    py: Decimal | None


_D = Decimal
_GROUPS = (
    _Group(
        "benefits", "Deductions", "expenses",
        (_Line("benefits_paid", "Benefits paid", _D("812650.00"), _D("700000.00")),
         _Line("admin", "Administrative expenses", _D("38400.00"), _D("30000.00"))),
        _D("851050.00"), _D("730000.00"),
    ),
)  # fmt: skip


def _lines(benefits: str = "812650.00") -> tuple[fs_draft.DraftLine, ...]:
    groups = (
        _Group(
            "benefits", "Deductions", "expenses",
            (_Line("benefits_paid", "Benefits paid", _D(benefits), _D("700000.00")),
             _Line("admin", "Administrative expenses", _D("38400.00"), _D("30000.00"))),
            _D(benefits) + _D("38400.00"), _D("730000.00"),
        ),
    )  # fmt: skip
    return fs_draft.draft(
        groups, 2025, {"benefits_paid": ("6000",), "admin": ("6100",)}, ("AJE-1",), {}
    )


def _values(lines: tuple[fs_draft.DraftLine, ...]) -> list[tie_out.Value]:
    return [
        tie_out.Value(
            line.line_key, line.label, v.year, v.value, v.source, v.terms, v.accounts, v.entries
        )
        for line in lines
        for v in line.values
    ]


_EXPECTED = {
    ("benefits_paid", 2025): _D("812650.00"),
    ("benefits_paid", 2024): _D("700000.00"),
    ("admin", 2025): _D("38400.00"),
    ("admin", 2024): _D("30000.00"),
}


def test_ac_the_draft_is_deterministic_and_marks_its_sources() -> None:
    assert fs_draft.content_hash(_lines()) == fs_draft.content_hash(_lines())
    assert fs_draft.content_hash(_lines()) != fs_draft.content_hash(_lines("797800.00"))
    by_key = {line.line_key: line for line in _lines()}
    assert by_key["benefits_paid"].values[0].source == "tb_linked"
    assert by_key["benefits_paid"].values[0].accounts == ("6000",)
    assert by_key["benefits.total"].values[0].source == "formula"
    assert by_key["benefits.total"].values[0].terms == ("benefits_paid", "admin")


def test_ac_a_clean_version_ties_every_figure() -> None:
    result = tie_out.tie_out(_values(_lines()), _EXPECTED, ())
    assert result.tied == result.total
    assert result.off == ()


def test_ac_a_stale_version_is_off_and_names_the_entry_it_does_not_reflect() -> None:
    effects = (tie_out.EntryEffect("RJE-1", "6000", _D("14850.00")),)
    result = tie_out.tie_out(_values(_lines("797800.00")), _EXPECTED, effects)
    off = {o.line_key: o for o in result.off}
    assert off["benefits_paid"].off_by == _D("-14850.00")
    assert off["benefits_paid"].cause == "RJE-1"


def test_ac_an_entry_the_version_reflects_is_not_the_cause() -> None:
    effects = (tie_out.EntryEffect("AJE-1", "6000", _D("14850.00")),)
    result = tie_out.tie_out(_values(_lines("797800.00")), _EXPECTED, effects)
    assert {o.line_key: o.cause for o in result.off}["benefits_paid"] is None


def test_ac_a_new_recorded_entry_changes_the_adjustments_hash() -> None:
    assert fs_draft.adjustments_hash(["AJE-1"]) != fs_draft.adjustments_hash(["AJE-1", "RJE-1"])
    assert fs_draft.adjustments_hash(["A", "B"]) == fs_draft.adjustments_hash(["B", "A"])
