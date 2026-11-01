"""A-06-T07 (TASK-2917; A-06 §3 F4; SPEC-642 AC-6; DEC-1964): the SUM engine, by code.

Row acceptance: "The library is pure (no I/O or clock), returns 34,150 rollover and 22,250 iron
curtain for the Northwind inputs and emits engine_version and inputs_hash on every result."
Northwind's inputs are typed from A-06 §3 F4: PAJE-1 35,300 under both views and the carried
prior-year effects that take 1,150 off the rollover and 13,050 off the iron curtain; F-09's
4,210 is below CT 12,610.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus.modules.assurance.compute import sum as sum_engine

NORTHWIND = sum_engine.Thresholds(Decimal("252200"), Decimal("189150"), Decimal("12610"))
ITEMS = (
    sum_engine.Item("PAJE-1", Decimal("35300"), Decimal("35300")),
    sum_engine.Item("PY-1", Decimal("-1150"), Decimal("-13050"), prior_year=True),
    sum_engine.Item("BCT-1", Decimal("4210"), Decimal("4210"), below_ct=True),
)


def test_northwind_rollover_iron_curtain_and_the_bar() -> None:
    found = sum_engine.evaluate(ITEMS, NORTHWIND, column_set="ebp_net_assets")
    assert (found.rollover, found.iron_curtain, found.aggregate) == (
        Decimal("34150.00"),
        Decimal("22250.00"),
        Decimal("34150.00"),
    )
    assert (found.pct_of_pm, found.fill_pct_of_overall) == (Decimal("18.1"), Decimal("13.5"))
    assert (found.ct_tick_pct, found.pm_tick_pct) == (Decimal("5.0"), Decimal("75.0"))
    assert not found.approaching_pm and not found.above_pm
    assert found.below_ct == ("BCT-1",) and "BCT-1" not in found.accumulated
    assert (found.engine_name, found.engine_version) == ("sum", "1")
    assert len(found.inputs_hash) == 64


def test_the_illustrative_96_800_projection_approaches_pm() -> None:
    items = (*ITEMS[:2], sum_engine.Item("PAJE-2", Decimal("96800"), Decimal("96800")))
    found = sum_engine.evaluate(items, NORTHWIND, column_set="ebp_net_assets")
    assert found.approaching_pm and found.pct_of_pm >= Decimal(50)


def test_the_same_inputs_give_the_same_hash_and_order_matters_not_for_totals() -> None:
    a = sum_engine.evaluate(ITEMS, NORTHWIND, column_set="ebp_net_assets")
    b = sum_engine.evaluate(ITEMS, NORTHWIND, column_set="ebp_net_assets")
    assert a.inputs_hash == b.inputs_hash
    c = sum_engine.evaluate(tuple(reversed(ITEMS)), NORTHWIND, column_set="ebp_net_assets")
    assert (c.rollover, c.iron_curtain) == (a.rollover, a.iron_curtain)


def test_below_ct_and_invalid_inputs() -> None:
    assert sum_engine.classify_below_ct(Decimal("4210"), Decimal("12610"))
    assert not sum_engine.classify_below_ct(Decimal("12610"), Decimal("12610"))
    with pytest.raises(sum_engine.SumInvalid):
        sum_engine.evaluate(
            ITEMS,
            sum_engine.Thresholds(Decimal(0), Decimal(1), Decimal(0)),
            column_set="commercial",
        )
    with pytest.raises(sum_engine.SumInvalid):
        sum_engine.evaluate((ITEMS[0], ITEMS[0]), NORTHWIND, column_set="commercial")
