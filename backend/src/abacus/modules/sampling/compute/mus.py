"""Monetary-unit sampler, version "mus/1.0", frozen (A-08-T13; A-08 §3 F4; ADR P-57, ADR-340 §3;
DEC-5402).

A new sampler version beside 2.3, which is untouched. Once registered its behaviour never
changes; new behaviour ships as a new version.

- **Interval** J = (tolerable - expected * expansion factor) / reliability factor, in whole cents
  rounded down (a smaller interval only selects more). The reliability factor is the firm's
  `mus_confidence_factors` row for zero errors at the confidence; the expansion factor is the
  step to one error (the row for one error minus the row for zero), so a nil expectation needs no
  one-error row.
- **Certainty**: every record whose amount is at or above J is selected (reason `certainty`),
  in canonical order.
- **Systematic PPS** over the rest, in canonical order: a seeded random start s in [0, J) cents,
  then the hits s, s + J, s + 2J, … along the running total; each record containing a hit is
  selected once (reason `pps`).
- Records with no amount, or an amount at or below zero, are outside the monetary population
  (counted, never selected): an AR confirmation sample tests overstatement of balances.

Money is `Decimal` and cents are integers; the same seed, population and parameters give
byte-identical items (`items_hash`).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from typing import Final, Literal

from abacus.modules.sampling.compute.canonical import CanonicalPopulation, normalise_key
from abacus.modules.sampling.compute.draw import Stream

VERSION: Final = "mus/1.0"
METHOD: Final = "monetary_unit"
METHODS: Final[tuple[str, ...]] = (METHOD,)
Reason = Literal["certainty", "pps"]
_CENT: Final = Decimal("0.01")
_HUNDRED: Final = Decimal(100)


class MusInvalid(ValueError):
    """Parameters the sampler refuses (the draw fails with `parameters_invalid`)."""


@dataclass(frozen=True)
class Factors:
    """The firm's factors at one confidence (from `mus_confidence_factors`)."""

    confidence_pct: Decimal
    reliability: Decimal  # zero errors
    expansion: Decimal  # one error minus zero errors (0 without a one-error row)


@dataclass(frozen=True)
class Item:
    position: int  # 1-based draw order
    ordinal: int  # 0-based index in the canonical population
    record_key: str
    reason: Reason
    stratum_position: int | None = None


@dataclass(frozen=True)
class MusDraw:
    engine_version: str
    method: str
    seed: int
    population_hash: str
    inputs_hash: str
    interval: Decimal
    start: Decimal
    monetary_total: Decimal
    excluded: int
    certainty: int
    items: tuple[Item, ...]
    items_hash: str


def interval(tolerable: Decimal, expected: Decimal, factors: Factors) -> Decimal:
    """J in dollars, whole cents, rounded down."""
    if tolerable <= 0 or expected < 0 or factors.reliability <= 0 or factors.expansion < 0:
        raise MusInvalid("tolerable, expected and factors must be positive")
    room = tolerable - expected * factors.expansion
    if room <= 0:
        raise MusInvalid("expected misstatement leaves no room under tolerable")
    found = (room / factors.reliability).quantize(_CENT, rounding=ROUND_FLOOR)
    if found <= 0:
        raise MusInvalid("the interval is below one cent")
    return found


def expected_size(monetary_total: Decimal, j: Decimal) -> int:
    """The sample size a reader expects: the hits plus no more (certainty items count once)."""
    if j <= 0:
        raise MusInvalid("the interval must be positive")
    return int((monetary_total / j).to_integral_value(rounding=ROUND_FLOOR)) + 1


def inputs_hash(
    seed: int, population_hash: str, tolerable: Decimal, expected: Decimal, factors: Factors
) -> str:
    document = {
        "engine_version": VERSION,
        "method": METHOD,
        "seed": seed,
        "population_hash": population_hash,
        "tolerable": str(tolerable),
        "expected": str(expected),
        "confidence_pct": str(factors.confidence_pct),
        "reliability": str(factors.reliability),
        "expansion": str(factors.expansion),
    }
    return hashlib.sha256(json.dumps(document, sort_keys=True).encode("utf-8")).hexdigest()


def items_hash(items: Sequence[Item]) -> str:
    digest = hashlib.sha256()
    for item in items:
        line = [item.position, normalise_key(item.record_key), item.reason, item.stratum_position]
        digest.update(json.dumps(line, ensure_ascii=False).encode("utf-8") + b"\n")
    return digest.hexdigest()


def _cents(amount: Decimal) -> int:
    return int((amount * _HUNDRED).to_integral_value())


def select(
    population: CanonicalPopulation,
    *,
    seed: int,
    tolerable: Decimal,
    expected: Decimal,
    factors: Factors,
) -> MusDraw:
    """The items "mus/1.0" selects; the same inputs always give byte-identical output."""
    j = interval(tolerable, expected, factors)
    j_cents = _cents(j)
    records = population.records
    monetary: list[tuple[int, int]] = []  # (ordinal, cents) of the monetary population
    excluded = 0
    for ordinal, record in enumerate(records):
        if record.amount is None or record.amount <= 0:
            excluded += 1
            continue
        monetary.append((ordinal, _cents(record.amount)))
    stream = Stream(seed)
    start_cents = stream.below(j_cents)
    chosen: list[tuple[int, Reason]] = [(o, "certainty") for o, c in monetary if c >= j_cents]
    hit = start_cents
    running = 0
    for ordinal, cents in monetary:
        if cents >= j_cents:
            continue
        low, running = running, running + cents
        if low <= hit < running:
            chosen.append((ordinal, "pps"))
            while hit < running:
                hit += j_cents
    items = tuple(
        Item(position, ordinal, records[ordinal].key, reason)
        for position, (ordinal, reason) in enumerate(chosen, start=1)
    )
    total = sum((Decimal(c) for _, c in monetary), Decimal(0)) / _HUNDRED
    return MusDraw(
        engine_version=VERSION,
        method=METHOD,
        seed=seed,
        population_hash=population.population_hash,
        inputs_hash=inputs_hash(seed, population.population_hash, tolerable, expected, factors),
        interval=j,
        start=Decimal(start_cents) / _HUNDRED,
        monetary_total=total.quantize(_CENT),
        excluded=excluded,
        certainty=sum(1 for _, r in chosen if r == "certainty"),
        items=items,
        items_hash=items_hash(items),
    )
