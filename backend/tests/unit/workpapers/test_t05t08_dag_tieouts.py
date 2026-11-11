"""T-05-T08 (TASK-6809; SPEC-651 AC-3.3, AC-4.2, AC-4.3; ADR-237; DEC-3407): the workbook's
dependency graph, evaluation and tie-outs.

Row acceptance: "I18 = F18+G18+H18 evaluates to (94,000), an edit recomputes only its dependents,
and D+E+F+G+H+I = J holds on every 05 Capital row."

Figures: 01 Trial Balance row 18 is account 2050 Accrued expenses (TXP-02: UTB (75,500), AJE
(18,500), RJE —, ATB (94,000)); 05 Capital row 12 is Jonah Feld's capital after the 18A fix
(TXP-11 B: 1,500,000 + 250,000 + 312,500 + 0 + 1,550 - 150,000 = 1,914,050).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from abacus.modules.workpapers.compute.dag import (
    CellInput,
    CycleError,
    Workbook,
    build_graph,
    dirty,
    evaluate,
    recompute,
)
from abacus.modules.workpapers.compute.formula import FormulaErrorCode
from abacus.modules.workpapers.compute.tieouts import (
    TallyState,
    crossfoot,
    foot,
    off_by,
    tie,
)

D = Decimal
SHEETS = ("01 Trial Balance", "05 Capital", "06 Schedule K")


def _tb() -> Workbook:
    book = Workbook(SHEETS)
    book.set("01 Trial Balance", "F18", CellInput(D("-75500")))
    book.set("01 Trial Balance", "G18", CellInput(D("-18500")))
    book.set("01 Trial Balance", "H18", CellInput(None))  # RJE —
    book.set("01 Trial Balance", "I18", CellInput(formula="=F18+G18+H18"))
    return book


def test_ac_4_2_i18_evaluates_to_94000_negative() -> None:
    results = evaluate(_tb())
    i18 = results["'01 Trial Balance'!I18"]
    assert i18.value == D("-94000") and i18.error is None
    assert i18.provenance is not None
    assert i18.provenance.text == "=F18+G18+H18"
    assert i18.provenance.inputs == (
        "'01 Trial Balance'!F18",
        "'01 Trial Balance'!G18",
        "'01 Trial Balance'!H18",
    )


def _capital() -> Workbook:
    book = Workbook(SHEETS)
    row = {"D": "1500000", "E": "250000", "F": "312500", "G": "0", "I": "-150000"}
    for column, value in row.items():
        book.set("05 Capital", f"{column}12", CellInput(D(value)))
    book.set("06 Schedule K", "C31", CellInput(D("6200")))
    book.set("05 Capital", "H12", CellInput(formula="='06 Schedule K'!C31*25%"))
    book.set("05 Capital", "J12", CellInput(formula="=SUM(D12:I12)"))
    book.set("05 Capital", "J13", CellInput(formula="=J12"))
    book.set("05 Capital", "K12", CellInput(formula="=D12"))  # not downstream of H12
    return book


def test_ac_4_2_the_capital_row_crossfoots() -> None:
    results = evaluate(_capital())
    assert results["'05 Capital'!H12"].value == D("1550")
    assert results["'05 Capital'!J12"].value == D("1914050")
    parts = [D("1500000"), D("250000"), D("312500"), D("0"), D("1550"), D("-150000")]
    assert foot(parts, results["'05 Capital'!J12"].value).state is TallyState.TIES


def test_ac_4_3_an_edit_recomputes_only_its_dependents() -> None:
    book = _capital()
    graph = build_graph(book)
    first = evaluate(book, graph)
    changed = book.set("06 Schedule K", "C31", CellInput(D("6204")))
    assert dirty(graph, [changed]) == (
        "'05 Capital'!H12",
        "'05 Capital'!J12",
        "'05 Capital'!J13",
    )
    after, touched = recompute(book, graph, first, [changed])
    assert "'05 Capital'!K12" not in touched
    assert after["'05 Capital'!K12"] is first["'05 Capital'!K12"]
    assert after["'05 Capital'!H12"].value == D("1551")


def test_the_order_is_deterministic_by_sheet_row_column() -> None:
    graph = build_graph(_capital())
    assert graph.order == build_graph(_capital()).order
    assert graph.order.index("'05 Capital'!H12") < graph.order.index("'05 Capital'!J12")


def test_a_cycle_is_refused_with_its_addresses() -> None:
    book = Workbook(SHEETS)
    book.set("05 Capital", "A1", CellInput(formula="=B1+1"))
    book.set("05 Capital", "B1", CellInput(formula="=A1"))
    with pytest.raises(CycleError) as raised:
        build_graph(book)
    assert raised.value.code is FormulaErrorCode.CYCLE
    assert set(raised.value.addresses) == {"'05 Capital'!A1", "'05 Capital'!B1"}


def test_division_by_zero_marks_the_cell_and_its_readers() -> None:
    book = Workbook(SHEETS)
    book.set("05 Capital", "A1", CellInput(D("10")))
    book.set("05 Capital", "B1", CellInput(formula="=A1/A2"))
    book.set("05 Capital", "C1", CellInput(formula="=B1+1"))
    results = evaluate(book)
    assert results["'05 Capital'!B1"].error is FormulaErrorCode.DIV_ZERO
    assert results["'05 Capital'!C1"].error is FormulaErrorCode.DIV_ZERO


def test_functions_round_if_min_max() -> None:
    book = Workbook(SHEETS)
    book.set("05 Capital", "A1", CellInput(D("2.345")))
    book.set("05 Capital", "B1", CellInput(formula="=ROUND(A1,2)"))
    book.set("05 Capital", "C1", CellInput(formula="=IF(A1>2,MAX(A1,9),MIN(A1,1))"))
    results = evaluate(book)
    assert results["'05 Capital'!B1"].value == D("2.35")
    assert results["'05 Capital'!C1"].value == D("9")


def test_tallies() -> None:
    assert tie(D("23014"), D("23015")).state is TallyState.OFF
    assert off_by(D("23014"), D("23015"), D("1")).state is TallyState.WITHIN
    assert tie(None, D("1")).state is TallyState.MISSING
    rows = [[D("1"), D("2")], [D("3"), D("4")]]
    tallies = crossfoot(rows, [D("3"), D("7")], [D("4"), D("6")])
    assert all(t.ok for t in tallies) and len(tallies) == 2 + 2 + 1


def test_no_eval_in_the_package() -> None:
    root = Path(__file__).resolve().parents[3] / "src/abacus/modules/workpapers/compute"
    for path in ("dag.py", "tieouts.py"):
        source = (root / path).read_text(encoding="utf-8")
        for banned in ("eval(", "exec(", "compile(", "__import__"):
            assert banned not in source.replace("_eval(", "").replace("evaluate(", ""), (
                path,
                banned,
            )
