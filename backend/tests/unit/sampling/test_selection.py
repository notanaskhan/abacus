"""SPEC-037 AC-1, AC-2 (TASK-077; ADR-117): the population ties to its ledger; each criterion
selects exactly its entries; the same inputs and seed always select the same entries."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from abacus.modules.ledger.api import GlEntry
from abacus.modules.sampling.api import (
    Parameters,
    build_population,
    manual_kinds_for,
    seeded_v1,
    select,
    tie_out,
)

YEAR_END = date(2025, 12, 31)  # a Wednesday


def _entry(
    n: int,
    *,
    on: date = date(2025, 6, 10),  # a Tuesday
    kind: str = "Invoice",
    ref: str | None = None,
    amount: str = "123.45",
    account: str = "4000",
    other: str = "1000",
    note: str = "sale",
) -> list[GlEntry]:
    """One balanced journal entry: two postings."""
    value = Decimal(amount)
    reference = ref or f"R{n}"
    return [
        GlEntry(2 * n, account, "", on, reference, kind, "Acme", note, value, Decimal(0), "r"),
        GlEntry(2 * n + 1, other, "", on, reference, kind, "Acme", note, Decimal(0), value, "r"),
    ]


def _params(**changes: object) -> Parameters:
    base = Parameters(
        threshold=Decimal(10_000),
        trivial=Decimal(100),
        year_end=YEAR_END,
        manual_kinds=manual_kinds_for("import_qbo_gl_csv"),
        rare_count=2,
        keywords=("adjust",),
        random_count=0,
        seed=7,
    )
    return Parameters(**{**base.__dict__, **changes})  # type: ignore[arg-type] -- a frozen copy


def _rules(postings: list[GlEntry], **changes: object) -> dict[str, tuple[str, ...]]:
    filler = [p for i in range(1, 6) for p in _entry(100 + i, account="4000", other="1000")]
    population = build_population([*postings, *filler])
    return {s.entry.key[2]: s.rules for s in select(population, _params(**changes))}


@pytest.mark.parametrize(
    ("entry", "rule"),
    [
        (_entry(1, ref="BIG", amount="10000.01"), "large"),
        (_entry(1, ref="RND", amount="2000"), "round"),
        (_entry(1, ref="YE", on=YEAR_END - timedelta(days=1)), "near_year_end"),
        (_entry(1, ref="MAN", kind="Journal Entry"), "manual"),
        (_entry(1, ref="RARE", account="9999"), "rare_account"),
        (_entry(1, ref="WKD", on=date(2025, 6, 14)), "weekend"),
        (_entry(1, ref="KW", note="Year-end adjust per CFO"), "keywords"),
    ],
)
def test_ac2_each_criterion_selects_its_entry(entry: list[GlEntry], rule: str) -> None:
    found = _rules(entry)
    assert found == {entry[0].reference: (rule,)}


def test_ac2_round_amounts_below_trivial_aren_t_selected() -> None:
    assert _rules(_entry(1, ref="SMALL", amount="200"), round_unit=Decimal(100), trivial=500) == {}


@pytest.mark.parametrize(
    "entry",
    [
        _entry(1, ref="WKD", on=date(2025, 6, 14), amount="99.99"),
        _entry(1, ref="KW", note="adjust", amount="99.99"),
        _entry(1, ref="MAN", kind="Journal Entry", amount="99.99"),
    ],
)
def test_ac2_criteria_apply_only_at_or_above_trivial(entry: list[GlEntry]) -> None:
    """Founder, 2026-10-19: the trivial floor keeps noisy rules testable."""
    assert _rules(entry) == {}


def test_ac2_large_entries_are_selected_whatever_the_floor() -> None:
    assert _rules(_entry(1, ref="BIG", amount="20000"), trivial=Decimal(50_000)) == {
        "BIG": ("large",)
    }


def test_ac2_an_entry_lists_every_rule_that_chose_it() -> None:
    entry = _entry(1, ref="ALL", amount="50000", kind="Journal Entry", note="manual adjust")
    assert _rules(entry) == {"ALL": ("large", "round", "manual", "keywords")}


def test_ac2_people_s_picks_join_with_their_reason() -> None:
    population = build_population(_entry(1, ref="P"))
    picks = {population.entries[0].key: "unusual vendor"}
    [chosen] = select(population, _params(rare_count=0), picks)
    assert (chosen.rules, chosen.reason) == (("picked",), "unusual vendor")


def test_ac2_a_pick_outside_the_population_is_refused() -> None:
    population = build_population(_entry(1))
    with pytest.raises(KeyError):
        select(population, _params(), {("2025-01-01", "", "nope", ""): "why"})


@given(
    count=st.integers(min_value=0, max_value=60),
    seed=st.integers(min_value=0, max_value=2**31),
    size=st.integers(min_value=0, max_value=80),
)
def test_ac2_the_random_draw_is_re_performable(count: int, seed: int, size: int) -> None:
    items = list(range(size))
    first = seeded_v1(items, count, seed)
    assert first == seeded_v1(items, count, seed)
    assert len(first) == min(count, size) == len(set(first))
    assert all(0 <= i < size for i in first)


def test_ac2_the_same_inputs_always_select_the_same_entries() -> None:
    postings = [p for n in range(200) for p in _entry(n, amount=f"{n + 1}.17")]
    population = build_population(postings)
    params = _params(random_count=15, seed=99)
    first = [s.entry.key for s in select(population, params)]
    assert first == [s.entry.key for s in select(population, params)]
    assert len(first) == 15
    other = [s.entry.key for s in select(population, _params(random_count=15, seed=100))]
    assert other != first


def test_ac1_the_population_ties_to_its_ledger() -> None:
    postings = [p for n in range(10) for p in _entry(n)]
    population = build_population(postings)
    assert len(population.entries) == 10
    total = sum((p.debit for p in postings), Decimal(0))
    assert tie_out(population, line_count=20, total_debit=total) is None
    assert tie_out(population, line_count=21, total_debit=total) == "line_count"
    assert tie_out(population, line_count=20, total_debit=total + 1) == "total_debit"


def test_d2_manual_types_depend_on_the_export_format() -> None:
    assert manual_kinds_for("import_xero_gl_xlsx") == frozenset({"manual journal"})
    assert "adjusting entry" in manual_kinds_for("import_qbo_gl_csv", ("Adjusting Entry",))
    assert manual_kinds_for("import_unknown") == frozenset()
