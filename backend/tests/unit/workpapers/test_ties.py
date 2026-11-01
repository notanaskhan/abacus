"""SPEC-310 (TASK-321): the tie engine, check validation, and TB() in working-paper formulas."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from abacus.modules.workpapers.formulas import TbSource
from abacus.modules.workpapers.formulas import evaluate as formula
from abacus.modules.workpapers.service import TbLink, content_hash, content_of
from abacus.modules.workpapers.tie_out import CheckInput, CheckInvalid, CitationRequired, clean
from abacus.modules.workpapers.ties import MINUS, Balances, Component, Definition, evaluate

D = Decimal
BAL = Balances(
    eoy={"3000": D("-16812400.00"), "1500": D("1606560.00"), "2500": D("-312400.00")},
    boy=None,
    totals={"eoy": (D("100.00"), D("100.00")), "boy": None},
)


def _def(**over: object) -> Definition:
    base: dict[str, object] = {
        "kind": "tie",
        "accounts": ("3000",),
        "column": "eoy",
        "negate": True,
        "expected": D("16812400.00"),
        "components": (),
        "tolerance": D("0.00"),
    }
    return Definition(**{**base, **over})  # type: ignore[arg-type]  # test overrides


def test_ac1_a_tie_within_tolerance_ties_and_outside_is_off() -> None:
    assert evaluate(_def(), BAL).status == "tie"
    off = evaluate(_def(accounts=("1500",), negate=False, expected=D("1605000.00")), BAL)
    assert (off.status, off.difference) == ("off", D("1560.00"))
    near = _def(accounts=("1500",), negate=False, expected=D("1606559.50"), tolerance=D("1.00"))
    assert evaluate(near, BAL).status == "tie"


def test_ac1_rollforward_shows_its_arithmetic() -> None:
    parts = (
        Component("Beginning", 1, D("288500.00")),
        Component("Draws", 1, D("96200.00")),
        Component("Repayments", -1, D("57450.00")),
        Component("Forgiven", -1, D("14850.00")),
    )
    r = evaluate(
        _def(kind="rollforward", accounts=("2500",), expected=None, components=parts), BAL
    )
    assert r.status == "tie" and r.expected == D("312400.00")
    assert r.formula == f"288,500.00 + 96,200.00 {MINUS} 57,450.00 {MINUS} 14,850.00 = 312,400.00"


def test_ac1_pending_when_the_trial_balance_cant_answer() -> None:
    assert evaluate(_def(accounts=("9999",)), BAL).missing == ("9999",)
    assert evaluate(_def(column="boy"), BAL).status == "pending"
    assert evaluate(_def(kind="balanced", column="boy"), BAL).status == "pending"
    assert evaluate(_def(kind="balanced"), BAL).status == "tie"


def _input(**over: object) -> CheckInput:
    base: dict[str, object] = {
        "label": " Net assets ",
        "kind": "tie",
        "accounts": ("3000", "3000"),
        "column": "eoy",
        "negate": True,
        "expected": D("16812400"),
        "components": (),
        "citation_ids": (uuid4(),),
        "tolerance": D("0"),
    }
    return CheckInput(**{**base, **over})  # type: ignore[arg-type]  # test overrides


def test_ac2_an_expected_value_needs_a_citation_and_shapes_are_checked() -> None:
    cleaned = clean(_input())
    assert (cleaned.label, cleaned.accounts, cleaned.expected) == (
        "Net assets",
        ("3000",),
        D("16812400.00"),
    )
    with pytest.raises(CitationRequired):
        clean(_input(citation_ids=()))
    with pytest.raises(CheckInvalid):
        clean(_input(kind="balanced"))  # a balanced check takes no accounts or value
    with pytest.raises(CheckInvalid):
        clean(_input(kind="rollforward"))  # needs components, not a value
    with pytest.raises(CheckInvalid):
        clean(_input(accounts=()))
    balanced = clean(_input(kind="balanced", accounts=(), expected=None, citation_ids=()))
    assert balanced.citation_ids == ()


TB = TbSource({"1000": D("120000.00"), "1010": D("5.00"), "2000": D("-68600.00")}, None)


def test_ac4_tb_cells_read_the_trial_balance() -> None:
    values = formula(
        {
            "A1": '=TB("1000")',
            "A2": '=TB("1000:1099")',
            "A3": '=-TB("2000")',
            "A4": '=TB("1000","BOY")',
            "A5": '=TB("4000")',
            "A6": "=A1-A2",
        },
        TB,
    )
    assert values["A1"] == D("120000.00") and values["A2"] == D("120005.00")
    assert values["A3"] == D("68600.00") and values["A6"] == D("-5.00")
    assert values["A4"] == "#TB!" and values["A5"] == "#TB!"
    assert formula({"A1": '=TB("1000")'})["A1"] == "#TB!"


def test_ac4_a_new_trial_balance_version_changes_a_linked_papers_hash() -> None:
    # SPEC-308 cells: the main sheet, no typed value (A-04-T04 added both to the content).
    cells = [
        SimpleNamespace(
            cell_key="A1", raw='=TB("1000")', tickmarks=[], sheet_key="main", value=None
        )
    ]
    plain = [SimpleNamespace(cell_key="A1", raw="5", tickmarks=[], sheet_key="main", value=None)]
    tb_id = uuid4()
    v1 = TbLink(tb_id, "standard", None, 1, TB, [])  # type: ignore[arg-type]  # date unused
    v2 = TbLink(tb_id, "standard", None, 2, TB, [])  # type: ignore[arg-type]  # date unused
    assert content_hash(content_of(cells, [], v1)) != content_hash(content_of(cells, [], v2))  # type: ignore[arg-type]  # SimpleNamespace rows
    assert content_hash(content_of(plain, [], v1)) == content_hash(content_of(plain, [], v2))  # type: ignore[arg-type]  # SimpleNamespace rows


def test_spec311_tb_final_reads_the_adjusted_balance() -> None:
    tb = TbSource({"1000": D("10.00")}, None, {"1000": D("12.50")})
    assert formula({"A1": '=TB("1000","FINAL")'}, tb)["A1"] == D("12.50")
    assert formula({"A1": '=TB("1000","FINAL")'}, TB)["A1"] == "#TB!"  # no adjustment source
