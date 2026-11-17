"""A-08-T13 (TASK-8402; SPEC-657 F4; ADR P-57): the monetary-unit sampler "mus/1.0". The same
seed and version reproduce identical items, every item at or above the interval is selected, and
the existing sampler versions are untouched."""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus.modules.sampling.compute import (
    SAMPLER_VERSIONS,
    CanonicalPopulation,
    Record,
    canonical,
    mus,
)

D = Decimal
# 95% confidence: 3.00 for no errors, 4.75 for one (the step, 1.75, expands the expected).
F95 = mus.Factors(D("95"), D("3.00"), D("1.75"))


def _population() -> CanonicalPopulation:
    amounts = [D("410000.00"), D("12500.00"), D("0.00"), D("-800.00")] + [
        D(str(1000 + 37 * n)) for n in range(1, 400)
    ]
    return canonical(Record(f"C-{n:04d}", a) for n, a in enumerate(amounts))


def test_interval_from_tolerable_expected_and_factors() -> None:
    # (174,000 - 20,000 x 1.75) / 3.00 = 46,333.33
    assert mus.interval(D("174000"), D("20000"), F95) == D("46333.33")
    with pytest.raises(mus.MusInvalid):
        mus.interval(D("10000"), D("10000"), F95)  # nothing left under tolerable


def test_same_seed_and_version_reproduce_the_items() -> None:
    population = _population()
    one = mus.select(
        population, seed=0x3A91F2, tolerable=D("174000"), expected=D("20000"), factors=F95
    )
    two = mus.select(
        population, seed=0x3A91F2, tolerable=D("174000"), expected=D("20000"), factors=F95
    )
    assert one.items == two.items and one.items_hash == two.items_hash
    assert one.inputs_hash == two.inputs_hash and one.engine_version == "mus/1.0"
    other = mus.select(
        population, seed=0x000001, tolerable=D("174000"), expected=D("20000"), factors=F95
    )
    assert other.items_hash != one.items_hash


def test_every_item_at_or_above_the_interval_is_selected_with_certainty() -> None:
    population = _population()
    drawn = mus.select(population, seed=7, tolerable=D("174000"), expected=D("20000"), factors=F95)
    big = {
        r.key for r in population.records if r.amount is not None and r.amount >= drawn.interval
    }
    certain = {i.record_key for i in drawn.items if i.reason == "certainty"}
    assert big and big == certain
    # Zero and negative balances are outside the monetary population, never selected.
    assert drawn.excluded == 2
    chosen = {i.record_key for i in drawn.items}
    assert len(chosen) == len(drawn.items)  # each record at most once
    pps = [i for i in drawn.items if i.reason == "pps"]
    rest = drawn.monetary_total - sum(
        (
            r.amount
            for r in population.records
            if r.amount is not None and r.amount >= drawn.interval
        ),
        D(0),
    )
    assert abs(len(pps) - int(rest / drawn.interval)) <= 1


def test_existing_sampler_versions_are_untouched() -> None:
    assert set(SAMPLER_VERSIONS) == {"2.3"}
    assert mus.VERSION not in SAMPLER_VERSIONS
