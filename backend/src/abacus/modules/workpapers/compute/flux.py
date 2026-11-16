"""The shared dual-threshold flux engine (A-08-T20; A-08 F3; C-01 F7; KNW-04; ADR-050). Pure.

One engine for assurance's preliminary analytics (AUD-13), SSARS analytics (AUD-26) and the close's
flux (CLS-10), so a threshold means the same thing everywhere:

- A line is **over** only when both legs are met on the absolute change: |Δ%| ≥ the percentage
  threshold **and** |Δ$| ≥ the amount threshold. Either leg alone is **within** (Granite Peak's
  interest moves 26.8% but only $110,000 against $116,250: within).
- **Derived lines** (subtotals such as gross profit) are computed from their parts and never
  evaluated on their own; the engine checks each derived line foots to its parts.
- The change is current − prior; the percentage is change over |prior| to one decimal place,
  half-up (none when the prior is zero: the amount leg alone decides).

Money is `Decimal`; no I/O, no clock; `ENGINE_VERSION` and `inputs_hash` make a set reproducible.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal

ENGINE_VERSION: Final = "flux/1.0.0"
_TENTH: Final = Decimal("0.1")

Result = Literal["over", "within"]


@dataclass(frozen=True, slots=True)
class FluxLine:
    key: str
    label: str
    current: Decimal
    prior: Decimal
    derived_from: tuple[str, ...] = ()  # a subtotal: the keys it adds up (never evaluated)


@dataclass(frozen=True, slots=True)
class Thresholds:
    pct: Decimal  # percent, e.g. 10
    amount: Decimal  # dollars, e.g. 116,250 (or 2,500 for a close)


@dataclass(frozen=True, slots=True)
class FluxRow:
    key: str
    label: str
    current: Decimal
    prior: Decimal
    change: Decimal
    change_pct: Decimal | None
    result: Result | None  # None for a derived line (not evaluated)
    derived: bool
    foots: bool  # a derived line equals the sum of its parts; True for detail lines


@dataclass(frozen=True, slots=True)
class FluxSet:
    rows: tuple[FluxRow, ...]
    evaluated: int
    over: int
    within: int
    foots: bool
    engine_version: str
    inputs_hash: str


def change_pct(current: Decimal, prior: Decimal) -> Decimal | None:
    if prior == 0:
        return None
    return ((current - prior) * 100 / abs(prior)).quantize(_TENTH, rounding=ROUND_HALF_UP)


def classify(change: Decimal, pct: Decimal | None, thresholds: Thresholds) -> Result:
    """Both legs, on the absolute change (KNW-04's dual rule)."""
    amount_leg = abs(change) >= thresholds.amount
    pct_leg = pct is None or abs(pct) >= thresholds.pct
    return "over" if amount_leg and pct_leg else "within"


def _hash(lines: Sequence[FluxLine], thresholds: Thresholds) -> str:
    payload = json.dumps(
        {"lines": [asdict(x) for x in lines], "t": asdict(thresholds)}, sort_keys=True, default=str
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def evaluate(lines: Sequence[FluxLine], thresholds: Thresholds) -> FluxSet:
    by_key = {x.key: x for x in lines}
    rows: list[FluxRow] = []
    for line in lines:
        change = line.current - line.prior
        pct = change_pct(line.current, line.prior)
        if line.derived_from:
            parts = [by_key[k] for k in line.derived_from if k in by_key]
            foots = len(parts) == len(line.derived_from) and (
                sum((p.current for p in parts), Decimal(0)) == line.current
                and sum((p.prior for p in parts), Decimal(0)) == line.prior
            )
            rows.append(FluxRow(line.key, line.label, line.current, line.prior, change, pct, None, True, foots))
            continue
        rows.append(
            FluxRow(line.key, line.label, line.current, line.prior, change, pct,
                    classify(change, pct, thresholds), False, True)
        )  # fmt: skip
    evaluated = [r for r in rows if not r.derived]
    over = sum(1 for r in evaluated if r.result == "over")
    return FluxSet(
        rows=tuple(rows),
        evaluated=len(evaluated),
        over=over,
        within=len(evaluated) - over,
        foots=all(r.foots for r in rows),
        engine_version=ENGINE_VERSION,
        inputs_hash=_hash(lines, thresholds),
    )
