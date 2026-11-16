"""A-08-T11 (TASK-8089; ADR-078 goldens and properties; SPEC-657 F1, F3, F5, F6): the fieldwork
engines' goldens, each citing its screen and state, and the properties that hold for any input:
footing, determinism and seed reproducibility.

- JE scoring (AUD-12 a): Granite Peak's 142 · 38 · 61 · 17 · 9, 236 unique, 34 at 61 or more.
- Flux (AUD-13 a, AUD-26 a): Granite Peak 8 of 14 over (6 explained + 2 unexplained), interest
  26.8% within; Lakeshore only Grants.
- Confirmation coverage (AUD-14 a): $897,950.00 of $5,860,000.00 = 15.3%.
- Unreconciled (AUD-14 drawer, C3 Alpine Ridge): 286,900.00 - 4,300.00 = 282,600.00, a tie.
- MUS goldens land with the engine (A-08-T13, a later sprint).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from functools import cache

from hypothesis import given, settings
from hypothesis import strategies as st

from abacus.modules.assurance import fieldwork_fixtures as fx
from abacus.modules.assurance.compute.reconciliation import reconcile
from abacus.modules.assurance.confirmations_service import coverage_of
from abacus.modules.sampling.compute import je_scoring as js
from abacus.modules.sampling.compute import je_selection as sel
from abacus.modules.workpapers.compute.flux import FluxLine, Thresholds, evaluate
from abacus_tools.synthetic.scenarios.brightwater_hale import granite_peak_gl as g

D = Decimal


@cache
def _granite() -> js.Scored:
    return js.score(g.inputs(), g.je_entries(list(g.entries())))


# --- JE scoring ----------------------------------------------------------------------------------


def test_aud12_a_the_criteria_hit_exactly_and_foot_to_236() -> None:
    scored = _granite()
    assert [c.hit_count for c in scored.criteria] == [142, 38, 61, 17, 9]
    assert scored.unique_flagged == 236 == fx.unique_flagged(dict(fx.JE_CRITERIA_HITS))
    assert sum(1 for s in scored.scores if s.score >= 61) == 34


_entries = st.lists(
    st.builds(
        js.JeEntry,
        ref=st.uuids().map(lambda u: f"JE-{u.hex[:8]}"),
        posted_on=st.dates(date(2025, 7, 1), date(2026, 7, 31)),
        amount=st.decimals(min_value=D(0), max_value=D(2_000_000), places=2),
        descriptions=st.lists(
            st.sampled_from(["plug", "accrual", "adjust", "reclass entry"]), max_size=2
        ).map(tuple),
        posted_by=st.sampled_from([None, "a.lee", "r.vance"]),
        source=st.sampled_from([None, "manual", "system"]),
    ),
    max_size=40,
    unique_by=lambda e: e.ref,
)
_INPUTS = js.Inputs(
    criteria=(
        js.Criterion("weekend_holiday", 20),
        js.Criterion("round_amount", 35, {"at_least": "50000", "unit": "1000"}),
        js.Criterion("post_close", 30, {"through": "2026-07-15"}),
        js.Criterion("manual_by_role", 25, {"role_class": "senior_management"}),
        js.Criterion("keywords", 15, {"words": "plug, adjust"}),
    ),
    holidays=js.HolidaySet("us-federal@1", frozenset({date(2026, 7, 3)})),
    period_end=date(2026, 6, 30),
    roles={"r.vance": "senior_management"},
    fields_available=frozenset({"posted_by", "source"}),
)


@settings(max_examples=80, deadline=None)
@given(entries=_entries)
def test_property_scores_foot_and_are_deterministic(entries: list[js.JeEntry]) -> None:
    scored = js.score(_INPUTS, entries)
    assert scored.unique_flagged == sum(1 for s in scored.scores if s.score > 0)
    for s in scored.scores:
        assert bool(s.reason_codes) == (s.score > 0) and 0 <= s.score <= 100
    flagged_by = {c.key: c.hit_count for c in scored.criteria}
    assert scored.unique_flagged <= sum(flagged_by.values())
    again = js.score(_INPUTS, list(reversed(entries)))
    assert again.scores == scored.scores and again.inputs_hash == scored.inputs_hash


@settings(max_examples=60, deadline=None)
@given(entries=_entries, seed=st.integers(0, 2**24 - 1), extra=st.integers(0, 5))
def test_property_a_selection_is_reproducible_from_its_seed(
    entries: list[js.JeEntry], seed: int, extra: int
) -> None:
    scores = [sel.Scored(s.entry_ref, s.score) for s in js.score(_INPUTS, entries).scores]
    n = min(extra, len(scores))
    first = sel.select(scores, score_min=50, top_n=None, unpredictable_n=0, seed=seed)
    n = min(n, len(scores) - first.by_score)
    a = sel.select(scores, score_min=50, top_n=None, unpredictable_n=n, seed=seed)
    b = sel.select(list(reversed(scores)), score_min=50, top_n=None, unpredictable_n=n, seed=seed)
    assert a == b and len(a.picks) == a.by_score + a.unpredictable


# --- flux ----------------------------------------------------------------------------------------


def _granite_lines() -> list[FluxLine]:
    return [FluxLine(c, c, D(cy), D(py)) for c, cy, py, _ in fx.GRANITE_PEAK_LINES]


def test_aud13_a_granite_peak_8_of_14_over_6_explained_2_unexplained() -> None:
    result = evaluate(_granite_lines(), Thresholds(*fx.GRANITE_PEAK_THRESHOLD))
    assert (result.evaluated, result.over) == (14, 8)
    tallies = fx.tallies(fx.GRANITE_PEAK_LINES, fx.GRANITE_PEAK_THRESHOLD)
    assert (tallies.over_threshold, tallies.explained, tallies.unexplained) == (8, 6, 2)
    assert tallies.over_threshold == tallies.explained + tallies.unexplained
    interest = next(r for r in result.rows if r.key == "Interest expense")
    assert (interest.change_pct, interest.result) == (D("26.8"), "within")


def test_aud26_a_lakeshore_flags_only_grants() -> None:
    rows = [*fx.LAKESHORE_REVENUE, *fx.LAKESHORE_EXPENSES]
    result = evaluate(
        [FluxLine(c, c, D(cy), D(py)) for c, cy, py in rows], Thresholds(*fx.LAKESHORE_THRESHOLD)
    )
    assert [r.key for r in result.rows if r.result == "over"] == ["Grants"] == fx.lakeshore_over()


_money = st.integers(-5_000_000, 5_000_000).map(D)


@settings(max_examples=150, deadline=None)
@given(cy=_money, py=_money, pct=st.integers(1, 50), amount=st.integers(1, 500_000))
def test_property_a_line_is_over_only_on_both_legs(
    cy: Decimal, py: Decimal, pct: int, amount: int
) -> None:
    (row,) = evaluate([FluxLine("x", "x", cy, py)], Thresholds(D(pct), D(amount))).rows
    assert row.change == cy - py
    if row.result == "over":
        assert abs(row.change) >= amount
        assert row.change_pct is None or abs(row.change_pct) >= pct


# --- confirmations -------------------------------------------------------------------------------


def test_aud14_a_coverage_reads_15_3_percent() -> None:
    sent = sum(fx.AR_SENT, D("0.00"))
    line = coverage_of(
        fx.AR_POPULATION, sent, sum(fx.AR_CONFIRMED, D("0.00")), D("4300.00"), fx.CLEARLY_TRIVIAL
    )
    assert (line.sent_total, line.sent_pct) == (D("897950.00"), D("15.3"))
    assert line == fx.coverage()


@settings(max_examples=150, deadline=None)
@given(population=st.integers(1, 10**9), share=st.integers(0, 1000))
def test_property_coverage_is_a_bounded_share(population: int, share: int) -> None:
    sent = D(population) * share / 1000
    line = coverage_of(D(population), sent, D(0), D(0), D(0))
    assert D(0) <= line.sent_pct <= D(100)


def test_aud14_drawer_alpine_ridge_reconciles_to_a_tie_below_ct() -> None:
    done = reconcile(D("286900.00"), D("282600.00"), [D("-4300.00")], fx.CLEARLY_TRIVIAL)
    assert (done.unreconciled, done.ties, done.below_clearly_trivial) == (D("0.00"), True, True)
    open_ = reconcile(D("286900.00"), D("282600.00"), [], fx.CLEARLY_TRIVIAL)
    assert (open_.unreconciled, open_.ties, open_.below_clearly_trivial) == (
        D("4300.00"),
        False,
        True,
    )


_cents = st.integers(-(10**10), 10**10).map(lambda n: D(n) / 100)


@settings(max_examples=150, deadline=None)
@given(books=_cents, respondent=_cents, items=st.lists(_cents, max_size=6))
def test_property_unreconciled_foots(
    books: Decimal, respondent: Decimal, items: list[Decimal]
) -> None:
    done = reconcile(books, respondent, items)
    assert done.unreconciled + respondent == books + sum(items, D(0))
    assert done.ties == (done.unreconciled == 0)
    assert reconcile(books, respondent, list(reversed(items))) == done


def test_seed_reproducibility_holds_across_runs() -> None:
    assert (
        _granite().inputs_hash == js.score(g.inputs(), g.je_entries(list(g.entries()))).inputs_hash
    )
    assert _granite().criteria[0].hit_count == 142
    assert date(2026, 6, 30) == g.PERIOD_END and g.PERIOD_END + timedelta(days=15) == date(
        2026, 7, 15
    )
