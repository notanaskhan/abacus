"""A-08-T10 (TASK-8049; SPEC-657 AC-0.9, AC-1.2, AC-1.3; ADR-050; DEC-5034): JE scoring v1.

The pure functions reproduce the seed's hits (142 · 38 · 61 · 17 · 9 → 236 unique) on a synthetic
population built to them; every non-zero score carries at least one reason code; a criterion the
ledger cannot support is unavailable with its missing fields; the same inputs give the same scores
and hash. Written for 100% line and branch coverage of `je_scoring` (the row's acceptance).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from abacus.modules.sampling.compute import je_scoring as js

PERIOD_END = date(2026, 6, 30)
HOLIDAYS = js.HolidaySet("us_federal/2026.1", frozenset({date(2026, 7, 3), date(2026, 5, 25)}))
CRITERIA = (
    js.Criterion("weekend_holiday", 20),
    js.Criterion("round_amount", 25, {"at_least": "50000", "unit": "1000"}),
    js.Criterion("post_close", 30, {"through": "2026-07-15"}),
    js.Criterion("manual_by_role", 41, {"role_class": "senior_management"}),
    js.Criterion("keywords", 15, {"words": "plug, adjust"}),
)
ALL_FIELDS = frozenset({"posted_by", "entered_at", "source", "approver"})
ROLES: dict[str, js.RoleClass] = {"m.okonkwo": "senior_management", "c.hart": "accounting_staff"}
_WEEKDAY = date(2026, 6, 10)  # a Wednesday
_SATURDAY = date(2026, 6, 13)


def _entry(n: int, **kw: object) -> js.JeEntry:
    base: dict[str, object] = {
        "ref": f"JE-26-{n:05d}",
        "posted_on": _WEEKDAY,
        "amount": Decimal("1234.56"),
        "descriptions": ("Routine accrual",),
        "posted_by": "c.hart",
        "entered_at": datetime(2026, 6, 10, 9, 0),
        "source": "system",
    }
    base.update(kw)
    return js.JeEntry(**base)  # pyright: ignore[reportArgumentType] -- the test feeds a bad field on purpose


def _seed_population() -> list[js.JeEntry]:
    """Entries built to the seed's hit counts and overlaps (12 weekend+round, 10 post+manual,
    9 manual+keywords), 236 flagged of 300."""
    out: list[js.JeEntry] = []
    for n in range(1, 301):
        kw: dict[str, object] = {}
        if 1 <= n <= 142:
            kw["posted_on"] = date(2026, 5, 25) if n <= 4 else _SATURDAY
        if 131 <= n <= 168:
            kw["amount"] = Decimal("50000.00")
        if 169 <= n <= 229:
            kw["entered_at"] = datetime(2026, 7, 8, 16, 30)
        if 220 <= n <= 236:
            kw.update(posted_by="m.okonkwo", source="manual")
        if 228 <= n <= 236:
            kw["descriptions"] = ("Year-end plug to suspense",)
        out.append(_entry(n, **kw))
    return out


def _inputs(fields: frozenset[str] = ALL_FIELDS) -> js.Inputs:
    return js.Inputs(CRITERIA, HOLIDAYS, PERIOD_END, ROLES, fields)


def test_ac0_9_the_seed_hits_are_reproduced() -> None:
    scored = js.score(_inputs(), _seed_population())
    assert [c.hit_count for c in scored.criteria] == [142, 38, 61, 17, 9]
    assert scored.unique_flagged == 236
    assert all(c.available and c.missing_fields == () for c in scored.criteria)
    assert scored.engine_version == js.ENGINE_VERSION


def test_ac1_2_holiday_and_weekend_are_distinct_reasons() -> None:
    by_ref = {s.entry_ref: s for s in js.score(_inputs(), _seed_population()).scores}
    # Memorial Day, Mon May 25, 2026: in the period, so the holiday alone (a Jul 3 posting
    # would also be post-close).
    assert by_ref["JE-26-00001"].reason_codes == ("holiday",)
    assert by_ref["JE-26-00010"].reason_codes == ("weekend",)
    assert by_ref["JE-26-00135"].reason_codes == ("weekend", "round_amount")


def test_every_non_zero_score_carries_reasons_and_zero_carries_none() -> None:
    for s in js.score(_inputs(), _seed_population()).scores:
        assert (s.score > 0) == bool(s.reason_codes) == (s.criteria_mask != 0)


def test_scores_sum_weights_cap_at_100_and_order_deterministically() -> None:
    capped = js.Inputs(
        tuple(js.Criterion(c.key, 60, c.params) for c in CRITERIA),
        HOLIDAYS,
        PERIOD_END,
        ROLES,
        ALL_FIELDS,
    )
    top = js.score(capped, [_entry(1, posted_on=_SATURDAY, amount=Decimal(50000))]).scores[0]
    assert top.score == 100
    scored = js.score(_inputs(), _seed_population())
    keys = [(-s.score, s.entry_ref) for s in scored.scores]
    assert keys == sorted(keys)
    assert js.score(_inputs(), list(reversed(_seed_population()))) == scored


def test_ac1_3_a_ledger_without_the_fields_makes_criteria_unavailable() -> None:
    scored = js.score(_inputs(frozenset()), _seed_population())
    by_key = {c.key: c for c in scored.criteria}
    assert by_key["manual_by_role"].available is False
    assert by_key["manual_by_role"].missing_fields == ("posted_by", "source")
    # Post-close still reads posting dates; these entries were posted in June and only entered
    # late, which a ledger without entry times cannot show.
    assert by_key["post_close"].available is True
    assert by_key["manual_by_role"].hit_count == by_key["post_close"].hit_count == 0
    # 142 weekend/holiday, 26 more round (131-168 less the 12 overlapping), keywords 228-236
    assert scored.unique_flagged == 142 + 26 + 9


def test_the_hash_moves_with_the_holiday_set_and_the_entries() -> None:
    entries = _seed_population()
    first = js.inputs_hash(_inputs(), entries)
    other = js.Inputs(
        CRITERIA, js.HolidaySet("us_federal/2026.2", HOLIDAYS.dates), PERIOD_END, ROLES, ALL_FIELDS
    )
    assert js.inputs_hash(other, entries) != first
    assert js.inputs_hash(_inputs(), entries[:-1]) != first
    assert js.inputs_hash(_inputs(), list(reversed(entries))) == first


def test_select_by_score_takes_the_top_in_order() -> None:
    scored = js.score(_inputs(), _seed_population())
    chosen = js.select_by_score(scored, 61)
    assert chosen and all(s.score >= 61 for s in scored.scores if s.entry_ref in chosen)
    assert js.select_by_score(scored, 0) == tuple(
        s.entry_ref for s in scored.scores if s.score > 0
    )


def test_post_close_reads_the_posting_date_or_the_entry_time_inside_the_window() -> None:
    c = CRITERIA[2]
    inputs = _inputs()
    assert js.reasons_for(_entry(1, entered_at=None), c, inputs) == ()
    assert js.reasons_for(_entry(1, posted_on=date(2026, 7, 3), entered_at=None), c, inputs) == (
        "post_close",
    )
    assert js.reasons_for(_entry(1, posted_on=date(2026, 7, 16), entered_at=None), c, inputs) == ()
    late = _entry(1, entered_at=datetime(2026, 7, 1, 8))
    assert js.reasons_for(late, c, _inputs(frozenset())) == ()  # entry times not carried
    assert js.reasons_for(_entry(1, entered_at=datetime(2026, 7, 16, 8)), c, inputs) == ()
    assert js.reasons_for(_entry(1, entered_at=datetime(2026, 7, 1, 8)), c, inputs) == (
        "post_close",
    )


def test_manual_by_role_needs_a_manual_entry_by_a_listed_role() -> None:
    c = CRITERIA[3]
    inputs = _inputs()
    assert js.reasons_for(_entry(1, posted_by="m.okonkwo", source="system"), c, inputs) == ()
    assert js.reasons_for(_entry(1, posted_by="c.hart", source="manual"), c, inputs) == ()
    assert js.reasons_for(_entry(1, posted_by=None, source="manual"), c, inputs) == ()  # unknown
    assert js.reasons_for(_entry(1, posted_by="m.okonkwo", source="manual"), c, inputs) == (
        "manual_by_role",
    )


def test_round_amount_needs_the_floor_and_the_unit() -> None:
    c = CRITERIA[1]
    inputs = _inputs()
    assert js.reasons_for(_entry(1, amount=Decimal(49000)), c, inputs) == ()
    assert js.reasons_for(_entry(1, amount=Decimal("50500")), c, inputs) == ()
    zero_unit = js.Criterion("round_amount", 25, {"at_least": "0", "unit": "0"})
    assert js.reasons_for(_entry(1, amount=Decimal(50000)), zero_unit, inputs) == ()


def test_keywords_match_whole_words_and_an_empty_list_matches_nothing() -> None:
    c = CRITERIA[4]
    inputs = _inputs()
    assert js.reasons_for(_entry(1, descriptions=("Adjusting entry",)), c, inputs) == ()
    assert js.reasons_for(_entry(1, descriptions=("ADJUST cutoff",)), c, inputs) == ("keyword",)
    empty = js.Criterion("keywords", 15, {"words": " , "})
    assert js.reasons_for(_entry(1, descriptions=("plug",)), empty, inputs) == ()


@pytest.mark.parametrize(
    "criteria",
    [
        (js.Criterion("keywords", 15), js.Criterion("keywords", 10)),  # repeated
        (js.Criterion("keywords", 101),),  # weight out of range
    ],
)
def test_invalid_policies_are_refused(criteria: tuple[js.Criterion, ...]) -> None:
    with pytest.raises(js.InvalidCriteria):
        js.score(js.Inputs(criteria, HOLIDAYS, PERIOD_END), [_entry(1)])


@pytest.mark.parametrize(
    ("criterion", "name"),
    [
        (js.Criterion("round_amount", 25, {"at_least": "abc"}), "at_least"),
        (js.Criterion("round_amount", 25, {"unit": "-5"}), "unit"),
        (js.Criterion("post_close", 30, {}), "through"),
        (js.Criterion("post_close", 30, {"through": "July"}), "through"),
    ],
)
def test_bad_parameters_are_refused(criterion: js.Criterion, name: str) -> None:
    with pytest.raises(js.InvalidCriteria, match=name):
        js.reasons_for(_entry(1, entered_at=datetime(2026, 7, 1)), criterion, _inputs())


def test_an_unknown_key_is_refused() -> None:
    bad = js.Criterion("velocity", 10)  # pyright: ignore[reportArgumentType] -- an unknown kind on purpose
    with pytest.raises(js.InvalidCriteria):
        js.score(js.Inputs((bad,), HOLIDAYS, PERIOD_END), [_entry(1)])


@given(
    offset=st.integers(min_value=0, max_value=400),
    amount=st.decimals(
        min_value=0, max_value=10**7, places=2, allow_nan=False, allow_infinity=False
    ),
)
def test_property_score_and_reasons_agree(offset: int, amount: Decimal) -> None:
    entry = _entry(1, posted_on=date(2026, 1, 1) + timedelta(days=offset), amount=amount)
    s = js.score(_inputs(), [entry]).scores[0]
    assert 0 <= s.score <= 100
    assert (s.score > 0) == bool(s.reason_codes)
