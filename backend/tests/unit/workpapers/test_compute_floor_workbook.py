"""The compute floor (ADR-079; `compute: 100`) for the workbook formula engine (ADR-237): the
closed grammar's refusals, quoted sheet titles, and the evaluator's negation, division by zero,
type errors, booleans as numbers and MIN; the tie-out helpers' guards."""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus.modules.workpapers.compute.dag import CellInput, Workbook, evaluate
from abacus.modules.workpapers.compute.formula import (
    FormulaError,
    FormulaErrorCode,
    is_valid,
    parse,
)
from abacus.modules.workpapers.compute.tieouts import TallyState, crossfoot, foot, off_by

D = Decimal


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("=$1", FormulaErrorCode.SYNTAX),  # a "$" with no column letter
        ("=$A!B1", FormulaErrorCode.REF_INVALID),  # an anchored word used as a sheet title
        ("=A0", FormulaErrorCode.REF_INVALID),  # row 0 is not a cell
        ("=A1:5", FormulaErrorCode.REF_INVALID),  # a range that does not end on a cell
        ("=SUM(A1:Z1000)", FormulaErrorCode.REF_INVALID),  # over 20,000 cells
        ("=FOO(1)", FormulaErrorCode.UNSUPPORTED_FUNCTION),
        ("=SUM(A1:A2+1)", FormulaErrorCode.TYPE),  # a range inside arithmetic in an argument
        ("=A1:A2%", FormulaErrorCode.TYPE),  # a percent of a range
    ],
)
def test_the_grammar_refuses(text: str, code: FormulaErrorCode) -> None:
    with pytest.raises(FormulaError) as e:
        parse(text)
    assert e.value.code is code


def test_a_quoted_title_with_an_apostrophe_reads() -> None:
    formula = parse("='O''Neil'!A1+1")
    assert formula.references
    assert is_valid("='O''Neil'!A1")


def test_is_valid_answers_false_outside_the_grammar() -> None:
    assert is_valid("=)") is False


def _book(**formulas: str) -> Workbook:
    book = Workbook(("S",))
    book.set("S", "A1", CellInput(D(4)))
    book.set("S", "A2", CellInput(D(2)))
    book.set("S", "A3", CellInput(D(0)))
    for a1, text in formulas.items():
        book.set("S", a1, CellInput(formula=text))
    return book


def test_the_evaluator_negates_divides_compares_and_takes_min() -> None:
    results = evaluate(
        _book(B1="=-A1", B2="=A1/A3", B3="=IF(A1>A2,1,0)", B4="=MIN(A1:A2)", B5="=A1/A2")
    )
    by = {k.rpartition("!")[2]: v for k, v in results.items()}
    assert by["B1"].value == D(-4)
    assert by["B2"].value is None and by["B2"].error is FormulaErrorCode.DIV_ZERO
    assert by["B3"].value == D(1)
    assert by["B4"].value == D(2)
    assert by["B5"].value == D(2)


def test_the_evaluator_guards_a_range_or_a_truth_value_used_as_a_number() -> None:
    # The grammar already refuses both shapes (ranges only in SUM, MIN and MAX; comparisons only
    # in IF), so the evaluator's own guard is checked on its own.
    from abacus.modules.workpapers.compute.dag import (
        _number,  # pyright: ignore[reportPrivateUsage]  # the guard under test
    )

    with pytest.raises(FormulaError) as e:
        _number([D(1), D(2)])
    assert e.value.code is FormulaErrorCode.TYPE
    assert _number(True) == D(1) and _number(False) == D(0)


def test_a_cell_on_an_unknown_sheet_is_refused() -> None:
    with pytest.raises(FormulaError):
        Workbook(("S",)).set("T", "A1", CellInput(D(1)))


def test_off_by_refuses_a_negative_tolerance_and_crossfoot_its_shapes() -> None:
    with pytest.raises(ValueError, match="tolerance"):
        off_by(D(1), D(1), D(-1))
    assert off_by(None, D(1)).state is TallyState.MISSING
    assert foot([D(1), None], D(1)).state is TallyState.MISSING
    assert foot([D(1)], None).state is TallyState.MISSING
    with pytest.raises(ValueError, match="one total per row"):
        crossfoot([[D(1)]], [], [D(1)])
    with pytest.raises(ValueError, match="one cell per column"):
        crossfoot([[D(1), D(2)]], [D(3)], [D(1)])
