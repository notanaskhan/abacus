"""The compute floor (ADR-079; `compute: 100`): the FS draft's key normaliser, a group the
statements do not present, a current-year-only line, and a tie-out value that is neither a
formula nor TB-linked."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from abacus.modules.reporting.compute.fs_draft import draft, line_key
from abacus.modules.reporting.compute.tie_out import Value, tie_out


@dataclass(frozen=True)
class _Line:
    key: str
    label: str
    cy: Decimal
    py: Decimal | None = None


@dataclass(frozen=True)
class _Group:
    key: str
    label: str
    class_: str
    lines: tuple[_Line, ...] = field(default_factory=tuple[_Line, ...])
    cy: Decimal = Decimal(0)
    py: Decimal | None = None


def test_a_key_that_does_not_start_with_a_letter_is_prefixed() -> None:
    assert line_key("1200 Investments") == "l_1200_investments"
    assert line_key("!!!") == "l_"


def test_a_group_outside_the_statements_is_left_out() -> None:
    assert draft([_Group("memo", "Memo", "memo")], 2025, {}, (), {}) == ()


def test_a_line_without_a_prior_year_carries_only_the_current_year() -> None:
    group = _Group("cash", "Cash", "assets", (_Line("cash.operating", "Operating", Decimal(5)),),
                   Decimal(5))  # fmt: skip
    lines = draft([group], 2025, {}, (), {})
    first = next(line for line in lines if line.line_key == "cash.operating")
    assert [v.year for v in first.values] == [2025]


def test_a_value_neither_formula_nor_tb_linked_is_not_tied() -> None:
    entered = Value("note.text", "Note", 2025, Decimal(7), "entered")
    result = tie_out([entered], {}, ())
    assert result.off == () or list(result.off) == []
