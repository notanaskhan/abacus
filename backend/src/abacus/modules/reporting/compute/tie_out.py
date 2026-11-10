"""The tie-out engine (A-06-T25; A-06 F7; ADR-050): prove a version's figures, by code.

Each `formula` value foots to its terms and each `tb_linked` value ties to the current final TB
line. A figure that does not tie names its difference and, where one explains it, the recorded
entry the version does not reflect ("RJE-1 not reflected"). Pure: Decimal only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

ENGINE_VERSION: Final = "tie_out@1"
_ZERO: Final = Decimal(0)


@dataclass(frozen=True)
class Value:
    line_key: str
    label: str
    year: int
    value: Decimal
    source: str
    terms: tuple[str, ...] = ()
    accounts: tuple[str, ...] = ()
    entries: tuple[str, ...] = ()


@dataclass(frozen=True)
class EntryEffect:
    """A recorded entry's net effect on an account (debit minus credit)."""

    ref: str
    account: str
    amount: Decimal


@dataclass(frozen=True)
class Off:
    line_key: str
    label: str
    year: int
    value: Decimal
    expected: Decimal
    off_by: Decimal
    cause: str | None


@dataclass(frozen=True)
class TieOut:
    total: int
    tied: int
    off: tuple[Off, ...]
    inputs_hash: str


def _cause(value: Value, effects: Sequence[EntryEffect]) -> str | None:
    """The first recorded entry touching this line's accounts that the version does not reflect."""
    accounts = set(value.accounts)
    for effect in effects:
        if effect.account in accounts and effect.ref not in value.entries:
            return effect.ref
    return None


def tie_out(
    values: Sequence[Value],
    expected: Mapping[tuple[str, int], Decimal],
    effects: Sequence[EntryEffect],
) -> TieOut:
    """`expected` is the current final TB by (line key, year). A figure missing from it is off."""
    by_key = {(v.line_key, v.year): v.value for v in values}
    off: list[Off] = []
    for v in values:
        if v.source == "formula":
            target = sum((by_key.get((t, v.year), _ZERO) for t in v.terms), _ZERO)
        elif v.source == "tb_linked":
            target = expected.get((v.line_key, v.year), _ZERO)
        else:
            continue
        if v.value != target:
            cause = _cause(v, effects) if v.source == "tb_linked" else None
            off.append(Off(v.line_key, v.label, v.year, v.value, target, v.value - target, cause))
    counted = [v for v in values if v.source in ("formula", "tb_linked")]
    body = {
        "values": sorted(f"{v.line_key}:{v.year}:{v.value}" for v in counted),
        "expected": sorted(f"{k[0]}:{k[1]}:{a}" for k, a in expected.items()),
        "effects": sorted(f"{e.ref}:{e.account}:{e.amount}" for e in effects),
    }
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return TieOut(len(counted), len(counted) - len(off), tuple(off), digest)
