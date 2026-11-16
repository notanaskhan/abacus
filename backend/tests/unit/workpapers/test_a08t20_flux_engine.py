"""A-08-T20 (TASK-8085; A-08 F3; C-01 F7): the shared dual-threshold flux engine. Row acceptance:
"Granite Peak flags 8 of 14 with interest at 26.8% staying Within, and Lakeshore flags only Grants
at 10% and $50,000." The close's Copperleaf set (10% and $2,500) runs through the same engine."""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.workpapers.compute.flux import FluxLine, Thresholds, change_pct, evaluate

D = Decimal
GRANITE = [
    ("revenue", "Revenue", "48600000", "44900000"),
    ("cogs", "Cost of goods sold", "29160000", "26490000"),
    ("opex", "Operating expenses", "15820000", "14960000"),
    ("interest", "Interest expense", "520000", "410000"),
    ("cash", "Cash", "2140000", "2610000"),
    ("ar", "Accounts receivable, net", "5860000", "4720000"),
    ("inventory", "Inventory, net", "11420000", "9180000"),
    ("ppe", "PP&E, net", "6380000", "6050000"),
    ("other", "Other assets", "610000", "640000"),
    ("ap", "Accounts payable", "4180000", "3310000"),
    ("accrued", "Accrued liabilities", "1630000", "1540000"),
    ("revolver", "Revolver — Front Range Bank", "6500000", "4900000"),
    ("term", "Term loan", "3200000", "3800000"),
    ("equity", "Stockholders' equity", "10900000", "9650000"),
]
LAKESHORE = [
    ("contributions", "Contributions", "2840000", "2610000"),
    ("grants", "Grants", "1120000", "1480000"),
    ("other", "Other revenue", "214000", "198000"),
    ("program", "Program services", "3210000", "3050000"),
    ("mg", "Management and general", "486000", "471000"),
    ("fundraising", "Fundraising", "318000", "342000"),
]


def _lines(rows: list[tuple[str, str, str, str]]) -> list[FluxLine]:
    return [FluxLine(k, label, D(c), D(p)) for k, label, c, p in rows]


def test_ac_granite_peak_flags_8_of_14_and_interest_stays_within() -> None:
    result = evaluate(_lines(GRANITE), Thresholds(D("10"), D("116250")))
    assert (result.evaluated, result.over) == (14, 8)
    interest = next(r for r in result.rows if r.key == "interest")
    assert (interest.change_pct, interest.result) == (D("26.8"), "within")
    over = {r.key for r in result.rows if r.result == "over"}
    assert over == {"cogs", "cash", "ar", "inventory", "ap", "revolver", "term", "equity"}


def test_ac_lakeshore_flags_only_grants() -> None:
    result = evaluate(_lines(LAKESHORE), Thresholds(D("10"), D("50000")))
    assert [r.key for r in result.rows if r.result == "over"] == ["grants"]
    grants = next(r for r in result.rows if r.key == "grants")
    assert (grants.change, grants.change_pct) == (D("-360000"), D("-24.3"))


def test_copperleaf_through_the_same_engine() -> None:
    lines = [
        FluxLine("payroll", "Payroll", D("69030"), D("61360")),
        FluxLine("repairs", "Repairs", D("3200"), D("640")),
        FluxLine("marketing", "Marketing", D("5515"), D("3985")),
        FluxLine("cogs", "COGS", D("85690"), D("82000")),
    ]
    result = evaluate(lines, Thresholds(D("10"), D("2500")))
    assert {r.key for r in result.rows if r.result == "over"} == {"payroll", "repairs"}


def test_derived_lines_are_not_evaluated_and_must_foot() -> None:
    lines = [
        FluxLine("revenue", "Revenue", D("100"), D("50")),
        FluxLine("cogs", "COGS", D("-60"), D("-30")),
        FluxLine("gp", "Gross profit", D("40"), D("20"), derived_from=("revenue", "cogs")),
    ]
    result = evaluate(lines, Thresholds(D("10"), D("1")))
    gp = next(r for r in result.rows if r.key == "gp")
    assert gp.result is None and gp.derived and result.foots and result.evaluated == 2
    broken = evaluate(
        [
            *lines[:2],
            FluxLine("gp", "Gross profit", D("41"), D("20"), derived_from=("revenue", "cogs")),
        ],
        Thresholds(D("10"), D("1")),
    )
    assert not broken.foots


def test_zero_prior_uses_the_amount_leg_alone_and_the_hash_is_stable() -> None:
    assert change_pct(D("10"), D("0")) is None
    a = evaluate(_lines(LAKESHORE), Thresholds(D("10"), D("50000")))
    assert (
        a.inputs_hash == evaluate(_lines(LAKESHORE), Thresholds(D("10"), D("50000"))).inputs_hash
    )
