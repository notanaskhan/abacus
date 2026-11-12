"""T-05-T15 (TASK-7306; SPEC-651 F6; TXP-05 a, a4, b; DEC-4306): E6 Schedule K and the K-1s against
T-05-T11's Ridgeline goldens.

Row acceptance: "Line 2 = 1,231,600, Pell Street Ventures box 2 = 400,270, Item K = 11,048,300, and
Σ K-1 = K on every line." The two periods' amounts for lines 5, 18a and 19a are test inputs (the
goldens give the year's totals only); Σ K-1 = K must hold whatever they are."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from abacus.modules.tax.compute.entity.allocation import segments
from abacus.modules.tax.compute.entity.schedule_k import (
    KLine,
    KPartner,
    ScheduleKInvalid,
    StateCell,
    schedule_k,
)

GOLDEN: dict[str, Any] = yaml.safe_load(  # Any: the YAML document
    (Path(__file__).parent / "ridgeline_ty2025.yaml").read_text(encoding="utf-8")
)
ALLOC = GOLDEN["allocation"]
K = GOLDEN["schedule_k"]["lines"]
D = Decimal


def _pcts(raw: dict[str, str]) -> dict[str, Decimal]:
    return {k: D(v) for k, v in raw.items()}


OPENING = _pcts(ALLOC["opening"])
AFTER = _pcts(ALLOC["after"])
KINDS = {
    "Ridgeline GP LLC": "llc",
    "Meera Shah": "individual",
    "Pell Street Ventures LLC": "llc",
    "Pell Street II LLC": "llc",
    "Jonah Feld": "individual",
}


def _partners() -> list[KPartner]:
    out: list[KPartner] = []
    for name, kind in KINDS.items():
        begin = OPENING.get(name, D(0))
        end = AFTER[name]
        out.append(KPartner(name, kind, (begin, begin, begin), (end, end, end)))  # type: ignore[arg-type]
    return out


def _segments() -> Any:  # noqa: ANN401 -- the engine's segment tuple
    start, end = (date.fromisoformat(d) for d in ALLOC["year"])
    return segments(
        start, end, [(None, OPENING), (date.fromisoformat(ALLOC["transfer"]), AFTER)], "monthly"
    )


def _half(total: str) -> tuple[Decimal, Decimal]:
    value = D(total)
    return (value / 2, value - value / 2)


def _lines() -> list[KLine]:
    return [
        KLine("2", D(K["line_2_net_rental"]), _half(K["line_2_net_rental"])),
        KLine("5", D(K["line_5_interest"]), _half(K["line_5_interest"])),
        KLine("18a", D(K["line_18a_tax_exempt"]), _half(K["line_18a_tax_exempt"])),
        KLine("19a", D(K["line_19a_distributions"]), _half(K["line_19a_distributions"])),
    ]


def _run(**extra: Any) -> Any:  # noqa: ANN401 -- the engine's result
    return schedule_k(
        _partners(),
        _segments(),
        _lines(),
        method="interim_closing",
        convention="monthly",
        liabilities={"nonrecourse": D(K["item_k_liabilities"])},
        **extra,
    )


def test_line_2_pell_street_box_2_item_k_and_k_equals_the_sum_of_the_k1s() -> None:
    result = _run()
    assert result.lines["2"] == D("1231600")
    pell = next(k for k in result.k1s if k.partner == "Pell Street Ventures LLC")
    crossfoot = GOLDEN["schedule_k"]["crossfoot"][0]
    assert str(pell.lines["2"]) == crossfoot["expect"]
    assert sum((k.item_k["nonrecourse"] for k in result.k1s), D(0)) == D("11048300")
    assert result.checks["k_equals_sum_of_k1s"] and result.checks["item_k_foots"]
    pell_ii = next(k for k in result.k1s if k.partner == "Pell Street II LLC")
    assert pell_ii.item_j["profit"] == (D(0), D(5))


def test_the_analysis_of_net_income_leaves_out_tax_exempt_income() -> None:
    result = _run()
    assert result.net_income == D("1231600") + D("18400")  # 18a and 19a are not in it
    assert result.checks["net_income_foots"]


def test_item_l_reads_off_6200_until_the_fix_then_ties() -> None:
    ending = GOLDEN["capital_m2"]["ending_after_fix"]
    names = list(KINDS)
    shares = [D(ending) - D(6200), D(0), D(0), D(0), D(0)]
    before = _run(
        ending_capital=dict(zip(names, shares, strict=True)), schedule_l_line_21=D(ending)
    )
    assert before.item_l["off"] == D(-6200) and not before.checks["item_l_ties"]
    after = _run(
        ending_capital=dict(zip(names, [D(ending), *shares[1:]], strict=True)),
        schedule_l_line_21=D(ending),
    )
    assert after.item_l["ties"] and after.checks["item_l_ties"]


def test_one_k1_per_partner_section_199a_statements_and_state_amounts_as_a_view() -> None:
    cells = [
        StateCell("IL", "Meera Shah", D(1000), "imported"),
        StateCell("IL", "Jonah Feld", D(500), "keyed"),
        StateCell("NY", "Jonah Feld", D(250), "keyed"),
    ]
    result = _run(state_cells=cells)
    assert result.k1_count == 5 and result.item_i == {"llc": 3, "individual": 2}
    assert all(k.section_199a_statement for k in result.k1s)  # line 2 is a trade or business line
    assert result.state_totals == {"IL": D(1500), "NY": D(250)}


def test_a_line_that_follows_actual_payments_must_foot() -> None:
    bad = KLine("19a", D(600000), by_partner={"Meera Shah": D(1)})
    with pytest.raises(ScheduleKInvalid) as refused:
        schedule_k(
            _partners(),
            _segments(),
            [bad],
            method="interim_closing",
            convention="monthly",
            liabilities={},
        )
    assert refused.value.code == "line_19a_does_not_foot"
