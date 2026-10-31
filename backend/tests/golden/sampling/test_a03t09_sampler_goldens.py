"""A-03-T09 (TASK-2610; A-03 §3 F1, §5.4; ADR-340; ADR-078 separate author): the sampler goldens
and the frozen corpus.

The row's acceptance: "The golden suite passes against T04 on both supported Python minors and
fails if any selection line in version 2.3 changes."

The YAML files are transcribed from the design (AUD-11 a and f, SHT-01 c, A-03 §3 F1), never from
the implementation. The two populations are built by inverse construction (A-03 §5.4): the
generators below place the designed participants and payments at the canonical ordinals the frozen
`2.3` algorithm draws for the designed seed, ordinals recorded once as constants here. The draw is
then run for real and must return the designed names and amounts in the designed order: a change
to any selection line moves the ordinals and the test fails. The corpus under `corpus/`
(protected, red) pins `(seed, population_hash, version) -> items_hash` for every case.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, cast

import pytest
import yaml

from abacus.modules.sampling.compute import (
    SAMPLER_VERSIONS,
    Record,
    StratumRule,
    attribute_size,
    canonical,
    projected_misstatement,
    sampler,
    udl_percent,
)
from abacus.modules.sampling.compute.v2_3 import SampleDraw

HERE: Final = Path(__file__).parent
Json = dict[str, Any]  # Any: YAML documents of mixed scalar types

# Inverse construction, recorded once from v2.3 (A-03 §5.4). Census v2: the canonical ordinal of
# each designed participant, in draw order (Alicia Brennan first). GL: the canonical ordinals of
# stratum 2's 16 random payments, in draw order (SURL-25 first); stratum 1 is ordinals 0-23.
CENSUS_ORDINALS: Final = (
    214, 165, 323, 327, 194, 159, 43, 390, 205, 57, 300, 255, 224,
    73, 311, 295, 160, 139, 144, 337, 240, 28, 52, 408, 153,
)  # fmt: skip
GL_RANDOM_ORDINALS: Final = (
    651, 520, 393, 403, 911, 885, 801, 519, 118, 983, 1010, 663, 966, 246, 1113, 774,
)  # fmt: skip
GL_STRATA: Final = (
    StratumRule(Decimal("50000.00"), None, "all"),
    StratumRule(Decimal("7750.00"), Decimal("50000.00"), "random", 16),
    StratumRule(None, Decimal("7750.00"), "none"),
)
GL_BIG, GL_MID, GL_LOW = 24, 1102, 786


def _load(name: str) -> Json:
    data: object = yaml.safe_load((HERE / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return cast(Json, data)


def _money(value: object) -> Decimal:
    assert isinstance(value, str), f"amounts are quoted text, not {type(value).__name__}"
    return Decimal(value)


# ---- the generators (synthetic; Brightwater Hale's fictional clients)


def northwind_census_v2() -> tuple[list[Record], dict[str, str]]:
    """412 census rows keyed by their census row ("NWC-0001" ...), and the record keys of the 25
    designed participants mapped to their names. Canonical order is the row key's."""
    golden = _load("northwind_participants.yaml")
    keys = [f"NWC-{n:04d}" for n in range(1, 413)]
    names = {
        keys[ordinal]: str(item["name"])
        for ordinal, item in zip(CENSUS_ORDINALS, golden["items"], strict=True)
    }
    return [Record(key) for key in keys], names


