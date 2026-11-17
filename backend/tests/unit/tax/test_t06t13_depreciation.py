"""T-06-T13 (SPEC-702 AC-1, AC-2, AC-4, AC-6; DEC-77): E3 on Ridgeline's 2025 register (TXP-03
a, b, c) and property tests of crossfoot and footing."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from abacus.modules.tax.compute import depreciation as e3

D = Decimal
ZERO = D("0")
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
TB = {"1600": 15752000, "1650": 2625167, "5600": 733500}


def test_txp03a_ridgeline_2025_gives_733_500_and_2_625_167() -> None:
    reg = e3.register(RIDGELINE, 2025)
    assert reg.cost == 15752000
    assert (reg.prior, reg.current, reg.accumulated) == (1891667, 733500, 2625167)
    rows = {r.asset_id: r for r in reg.rows}
    assert [rows[k].prior for k in ("elm_building", "larimer_lofts", "bergen_street")] == [
        1073333,
        637500,
        180834,
    ]
    assert [rows[k].current for k in rows] == [160000, 180000, 140000, 9500, 180000, 64000]
    assert reg.crossfoots()
    assert e3.ties(reg, TB).tie


def test_txp03b_form_8825_by_property_foots_to_733_500() -> None:
    by_property = e3.register(RIDGELINE, 2025).by_property
    assert by_property == {"elm_street": 169500, "larimer": 360000, "bergen": 204000}
    assert sum(by_property.values()) == 733500


def test_txp03c_the_bonus_check_needs_a_cited_date_after_jan_19_2025() -> None:
    params = e3.parameters(2025)
    lot = RIDGELINE[4]
    undated = replace(lot, acquired_on=None)
    assert e3.bonus_check(undated, params) == "check"  # never inferred (INV-2)
    contracted = replace(undated, binding_contract_on=date(2025, 2, 3))
    assert e3.bonus_check(contracted, params) == "tie"
    early = replace(undated, binding_contract_on=date(2024, 12, 2))
    assert e3.bonus_rate(early, params) == D("40")
    assert e3.bonus_check(early, params) == "check"
    assert e3.bonus_check(RIDGELINE[3], params) == "tie"  # the roof takes no bonus
    assert e3.bonus_check(replace(RIDGELINE[3], bonus_pct=D("50")), params) == "not_eligible"
    assert e3.bonus_rate(RIDGELINE[0], params) == ZERO


def test_real_property_is_straight_line_mid_month_and_1250() -> None:
    with pytest.raises(ValueError, match="real property"):
        e3.Asset("x", "p", date(2025, 1, 1), D("100"), "39", "200DB", "HY")
    with pytest.raises(ValueError, match="mid-month"):
        e3.Asset("x", "p", date(2025, 1, 1), D("100"), "5", "200DB", "MM")
    assert e3.recapture_class("39") == "section_1250"
    assert e3.recapture_class("15") == "section_1245"


def test_the_mid_quarter_test_moves_fourth_quarter_heavy_years_to_mq() -> None:
    q4 = e3.Asset("a", "p", date(2025, 11, 1), D("60000"), "5", "200DB", "HY")
    q1 = e3.Asset("b", "p", date(2025, 2, 1), D("40000"), "5", "200DB", "HY")
    assert e3.mid_quarter_applies([q4, q1], 2025)
    assert not e3.mid_quarter_applies([q1], 2025)
    row = e3.year_row(q4, 2025, mid_quarter=True)
    assert row.current == D("60000") * D("0.4") * D("0.125")  # 200DB 5-yr, Q4 fraction


def test_200db_switches_to_straight_line_and_recovers_the_whole_basis() -> None:
    asset = e3.Asset("a", "p", date(2025, 1, 1), D("10000"), "5", "200DB", "HY")
    schedule = e3.regular_schedule(asset, "HY", D("10000"))
    # Rev. Proc. 87-57 table A-1: 20.00, 32.00, 19.20, 11.52, 11.52, 5.76
    assert [round(v, 2) for v in schedule] == [
        D("2000.00"), D("3200.00"), D("1920.00"), D("1152.00"), D("1152.00"), D("576.00"),
    ]  # fmt: skip
    assert sum(schedule) == D("10000")


def test_section_179_and_the_small_business_test_use_reviewed_parameters() -> None:
    p25 = e3.parameters(2025)
    assert e3.section_179_allowed(D("4100000"), D("2500000"), p25) == D("2400000")
    assert e3.small_business_exempt([D("29000000"), D("31000000"), D("32000000")], p25)
    with pytest.raises(e3.ParameterMissing):
        e3.section_179_allowed(D("0"), D("1"), e3.parameters(2027))
    with pytest.raises(e3.ParameterMissing):
        e3.parameters(2019)


CLASSES: tuple[e3.RecoveryClass, ...] = ("5", "7", "15", "27.5", "39")


@settings(max_examples=60, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.integers(min_value=1, max_value=5_000_000),
            st.sampled_from(CLASSES),
            st.dates(min_value=date(2015, 1, 1), max_value=date(2025, 12, 31)),
            st.sampled_from([D("0"), D("40"), D("100")]),
        ),
        min_size=1,
        max_size=8,
    )
)
def test_property_the_register_crossfoots_and_never_exceeds_cost(
    rows: list[tuple[int, e3.RecoveryClass, date, Decimal]],
) -> None:
    assets: list[e3.Asset] = []
    for i, (cost, cls, placed, bonus) in enumerate(rows):
        real = cls in e3.REAL_PROPERTY
        method: e3.Method = "SL" if real else "200DB"
        convention: e3.Convention = "MM" if real else "HY"
        asset = e3.Asset(f"a{i}", f"p{i % 3}", placed, D(cost), cls, method, convention)
        assets.append(asset if real else replace(asset, bonus_pct=bonus))
    reg = e3.register(assets, 2025)
    assert reg.crossfoots()
    for asset, row in zip(assets, reg.rows, strict=True):
        assert 0 <= row.accumulated <= int(asset.cost) + 1
    mq = e3.mid_quarter_applies(assets, 2025)
    exact = [e3.year_row(a, 2025, mid_quarter=mq) for a in assets]
    assert abs(sum((r.current for r in exact), ZERO) - reg.current) < 1


def test_edges_invalid_assets_empty_years_and_missing_parameters() -> None:
    with pytest.raises(ValueError, match="cost and"):
        e3.Asset("x", "p", date(2025, 1, 1), D("100"), "5", "200DB", "HY", section_179=D("101"))
    with pytest.raises(ValueError, match="percentage"):
        e3.Asset("x", "p", date(2025, 1, 1), D("100"), "5", "200DB", "HY", bonus_pct=D("101"))
    real = e3.Asset("r", "p", date(2025, 6, 1), D("100"), "39", "SL", "MM")
    assert not e3.mid_quarter_applies([real], 2025)  # no personal property placed
    assert e3.regular_schedule(real, "MM", ZERO) == []
    full = e3.Asset("f", "p", date(2025, 1, 1), D("500"), "7", "150DB", "HY", bonus_pct=D("100"))
    assert e3.year_row(full, 2025).current == D("500")
    assert e3.year_row(full, 2026).current == ZERO
    assert e3.small_business_exempt([], e3.parameters(2025))
    assert not e3.small_business_exempt([D("40000000")] * 3, e3.parameters(2025))
    with pytest.raises(e3.ParameterMissing):
        e3.small_business_exempt([D("1")], e3.parameters(2028))
    s179 = e3.Asset(
        "s", "p", date(2025, 3, 1), D("1000"), "5", "200DB", "HY", section_179=D("1000")
    )
    row = e3.year_row(s179, 2025)
    assert (row.current, row.section_179, row.accumulated) == (D("1000"), D("1000"), D("1000"))
    assert e3.bonus_check(s179, e3.parameters(2025)) == "tie"  # no bonus elected
    tb = {"1600": 1, "1650": 2, "5600": 3}
    assert not e3.ties(e3.register([s179], 2025), tb).tie
    assert e3.largest_remainder([D("0.5"), D("0.5"), D("0.5")]) == [
        1,
        1,
        0,
    ]  # 1.5 to 2; earlier rows first


def test_150db_15_year_matches_the_published_table() -> None:
    asset = e3.Asset("l", "p", date(2025, 1, 1), D("100000"), "15", "150DB", "HY")
    schedule = e3.regular_schedule(asset, "HY", D("100000"))
    # Rev. Proc. 87-57 table A-1, 15-year: 5.00, 9.50, 8.55, 7.70, 6.93, 6.23, 5.90 ...
    assert [round(v / 1000, 2) for v in schedule[:7]] == [
        D("5.00"), D("9.50"), D("8.55"), D("7.70"), D("6.93"), D("6.23"), D("5.90"),
    ]  # fmt: skip
    assert len(schedule) == 16 and sum(schedule) == D("100000")
