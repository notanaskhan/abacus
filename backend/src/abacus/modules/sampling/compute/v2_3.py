"""Sampler version 2.3, frozen (ADR-340 §3; A-03-T04; SPEC-580 AC-7, AC-10).

Once registered in `SAMPLER_VERSIONS` this file's behaviour never changes: the corpus test
`(seed, population_hash, version) → items_hash` under `backend/tests/golden/sampling/corpus/`
fails on any drift. New behaviour ships as a new version.

Methods:
- `attribute_nonstatistical`, `attribute_statistical`: `size` records uniformly without
  replacement from the canonical order (one partial Fisher-Yates walk).
- `threshold_random_stratified`: strata partition the population by amount (minimum inclusive,
  maximum exclusive); `all` takes every record in canonical order, `random` draws its count
  uniformly inside the stratum, `none` takes nothing. Threshold items come first in canonical
  order, then random items stratum by stratum in draw order, all from one stream.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

from abacus.modules.sampling.compute.canonical import CanonicalPopulation, normalise_key
from abacus.modules.sampling.compute.draw import Stream, partial_fisher_yates

VERSION: Final = "2.3"
Method = Literal[
    "attribute_nonstatistical", "attribute_statistical", "threshold_random_stratified"
]
METHODS: Final[tuple[Method, ...]] = (
    "attribute_nonstatistical",
    "attribute_statistical",
    "threshold_random_stratified",
)
TestRule = Literal["all", "random", "none"]
Reason = Literal["random", "threshold"]
_RANDOM: Final[Reason] = "random"
_THRESHOLD: Final[Reason] = "threshold"


@dataclass(frozen=True)
class StratumRule:
    min_amount: Decimal | None
    max_amount: Decimal | None
    test_rule: TestRule
    random_count: int | None = None


@dataclass(frozen=True)
class StratumResult:
    position: int
    min_amount: Decimal | None
    max_amount: Decimal | None
    test_rule: TestRule
    population_count: int
    population_amount: Decimal
    selected_count: int


@dataclass(frozen=True)
class Item:
    position: int  # 1-based draw order, the sample item's position
    ordinal: int  # 0-based index in the canonical population
    record_key: str
    reason: Reason
    stratum_position: int | None


@dataclass(frozen=True)
class SampleDraw:
    engine_version: str
    method: Method
    seed: int
    population_hash: str
    inputs_hash: str
    items: tuple[Item, ...]
    strata: tuple[StratumResult, ...]
    items_hash: str


def _text(amount: Decimal | None) -> str | None:
    return None if amount is None else str(amount)


def _inputs_hash(
    method: Method,
    seed: int,
    population_hash: str,
    size: int | None,
    strata: Sequence[StratumRule],
) -> str:
    document = {
        "engine_version": VERSION,
        "method": method,
        "seed": seed,
        "population_hash": population_hash,
        "size": size,
        "strata": [
            [_text(s.min_amount), _text(s.max_amount), s.test_rule, s.random_count] for s in strata
        ],
    }
    return hashlib.sha256(json.dumps(document, sort_keys=True).encode("utf-8")).hexdigest()


def items_hash(items: Sequence[Item]) -> str:
    """SHA-256 of the items in position order: what the corpus pins per version."""
    digest = hashlib.sha256()
    for item in items:
        line = [item.position, normalise_key(item.record_key), item.reason, item.stratum_position]
        digest.update(json.dumps(line, ensure_ascii=False).encode("utf-8") + b"\n")
    return digest.hexdigest()


def _within(amount: Decimal, rule: StratumRule) -> bool:
    above = rule.min_amount is None or amount >= rule.min_amount
    below = rule.max_amount is None or amount < rule.max_amount
    return above and below


def _check_strata(strata: Sequence[StratumRule]) -> None:
    if not strata:
        raise ValueError("a stratified draw needs strata")
    for rule in strata:
        low, high = rule.min_amount, rule.max_amount
        if low is not None and high is not None and low >= high:
            raise ValueError("a stratum's minimum must be below its maximum")
        if (rule.test_rule == "random") != (rule.random_count is not None):
            raise ValueError("a random stratum, and only one, carries a random count")
        if rule.random_count is not None and rule.random_count < 0:
            raise ValueError("a random count must not be negative")


def select(
    population: CanonicalPopulation,
    method: Method,
    *,
    seed: int,
    size: int | None = None,
    strata: Sequence[StratumRule] = (),
) -> SampleDraw:
    """The items version 2.3 selects; the same inputs always give byte-identical output."""
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}")
    stream = Stream(seed)
    records = population.records
    items: list[Item] = []
    results: list[StratumResult] = []
    if method == "threshold_random_stratified":
        if size is not None:
            raise ValueError("a stratified draw takes its size from its strata")
        _check_strata(strata)
        members: list[list[int]] = [[] for _ in strata]
        for ordinal, record in enumerate(records):
            if record.amount is None:
                raise ValueError("a stratified draw needs an amount on every record")
            homes = [i for i, rule in enumerate(strata) if _within(record.amount, rule)]
            if len(homes) != 1:
                raise ValueError("strata must partition the population")
            members[homes[0]].append(ordinal)
        chosen: list[tuple[int, Reason, int]] = []
        for i, rule in enumerate(strata):
            if rule.test_rule == "all":
                chosen.extend((ordinal, _THRESHOLD, i + 1) for ordinal in members[i])
        for i, rule in enumerate(strata):
            if rule.test_rule == "random":
                count = rule.random_count or 0
                picks = partial_fisher_yates(stream, len(members[i]), count)
                chosen.extend((members[i][pick], _RANDOM, i + 1) for pick in picks)
        for i, rule in enumerate(strata):
            amount = sum(
                (a for a in (records[o].amount for o in members[i]) if a is not None), Decimal(0)
            )
            selected = sum(1 for _, _, home in chosen if home == i + 1)
            results.append(
                StratumResult(
                    i + 1,
                    rule.min_amount,
                    rule.max_amount,
                    rule.test_rule,
                    len(members[i]),
                    amount,
                    selected,
                )
            )
        for position, (ordinal, reason, home) in enumerate(chosen, start=1):
            items.append(Item(position, ordinal, records[ordinal].key, reason, home))
    else:
        if strata:
            raise ValueError("an attribute draw takes no strata")
        if size is None or not 0 < size <= len(records):
            raise ValueError("an attribute draw needs a size between 1 and the population")
        for position, ordinal in enumerate(
            partial_fisher_yates(stream, len(records), size), start=1
        ):
            items.append(Item(position, ordinal, records[ordinal].key, "random", None))
    frozen = tuple(items)
    return SampleDraw(
        engine_version=VERSION,
        method=method,
        seed=seed,
        population_hash=population.population_hash,
        inputs_hash=_inputs_hash(method, seed, population.population_hash, size, strata),
        items=frozen,
        strata=tuple(results),
        items_hash=items_hash(frozen),
    )
