"""A-03-T04 (SPEC-580 AC-7 to AC-10; ADR-340): the sampler library, version 2.3."""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest

from abacus.modules.sampling import api
from abacus.modules.sampling.compute import (
    CURRENT,
    SAMPLER_VERSIONS,
    Record,
    StratumRule,
    attribute_size,
    canonical,
    normalise_key,
    project,
    project_ratio,
    sampler,
    udl,
    udl_percent,
)
from abacus.modules.sampling.compute.draw import SEED_MAX, Stream, partial_fisher_yates
from abacus.modules.sampling.compute.v2_3 import select

COMPUTE = Path(__file__).resolve().parents[3] / "src/abacus/modules/sampling/compute"
CENSUS = [Record(f"NW-{1000 + i}") for i in range(412)]


def _gl() -> list[Record]:
    # 24 at or above 50,000, 1,102 in [7,750, 50,000), 786 below: the AUD-11f strata shape.
    rows = [Record(f"T{i:04d}", Decimal(50_000 + i * 10)) for i in range(24)]
    rows += [Record(f"M{i:04d}", Decimal("7750.00") + i) for i in range(1102)]
    rows += [Record(f"L{i:04d}", Decimal(100 + i)) for i in range(786)]
    return rows


STRATA = (
    StratumRule(Decimal(50_000), None, "all"),
    StratumRule(Decimal(7_750), Decimal(50_000), "random", 16),
    StratumRule(None, Decimal(7_750), "none"),
)


def test_ac7_same_seed_population_and_version_give_byte_identical_items() -> None:
    first = select(canonical(CENSUS), "attribute_statistical", seed=0x5E2A91, size=25)
    again = select(canonical(reversed(CENSUS)), "attribute_statistical", seed=0x5E2A91, size=25)
    assert first == again
    assert first.items_hash == again.items_hash
    assert first.engine_version == "2.3"
    assert len(first.inputs_hash) == 64
    other = select(canonical(CENSUS), "attribute_statistical", seed=0x5E2A92, size=25)
    assert other.items_hash != first.items_hash
    assert other.inputs_hash != first.inputs_hash


def test_ac7_items_are_25_distinct_records_in_draw_order() -> None:
    selection = select(canonical(CENSUS), "attribute_statistical", seed=0x5E2A91, size=25)
    assert [item.position for item in selection.items] == list(range(1, 26))
    assert len({item.record_key for item in selection.items}) == 25
    assert all(item.reason == "random" for item in selection.items)


def test_ac8_the_designed_size_limits_and_projection() -> None:
    assert attribute_size(0.90, 0.10, 0) == 22
    assert udl_percent(0, 25, 0.90) == Decimal("8.8")
    assert udl_percent(2, 25, 0.90) == Decimal("19.9")
    assert project(2140, 25, 412) == Decimal("35267.20")
    assert Decimal("0.0879") < udl(0, 25, 0.90) < Decimal("0.0881")
    assert project_ratio(100, 1_000, 50_000) == Decimal("5000.00")


def test_ac8_refusals() -> None:
    for bad in ((0, 0.1, 0), (0.9, 0, 0), (0.9, 0.1, 0.1), (1, 0.1, 0)):
        with pytest.raises(ValueError):
            attribute_size(*bad)
    with pytest.raises(ValueError):
        udl(3, 2, 0.9)
    assert udl(5, 5, 0.9) == Decimal(1)
    with pytest.raises(ValueError):
        project(1, 0, 10)


_RNG_METHODS = {
    "random",
    "randrange",
    "randint",
    "randbytes",
    "choice",
    "choices",
    "sample",
    "shuffle",
    "uniform",
    "gauss",
    "normalvariate",
    "triangular",
    "betavariate",
    "expovariate",
    "seed",
    "getstate",
    "setstate",
    "SystemRandom",
    "binomialvariate",
}


def test_ac9_no_random_member_but_random_and_getrandbits_is_referenced() -> None:
    for path in sorted(COMPUTE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "random":
                raise AssertionError((path, "from random import ..."))
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name) and node.value.id == "random":
                    assert node.attr == "Random", (path, node.attr)
                assert node.attr not in _RNG_METHODS, (path, node.attr)


def test_ac9_the_registry_freezes_2_3() -> None:
    assert CURRENT == "2.3"
    version = sampler("2.3")
    assert version.frozen
    assert set(version.methods) == {
        "attribute_nonstatistical",
        "attribute_statistical",
        "threshold_random_stratified",
    }
    with pytest.raises(KeyError, match="unknown_sampler_version"):
        sampler("2.4")
    with pytest.raises(TypeError):
        SAMPLER_VERSIONS["9.9"] = version  # type: ignore[index]


def test_ac10_threshold_strata_take_all_above_sixteen_inside_and_none_below() -> None:
    selection = select(
        canonical(_gl()), "threshold_random_stratified", seed=0x7C31B4, strata=STRATA
    )
    counts = [s.population_count for s in selection.strata]
    assert counts == [24, 1102, 786]
    assert [s.selected_count for s in selection.strata] == [24, 16, 0]
    assert len(selection.items) == 40
    assert [i.reason for i in selection.items[:24]] == ["threshold"] * 24
    assert {i.stratum_position for i in selection.items[24:]} == {2}
    assert sum(s.population_amount for s in selection.strata) == canonical(_gl()).total


def test_ac10_strata_must_partition_and_carry_counts_only_when_random() -> None:
    population = canonical(_gl())
    gap = (StratumRule(Decimal(50_000), None, "all"), StratumRule(None, Decimal(7_000), "none"))
    with pytest.raises(ValueError, match="partition"):
        select(population, "threshold_random_stratified", seed=1, strata=gap)
    with pytest.raises(ValueError, match="random count"):
        select(
            population,
            "threshold_random_stratified",
            seed=1,
            strata=(StratumRule(None, None, "random"),),
        )
    with pytest.raises(ValueError):
        select(population, "attribute_statistical", seed=1, size=25, strata=STRATA)


def test_canonical_order_hash_and_refusals() -> None:
    a = canonical([Record("b"), Record(" A ")])
    assert [r.key for r in a.records] == [" A ", "b"]
    assert a.total is None
    assert canonical([Record("a"), Record("b")]).population_hash == a.population_hash
    assert normalise_key("\uff2e\uff37-1184 ") == "nw-1184"
    for bad in ([], [Record("a"), Record("A")], [Record("a", Decimal(1)), Record("b")]):
        with pytest.raises(ValueError):
            canonical(bad)


def test_seeds_are_24_bit_and_the_walk_is_bounded() -> None:
    Stream(0)
    Stream(SEED_MAX)
    for seed in (-1, SEED_MAX + 1):
        with pytest.raises(ValueError):
            Stream(seed)
    assert partial_fisher_yates(Stream(7), 5, 0) == []
    assert sorted(partial_fisher_yates(Stream(7), 5, 5)) == [0, 1, 2, 3, 4]
    with pytest.raises(ValueError):
        partial_fisher_yates(Stream(7), 5, 6)


def test_the_module_api_re_exports_the_compute_helpers() -> None:
    assert api.attribute_size is attribute_size
    assert api.udl is udl
    assert api.project is project
