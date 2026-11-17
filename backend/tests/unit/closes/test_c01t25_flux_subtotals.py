"""C-01-T25/T40 rest (S48; CLS-10 DV-a): code's subtotals over the set's own lines."""

from __future__ import annotations

import uuid
from decimal import Decimal as D

from abacus.modules.closes import flux
from abacus.modules.closes.contract_work import FluxLineOut


def _line(key: str, prior: str | None, current: str) -> FluxLineOut:
    return FluxLineOut(
        line_id=uuid.uuid4(),
        line_key=key,
        caption=key,
        prior=None if prior is None else D(prior),
        current=D(current),
        test="within" if prior is not None else "not_comparable",
        status="within_threshold",
    )


LINES = [
    _line("sales", "180000", "185000"),
    _line("cogs", "55870", "55260"),
    _line("payroll", "61330", "69000"),
    _line("rent", "31095", "32425"),
    _line("interest", "1000", "1000"),
]
SIDES: dict[str, flux.Side] = {
    "sales": "income",
    "cogs": "cogs",
    "payroll": "operating",
    "rent": "operating",
    "interest": "other",
}


def test_gross_profit_opex_and_net_income_foot_from_the_lines() -> None:
    found = {s.kind: s for s in flux.subtotals(LINES, SIDES)}
    gp = found["gross_profit"]
    assert (gp.prior, gp.current, gp.change) == (D("124130"), D("129740"), D("5610"))
    assert gp.after_line_key == "cogs"
    assert gp.change_pct == D("4.5")
    opex = found["total_operating_expenses"]
    assert (opex.prior, opex.current, opex.after_line_key) == (D("92425"), D("101425"), "rent")
    ni = found["net_income"]
    assert ni.current == D("185000") - D("55260") - D("69000") - D("32425") - D("1000")
    assert ni.after_line_key is None
    assert [s.caption for s in flux.subtotals(LINES, SIDES)] == [
        "Gross profit",
        "Total operating expenses",
        "Net income",
    ]


def test_a_missing_prior_leaves_the_subtotals_prior_empty() -> None:
    lines = [_line("sales", None, "100"), _line("cogs", "10", "20")]
    gp = next(s for s in flux.subtotals(lines, SIDES) if s.kind == "gross_profit")
    assert (gp.prior, gp.change, gp.change_pct, gp.current) == (None, None, None, D("80"))


def test_no_cost_of_goods_sold_means_no_gross_profit_row() -> None:
    kinds = [s.kind for s in flux.subtotals([_line("sales", "1", "2")], SIDES)]
    assert kinds == ["net_income"]
