"""T-05-T16 (TASK-7307; T-05 §4.4; DEC-4307): property tests for the entity engines (Hypothesis).

E1 (the TB pipeline), E5 (allocation by period and the targeted waterfall) and E6 (Schedule K):
every column foots, interests conserve to 100.000000%, every split foots to its whole, the same
inputs give the same `inputs_hash`, and Σ K-1 = K for random structures. Run in stage 2; the
nightly mutation job's `compute` scope covers `tax/compute/entity` (abacus_tools.quality.mutation).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from abacus.modules.tax.compute.entity.allocation import allocate_item, segments
from abacus.modules.tax.compute.entity.schedule_k import KLine, KPartner, schedule_k
from abacus.modules.tax.compute.entity.tb_pipeline import TbAccount, run
from abacus.modules.tax.compute.entity.waterfall import Rung, WaterfallPartner, run_waterfall

D = Decimal
SCALE = 10**6  # numeric(9,6): a percentage is an integer of millionths of a percent
YEAR_START, YEAR_END = date(2025, 1, 1), date(2025, 12, 31)


@st.composite
def interests(draw: st.DrawFn, keys: list[str]) -> dict[str, Decimal]:
    """Percentages with six places that sum to exactly 100.000000."""
    cuts = sorted(
        draw(st.lists(st.integers(0, 100 * SCALE), min_size=len(keys) - 1, max_size=len(keys) - 1))
    )
    bounds = [0, *cuts, 100 * SCALE]
    return {k: D(bounds[i + 1] - bounds[i]).scaleb(-6) for i, k in enumerate(keys)}


@st.composite
def structures(draw: st.DrawFn) -> tuple[list[str], list[tuple[date | None, dict[str, Decimal]]]]:
    keys = [f"p{i}" for i in range(draw(st.integers(1, 6)))]
    opening = draw(interests(keys))
    days = sorted(set(draw(st.lists(st.integers(0, 363), max_size=3))))
    after = [(YEAR_START + timedelta(days=d), draw(interests(keys))) for d in days]
    return keys, [(None, opening), *after]


@settings(max_examples=150, deadline=None)
@given(structure=structures(), total=st.integers(-(10**9), 10**9))
def test_e5_every_period_and_partner_split_foots_and_interests_conserve(
    structure: tuple[list[str], list[tuple[date | None, dict[str, Decimal]]]], total: int
) -> None:
    keys, entries = structure
    for _, pcts in entries:
        assert sum(pcts.values(), D(0)) == D(100)
    segs = segments(YEAR_START, YEAR_END, entries, "calendar_day")
    result = allocate_item(D(total), segs, method="proration", convention="calendar_day")
    assert sum(result.segment_amounts, D(0)) == D(total)
    for amount, shares in zip(result.segment_amounts, result.shares, strict=True):
        assert sum(shares.values(), D(0)) == amount
    assert sum(result.totals.values(), D(0)) == D(total)
    again = allocate_item(D(total), segs, method="proration", convention="calendar_day")
    assert again.stamp.inputs_hash == result.stamp.inputs_hash
    assert set(result.totals) <= set(keys)


@settings(max_examples=150, deadline=None)
@given(
    structure=structures(),
    totals=st.lists(st.integers(-(10**8), 10**8), min_size=1, max_size=5),
    liabilities=st.integers(0, 10**9),
)
def test_e6_k_equals_the_sum_of_the_k1s_on_every_line(
    structure: tuple[list[str], list[tuple[date | None, dict[str, Decimal]]]],
    totals: list[int],
    liabilities: int,
) -> None:
    keys, entries = structure
    segs = segments(YEAR_START, YEAR_END, entries, "calendar_day")
    begin, end = entries[0][1], entries[-1][1]
    partners = [
        KPartner(k, "individual", (begin[k],) * 3, (end[k],) * 3)  # type: ignore[arg-type]  # a JSON value or a test double
        for k in keys
    ]
    lines = [KLine(str(i + 1), D(t)) for i, t in enumerate(totals)]
    result = schedule_k(
        partners,
        segs,
        lines,
        method="proration",
        convention="calendar_day",
        liabilities={"recourse": D(liabilities)},
    )
    assert result.checks["k_equals_sum_of_k1s"] and result.checks["item_k_foots"]
    assert result.checks["net_income_foots"] and result.k1_count == len(keys)


@st.composite
def partnerships(draw: st.DrawFn) -> list[WaterfallPartner]:
    lps = draw(st.integers(1, 4))
    out = [WaterfallPartner("gp", "gp", D(draw(st.integers(0, 10**7))))]
    out += [WaterfallPartner(f"lp{i}", "lp", D(draw(st.integers(1, 10**8)))) for i in range(lps)]
    return out


@settings(max_examples=150, deadline=None)
@given(
    partners=partnerships(),
    income=st.integers(0, 10**8),
    rate=st.integers(0, 20),
    target=st.integers(1, 40),
    gp=st.integers(0, 50),
)
def test_e5_the_waterfall_foots_and_its_plugs_sum_to_the_income(
    partners: list[WaterfallPartner], income: int, rate: int, target: int, gp: int
) -> None:
    rungs = [
        Rung(1, "return_of_capital"),
        Rung(2, "preferred_return", {"rate": rate}),
        Rung(3, "catch_up", {"target": target}),
        Rung(4, "promote", {"gp": gp}),
    ]
    result = run_waterfall(partners, rungs, D(income))
    assert all(result.checks.values())
    assert sum(result.plugs.values(), D(0)) == D(income)
    assert result.distributable == sum((p.beginning_capital for p in partners), D(0)) + income
    assert run_waterfall(partners, rungs, D(income)).stamp == result.stamp


@st.composite
def balanced_tbs(draw: st.DrawFn) -> list[TbAccount]:
    """A balanced trial balance: income and assets offset by liabilities and equity."""
    assets = draw(st.lists(st.integers(0, 10**8), min_size=1, max_size=6))
    liabilities = draw(st.integers(0, sum(assets)))
    accounts = [
        TbAccount(f"1{i:03d}", f"Asset {i}", "assets", "L1", D(a)) for i, a in enumerate(assets)
    ]
    accounts.append(TbAccount("2000", "Liabilities", "liabilities", "L15", D(-liabilities)))
    beginning = sum(assets) - liabilities
    accounts.append(
        TbAccount("3000", "Capital", "equity", "L21", D(-beginning), capital_role="beginning")
    )
    return accounts


@settings(max_examples=150, deadline=None)
@given(tb=balanced_tbs())
def test_e1_every_column_foots_and_the_hash_is_idempotent(tb: list[TbAccount]) -> None:
    assume(sum(a.utb for a in tb) == 0)
    result = run(tb)
    assert all(t.ok for t in result.column_foots.values())
    assert run(tb).stamp.inputs_hash == result.stamp.inputs_hash
