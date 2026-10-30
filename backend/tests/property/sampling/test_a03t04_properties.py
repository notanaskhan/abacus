"""A-03-T04 (SPEC-580 AC-7, AC-10): Hypothesis properties of sampler 2.3 and the size helpers."""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from abacus.modules.sampling.compute import Record, StratumRule, attribute_size, canonical
from abacus.modules.sampling.compute.draw import SEED_MAX
from abacus.modules.sampling.compute.v2_3 import select

_seeds = st.integers(min_value=0, max_value=SEED_MAX)


@settings(max_examples=150, deadline=None)
@given(n=st.integers(min_value=1, max_value=400), seed=_seeds, data=st.data())
def test_a_selection_is_a_subset_without_duplicates_and_repeats_exactly(
    n: int, seed: int, data: st.DataObject
) -> None:
    size = data.draw(st.integers(min_value=1, max_value=n))
    population = canonical(Record(f"K{i}") for i in range(n))
    first = select(population, "attribute_nonstatistical", seed=seed, size=size)
    ordinals = [item.ordinal for item in first.items]
    assert len(ordinals) == size == len(set(ordinals))
    assert all(0 <= o < n for o in ordinals)
    assert select(population, "attribute_nonstatistical", seed=seed, size=size) == first


@settings(max_examples=100, deadline=None)
@given(
    amounts=st.lists(st.integers(min_value=0, max_value=200_000), min_size=1, max_size=300),
    seed=_seeds,
    low=st.integers(min_value=1, max_value=100_000),
    span=st.integers(min_value=1, max_value=100_000),
)
def test_strata_partition_the_population(
    amounts: list[int], seed: int, low: int, span: int
) -> None:
    population = canonical(Record(f"R{i}", Decimal(a)) for i, a in enumerate(amounts))
    floor, top = Decimal(low), Decimal(low + span)
    middle = sum(1 for a in amounts if floor <= a < top)
    strata = (
        StratumRule(top, None, "all"),
        StratumRule(floor, top, "random", min(middle, 5)),
        StratumRule(None, floor, "none"),
    )
    selection = select(population, "threshold_random_stratified", seed=seed, strata=strata)
    assert sum(s.population_count for s in selection.strata) == len(amounts)
    assert sum(s.population_amount for s in selection.strata) == population.total
    assert selection.strata[0].selected_count == sum(1 for a in amounts if a >= top)
    assert selection.strata[2].selected_count == 0
    assert len({i.ordinal for i in selection.items}) == len(selection.items)


@settings(max_examples=60, deadline=None)
@given(
    confidence=st.sampled_from(["0.80", "0.85", "0.90", "0.95"]),
    tolerable=st.sampled_from(["0.05", "0.06", "0.08", "0.10", "0.15"]),
)
def test_size_is_monotonic_in_confidence_and_tolerable_rate(
    confidence: str, tolerable: str
) -> None:
    size = attribute_size(confidence, tolerable, 0)
    assert attribute_size(Decimal(confidence) + Decimal("0.04"), tolerable, 0) >= size
    assert attribute_size(confidence, Decimal(tolerable) + Decimal("0.02"), 0) <= size
