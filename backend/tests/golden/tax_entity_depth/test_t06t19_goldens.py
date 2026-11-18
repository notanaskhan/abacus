"""T-06-T19 (TASK-8630; ADR-078 independent author; DEC-5630): E3, E4, E8 and E9 against every
figure in `tax_entity_depth_figures.yaml`, plus properties that a seeded off-by-one breaks
(each engine's footing identity)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast

import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from abacus.modules.tax.compute import basis as e8
from abacus.modules.tax.compute import book_tax as e4
from abacus.modules.tax.compute import depreciation as e3
from abacus.modules.tax.compute import states as e9

D = Decimal
FIG = cast(
    "Mapping[str, Mapping[str, object]]",
    yaml.safe_load((Path(__file__).parent / "tax_entity_depth_figures.yaml").read_text()),
)
RIDGELINE = (
    e3.Asset("elm_building", "elm_street", date(2018, 4, 1), D("6240000"), "39", "SL", "MM"),
    e3.Asset("larimer_lofts", "larimer", date(2021, 6, 1), D("4950000"), "27.5", "SL", "MM"),
    e3.Asset("bergen_street", "bergen", date(2023, 9, 1), D("3850000"), "27.5", "SL", "MM"),
    e3.Asset("elm_roof", "elm_street", date(2025, 3, 10), D("468000"), "39", "SL", "MM"),
    e3.Asset("larimer_lot", "larimer", date(2025, 2, 14), D("180000"), "15", "150DB", "HY",
             bonus_pct=D("100"), acquired_on=date(2025, 2, 14)),
    e3.Asset("bergen_appliances", "bergen", date(2025, 8, 1), D("64000"), "5", "200DB", "HY",
             bonus_pct=D("100"), acquired_on=date(2025, 8, 1)),
)  # fmt: skip


def _d(v: object) -> Decimal:
    return D(str(v))


def _case(name: str) -> Mapping[str, object]:
    case = FIG[name]
    assert {"source", "screen", "state", "parameter_set"} <= set(case)
    return case


def test_e3_register() -> None:
    c = _case("e3_register")
    reg = e3.register(RIDGELINE, 2025)
    assert (reg.cost, reg.prior, reg.current, reg.accumulated) == tuple(
        _d(c[k]) for k in ("cost", "prior", "current", "accumulated")
    )


def test_e4_m3_and_m2() -> None:
    c = _case("e4_m3")
    rows = [
        e4.M3Row(str(r["item"]), _d(r["a"]), _d(r["b"]), _d(r["c"]), _d(r["d"]))
        for r in cast("Sequence[Mapping[str, object]]", c["rows"])
    ]
    assert e4.m3_requirement(_d(c["total_assets"])).required
    rec = e4.reconcile_m3(
        rows, part_i_line_11=_d(c["part_i_line_11"]), analysis_line_1=_d(c["analysis_line_1"])
    )
    assert (rec.permanent, rec.part_i_tie, rec.analysis_tie) == (_d(c["permanent"]), "tie", "tie")
    m = _case("e4_m2")
    drafted = e4.roll_m2(beginning=_d(m["beginning"]), net_income=_d(m["net_income"]),
                         schedule_l_line_21=_d(m["schedule_l_line_21"]))  # fmt: skip
    assert drafted.difference == _d(m["drafted_off"])
    fixed = e4.roll_m2(beginning=_d(m["beginning"]), net_income=_d(m["net_income"]),
                       other_increases=_d(m["fix_other_increase"]),
                       schedule_l_line_21=_d(m["schedule_l_line_21"]))  # fmt: skip
    assert fixed.tally == "tie"


def test_e8_basis() -> None:
    c = _case("e8_basis")
    partners = cast("Sequence[Mapping[str, object]]", c["partners"])
    shares = e8.liability_shares(
        _d(c["liabilities"]), {str(p["name"]): _d(p["profit_pct"]) for p in partners}
    )
    outside = inside = D("0")
    for p in partners:
        assert shares[str(p["name"])] == _d(p["share"])
        b = e8.partner_basis(str(p["name"]), tax_capital=_d(p["tax_capital"]),
                             s752_share=_d(p["share"]), outside=_d(p["outside"]))  # fmt: skip
        outside += b.outside
        inside += b.inside
    assert (outside, inside) == (_d(c["total_outside"]), _d(c["total_inside"]))
    prem = cast("Mapping[str, object]", c["premium"])
    assert e8.s743b_placeholder(_d(prem["paid"]), _d(prem["capital_acquired"])) == _d(
        prem["placeholder"]
    )
    assert outside - inside == _d(prem["placeholder"])


def test_e9_states() -> None:
    c = _case("e9_states")
    nums = {str(k): _d(v) for k, v in cast("Mapping[str, object]", c["numerators"]).items()}
    shares = {r.state: r.share for r in e9.apportion(nums, _d(c["base"]))}
    assert shares == {str(k): _d(v) for k, v in cast("Mapping[str, object]", c["shares"]).items()}
    weights = {str(k): _d(v) for k, v in cast("Mapping[str, object]", c["weights"]).items()}
    feld = D("0")
    for state, amount in cast("Mapping[str, object]", c["ptet"]).items():
        assert e9.ptet(nums[str(state)], e9.rate(2025, str(state))) == _d(amount)
        credits = e9.partner_credits(
            _d(amount), weights, half_up=cast("Sequence[str]", c["half_up"])
        )
        expected = cast("Mapping[str, Sequence[object]]", c["credits"])[str(state)]
        assert list(credits.values()) == [_d(v) for v in expected]
        feld += credits["Jonah Feld"]
    assert feld == _d(c["feld_total"])


# --- properties: an off-by-one in any engine breaks one of these --------------------------------

AMOUNTS = st.integers(min_value=0, max_value=50_000_000).map(D)
WEIGHTS = st.lists(st.integers(min_value=1, max_value=100).map(D), min_size=2, max_size=8)


@settings(max_examples=300, deadline=None)
@given(total=AMOUNTS, weights=WEIGHTS)
def test_e8_shares_always_foot(total: Decimal, weights: list[Decimal]) -> None:
    shares = e8.liability_shares(total, {str(i): w for i, w in enumerate(weights)})
    assert sum(shares.values()) == total


@settings(max_examples=300, deadline=None)
@given(total=AMOUNTS, weights=WEIGHTS, override=st.booleans())
def test_e9_credits_always_foot(total: Decimal, weights: list[Decimal], override: bool) -> None:
    named = {str(i): w for i, w in enumerate(weights)}
    credits = e9.partner_credits(total, named, half_up=["0"] if override else [])
    assert sum(credits.values()) == total


@settings(max_examples=300, deadline=None)
@given(a=AMOUNTS, b=AMOUNTS, c=AMOUNTS)
def test_e4_rows_reconcile_column_d(a: Decimal, b: Decimal, c: Decimal) -> None:
    row = e4.M3Row("x", a, b, -c, a + b - c)
    rec = e4.reconcile_m3([row], part_i_line_11=a, analysis_line_1=a + b - c)
    assert (rec.part_i_tie, rec.analysis_tie) == ("tie", "tie")