def _spread(count: int, target: Decimal, width: int, step: int) -> list[Decimal]:
    """`count` whole-dollar amounts that sum to exactly `target`: the mean, varied by +d and -d in
    pairs (so every amount stays within `width` of the mean), the remainder on the last."""
    mean, rest = divmod(int(target), count)
    amounts: list[Decimal] = []
    for n in range(count):
        d = (n // 2 * step) % (width + 1)
        amounts.append(Decimal(mean + (d if n % 2 == 0 else -d)))
    if count % 2 == 1:
        amounts[-1] = Decimal(mean)
    amounts[-1] += rest
    return amounts


def granite_peak_disbursements() -> tuple[list[Record], dict[str, int]]:
    """1,912 payments keyed "GP-AP-00001" ... in canonical order: ordinals 0-23 are SURL-01 to 24
    (>= $50,000), 24-1125 the $7,750-$49,999 stratum with SURL-25 to 40 at the drawn ordinals,
    1126-1911 the payments under $7,750; the whole foots to $38,640,200.00."""
    golden = _load("granite_peak_disbursements.yaml")
    items = golden["items"]
    surl = [_money(i["amount"]) for i in items]
    low = _spread(GL_LOW, Decimal("2358000"), 500, 53)
    big_total = sum(surl[:GL_BIG], Decimal(0))
    mid_total = _money(golden["population"]["total"]) - big_total - sum(low, Decimal(0))
    random_at = dict(zip(GL_RANDOM_ORDINALS, surl[GL_BIG:], strict=True))
    fillers = _spread(GL_MID - len(random_at), mid_total - sum(surl[GL_BIG:]), 10000, 97)
    amounts = list(surl[:GL_BIG])
    filler = iter(fillers)
    for ordinal in range(GL_BIG, GL_BIG + GL_MID):
        amounts.append(random_at[ordinal] if ordinal in random_at else next(filler))
    amounts += low
    keys = [f"GP-AP-{n:05d}" for n in range(1, len(amounts) + 1)]
    position = {keys[o]: n for n, o in enumerate(range(GL_BIG), start=1)}
    position |= {keys[o]: GL_BIG + n for n, o in enumerate(GL_RANDOM_ORDINALS, start=1)}
    return [Record(k, a) for k, a in zip(keys, amounts, strict=True)], position


def _draw(case: Json) -> SampleDraw:
    """The case's population drawn by its version's frozen function."""
    version = sampler(str(case["version"]))
    if case["generator"] == "northwind_census_v2":
        records, _ = northwind_census_v2()
    elif case["generator"] == "granite_peak_disbursements":
        records, _ = granite_peak_disbursements()
    else:
        records = _plain(int(case["records"]))
    population = canonical(records)
    if case["method"] == "threshold_random_stratified":
        return version.select(population, case["method"], seed=int(case["seed"]), strata=GL_STRATA)
    return version.select(
        population, case["method"], seed=int(case["seed"]), size=int(case["size"])
    )


def _plain(count: int) -> list[Record]:
    return [Record(f"R-{n:05d}") for n in range(1, count + 1)]


# ---- AC: the 25 Northwind participants


def test_ac1_seed_0x5e2a91_draws_the_25_designed_participants_in_order() -> None:
    golden = _load("northwind_participants.yaml")
    records, names = northwind_census_v2()
    assert golden["seed"] == 0x5E2A91 == int(golden["seed_hex"], 16)
    draw = sampler(golden["engine_version"]).select(
        canonical(records), golden["method"], seed=golden["seed"], size=golden["size"]
    )
    assert draw.engine_version == "2.3"
    assert len(draw.items) == golden["size"] == 25
    assert [names.get(i.record_key) for i in draw.items] == [i["name"] for i in golden["items"]]
    assert [i.position for i in draw.items] == list(range(1, 26))
    assert draw.items[0].reason == "random"


def test_ac1_the_census_order_is_canonical_whatever_order_the_file_arrives_in() -> None:
    golden = _load("northwind_participants.yaml")
    records, names = northwind_census_v2()
    forward = sampler("2.3").select(
        canonical(records), golden["method"], seed=golden["seed"], size=25
    )
    backward = sampler("2.3").select(
        canonical(reversed(records)), golden["method"], seed=golden["seed"], size=25
    )
    assert forward.items_hash == backward.items_hash
    assert names[backward.items[0].record_key] == "Alicia Brennan"


# ---- AC: the Granite Peak stratified sample


def test_ac2_seed_0x7c31b4_draws_24_plus_16_payments_totalling_3698700() -> None:
    golden = _load("granite_peak_disbursements.yaml")
    records, position = granite_peak_disbursements()
    population = canonical(records)
    assert len(population.records) == golden["population"]["records"] == 1912
    assert population.total == _money(golden["population"]["total"])
    draw = sampler(golden["engine_version"]).select(
        population, golden["method"], seed=golden["seed"], strata=GL_STRATA
    )
    amount = {r.key: r.amount for r in records}
    expected = golden["items"]
    assert len(draw.items) == golden["items_total"] == 40
    assert [position.get(i.record_key) for i in draw.items] == [i["position"] for i in expected]
    assert [amount[i.record_key] for i in draw.items] == [_money(i["amount"]) for i in expected]
    total = sum((amount[i.record_key] or Decimal(0) for i in draw.items), Decimal(0))
    assert total == _money(golden["items_amount"])
    for stratum, want in zip(draw.strata, golden["strata"], strict=True):
        assert (stratum.population_count, stratum.selected_count) == (
            want["population_count"],
            want["selected_count"],
        )
        drawn = [
            amount[i.record_key] for i in draw.items if i.stratum_position == stratum.position
        ]
        assert sum((a or Decimal(0) for a in drawn), Decimal(0)) == _money(want["items_amount"])


def test_ac2_the_value_share_renders_9_6_percent() -> None:
    golden = _load("granite_peak_disbursements.yaml")
    share = (
        _money(golden["items_amount"]) / _money(golden["population"]["total"]) * 100
    ).quantize(Decimal("0.1"))
    assert str(share) == golden["value_share_percent"] == "9.6"


def test_ac2_the_strata_foot_24_plus_16_and_3286400_plus_412300() -> None:
    golden = _load("granite_peak_disbursements.yaml")
    strata = golden["strata"]
    assert sum(s["selected_count"] for s in strata) == golden["items_total"]
    assert sum((_money(s["items_amount"]) for s in strata), Decimal(0)) == _money(
        golden["items_amount"]
    )
    assert sum(s["population_count"] for s in strata) == golden["population"]["records"]


# ---- AC: size, UDL and projection


def test_ac3_attribute_size_udl_and_projection_match_the_design() -> None:
    golden = _load("statistics.yaml")
    for case in golden["attribute_size"]:
        size = attribute_size(
            Decimal(case["confidence"]),
            Decimal(case["tolerable_rate"]),
            Decimal(case["expected_rate"]),
        )
        assert size == case["size"] == 22
    for case in golden["udl_percent"]:
        got = udl_percent(case["deviations"], case["size"], Decimal(case["confidence"]))
        assert got == Decimal(case["percent"])
    for case in golden["projection"]:
        got = projected_misstatement(
            Decimal(case["misstatement"]), case["sample_count"], case["population_count"]
        )
        assert got == Decimal(case["projected"]) == Decimal("35267.20")


def test_ac3_qa3_is_settled_the_golden_pins_the_computed_value_not_the_display() -> None:
    qa3 = _load("statistics.yaml")["qa3"]
    assert qa3["computed"] == "35267.20"
    assert qa3["design_display"] == "$35,300"
    assert qa3["decision"] == "DEC-1659"
    assert projected_misstatement(Decimal("2140"), 25, 412) != Decimal("35300")


# ---- the frozen corpus

CORPUS: Final = yaml.safe_load((HERE / "corpus" / "v2.3.yaml").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CORPUS["entries"], ids=lambda c: str(c["case"]))
def test_corpus_seed_population_and_version_give_the_pinned_items_hash(case: Json) -> None:
    assert case["version"] in SAMPLER_VERSIONS
    draw = _draw(case)
    assert draw.population_hash == case["population_hash"]
    assert draw.seed == int(case["seed"])
    assert draw.items_hash == case["items_hash"]


def test_corpus_covers_both_goldens_and_every_method() -> None:
    entries: list[Json] = CORPUS["entries"]
    assert {e["generator"] for e in entries} >= {
        "northwind_census_v2",
        "granite_peak_disbursements",
    }
    assert {e["method"] for e in entries} >= {
        "attribute_statistical",
        "threshold_random_stratified",
    }
    assert all(e["version"] == "2.3" for e in entries)


def test_a_changed_selection_line_would_fail_the_golden() -> None:
    """Red-when-broken: draw the census with a neighbouring seed (what a one-line change to the
    walk or the stream does to the ordinals) and the designed names no longer come out."""
    golden = _load("northwind_participants.yaml")
    records, names = northwind_census_v2()
    moved: Callable[[int], list[str | None]] = lambda seed: [  # noqa: E731
        names.get(i.record_key)
        for i in sampler("2.3")
        .select(canonical(records), golden["method"], seed=seed, size=25)
        .items
    ]
    designed = [i["name"] for i in golden["items"]]
    assert moved(0x5E2A91) == designed
    assert moved(0x5E2A92) != designed
