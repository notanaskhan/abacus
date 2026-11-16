"""A-08-T12 (TASK-8086; SPEC-657 F1, F3, AC-1.1, AC-1.4; ADR P-57; DEC-5068): the JE test
service's pure parts and the frozen `je_score_selection` version."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from abacus.kernel.errors import DomainInvalid
from abacus.modules.ledger.api import Balance, GlEntry, GlSnapshotView, JournalEntry
from abacus.modules.sampling import je_tests as svc
from abacus.modules.sampling.compute import je_selection as sel


def _snapshot(*gaps: Decimal) -> GlSnapshotView:
    balances = tuple(
        Balance(f"{1000 + n}", "Cash", Decimal(0), Decimal(10), Decimal(0), Decimal(10),
                Decimal(10) - gap, False)
        for n, gap in enumerate(gaps)
    )  # fmt: skip
    return GlSnapshotView(
        uuid4(), uuid4(), date(2025, 7, 1), date(2026, 6, 30), "netsuite_gl_csv", "f" * 64,
        uuid4(), 10, Decimal(10), datetime(2026, 7, 15, tzinfo=UTC), balances,
    )  # fmt: skip


def _entry(ref: str | None, on: date, *codes: str) -> JournalEntry:
    lines = tuple(
        GlEntry(
            n, code, "", on, ref, "Journal", None, f"line {n}", Decimal(5 * n), Decimal(0), "x"
        )
        for n, code in enumerate(codes, start=1)
    )
    return JournalEntry(
        (on.isoformat(), "Journal", ref or "", ""), ref, on, lines,
        sum((x.debit for x in lines), Decimal(0)), None, None, None, None,
    )  # fmt: skip


def test_ac1_1_the_tie_reads_from_the_snapshot_balances() -> None:
    tied = svc.tie_of(_snapshot(Decimal(0), Decimal(0)))
    assert (tied.accounts_tied, tied.accounts_total, tied.difference, tied.result) == (
        2, 2, Decimal(0), "tie",
    )  # fmt: skip
    off = svc.tie_of(_snapshot(Decimal(0), Decimal("12.50")))
    assert (off.accounts_tied, off.result, off.difference) == (1, "difference", Decimal("12.50"))


def test_every_entry_reference_names_one_entry() -> None:
    on = date(2026, 6, 30)
    entries = [_entry("JE-1", on, "1000"), _entry("JE-1", on, "1000"), _entry(None, on, "1000")]
    assert svc.entry_refs(entries) == ["JE-1", "JE-1 #2", "JE 2026-06-30"]


def test_the_account_and_description_come_from_the_largest_debit_line() -> None:
    entry = _entry("JE-9", date(2026, 6, 30), "6100", "21500")
    engine = svc.to_engine(entry, "JE-9")
    assert engine.amount == Decimal(15)
    assert engine.descriptions == ("line 1", "line 2")


def test_post_close_takes_the_tests_date_and_overrides_win() -> None:
    policy = [("post_close", 20, {}), ("round_amount", 25, {"at_least": "10000", "unit": "5000"})]
    merged = svc.merged_criteria(policy, {"round_amount": {"unit": "1000"}}, date(2026, 8, 15))
    assert merged[0].params == {"through": "2026-08-15"}
    assert merged[1].params == {"at_least": "10000", "unit": "1000"}


def test_an_override_for_a_criterion_the_policy_lacks_is_refused() -> None:
    with pytest.raises(svc.CriteriaInvalid):
        svc.merged_criteria(
            [("keywords", 10, {"words": "bonus"})], {"post_close": {}}, date(2026, 8, 1)
        )


def test_a_parameter_the_engine_cannot_read_is_refused() -> None:
    with pytest.raises(svc.CriteriaInvalid):
        svc.merged_criteria([("round_amount", 10, {"unit": "lots"})], {}, date(2026, 8, 1))


def test_posting_users_match_whatever_their_case_or_spacing() -> None:
    assert svc.posting_user_key("  J. Okafor ") == svc.posting_user_key("j. okafor")
    assert len(svc.posting_user_key("x")) == 32


def test_the_cursor_round_trips_and_a_forged_one_is_refused() -> None:
    cursor = svc.encode_cursor(61, "JE-26-17994")
    assert svc.decode_cursor(cursor) == (61, "JE-26-17994")
    assert svc.decode_cursor(None) is None
    with pytest.raises(DomainInvalid):
        svc.decode_cursor("not a cursor!")


_SCORES = [sel.Scored(f"JE-{n:03d}", (n * 37) % 101) for n in range(120)]


def test_ac1_4_a_floor_and_a_count_cut_the_by_score_part() -> None:
    by_floor = sel.select(_SCORES, score_min=90, top_n=None, unpredictable_n=0, seed=1)
    assert all(p.score >= 90 for p in by_floor.picks)
    cut = sel.select(_SCORES, score_min=90, top_n=3, unpredictable_n=2, seed=1)
    assert (cut.by_score, cut.unpredictable) == (3, 2)
    assert [p.entry_ref for p in cut.picks[:3]] == [p.entry_ref for p in by_floor.picks[:3]]


def test_a_zero_score_is_never_a_by_score_pick() -> None:
    zeros = [sel.Scored(f"Z{n}", 0) for n in range(5)]
    picked = sel.select(zeros, score_min=0, top_n=None, unpredictable_n=2, seed=7)
    assert picked.by_score == 0 and picked.unpredictable == 2


@pytest.mark.parametrize(
    ("score_min", "top_n", "unpredictable_n", "seed"),
    [(None, None, 1, 1), (50, None, 500, 1), (50, None, 1, -1), (50, None, 1, 2**24)],
)
def test_parameters_the_version_cannot_draw_with_are_refused(
    score_min: int | None, top_n: int | None, unpredictable_n: int, seed: int
) -> None:
    with pytest.raises(sel.SelectionInvalid):
        sel.select(
            _SCORES, score_min=score_min, top_n=top_n, unpredictable_n=unpredictable_n, seed=seed
        )


@given(seed=st.integers(0, 2**24 - 1), extra=st.integers(0, 20))
def test_property_the_draw_is_a_function_of_its_inputs(seed: int, extra: int) -> None:
    first = sel.select(_SCORES, score_min=70, top_n=None, unpredictable_n=extra, seed=seed)
    shuffled = list(reversed(_SCORES))
    again = sel.select(shuffled, score_min=70, top_n=None, unpredictable_n=extra, seed=seed)
    assert first == again
    assert len({p.entry_ref for p in first.picks}) == len(first.picks)
