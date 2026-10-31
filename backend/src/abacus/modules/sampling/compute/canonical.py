"""Canonical population order and hash (ADR-340 §2; A-03-T04; SPEC-580 AC-7).

Before any draw the population is ordered by its normalised record key, so the same records give
the same order whatever order a file or a query returned them in. The population hash is the
SHA-256 of the canonical rows: a re-performer who rebuilds the population checks it first.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise

from abacus.kernel.numeric import quantize_half_up


@dataclass(frozen=True)
class Record:
    """One population record as the sampler needs it: its key and, for monetary strata, amount."""

    key: str
    amount: Decimal | None = None


@dataclass(frozen=True)
class CanonicalPopulation:
    records: tuple[Record, ...]
    total: Decimal | None
    population_hash: str


def normalise_key(key: str) -> str:
    """NFKC, trimmed and case-folded: "nw-1184 " and "NW-1184" are one record key."""
    normal = unicodedata.normalize("NFKC", key).strip().casefold()
    if not normal:
        raise ValueError("a record key must not be blank")
    if any(unicodedata.category(ch) == "Cc" for ch in normal):
        raise ValueError("a record key must not hold control characters")
    return normal


def _amount_text(amount: Decimal | None) -> str | None:
    return None if amount is None else str(quantize_half_up(amount, 2))


def canonical(records: Iterable[Record]) -> CanonicalPopulation:
    """The records in canonical order (by normalised key), their total and the population hash.

    Refused: an empty population, two records whose keys normalise alike, and a mix of records
    with and without amounts (a population is monetary or it is not).
    """
    keyed = sorted(((normalise_key(r.key), r) for r in records), key=lambda pair: pair[0])
    if not keyed:
        raise ValueError("a population must hold at least one record")
    for (left, _), (right, _) in pairwise(keyed):
        if left == right:
            raise ValueError("two records share a normalised key")
    with_amount = {record.amount is not None for _, record in keyed}
    if len(with_amount) > 1:
        raise ValueError("either every record has an amount or none does")
    ordered = tuple(record for _, record in keyed)
    total = (
        sum((r.amount for r in ordered if r.amount is not None), Decimal(0))
        if True in with_amount
        else None
    )
    digest = hashlib.sha256()
    for key, record in keyed:
        line = json.dumps([key, _amount_text(record.amount)], ensure_ascii=False)
        digest.update(line.encode("utf-8") + b"\n")
    return CanonicalPopulation(ordered, total, digest.hexdigest())
