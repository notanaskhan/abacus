"""The two-year comparison (T-08-T11; TASK-8726; SPEC-710; TAX-10; ADR-050; DEC-5720), pure.

Lines come from the current-year and prior-year engine summaries over the CPA-reviewed line map
(`code` → line). Delta and delta percent are computed by code (percent to one place, half up; a
prior of zero has no percent). A line is flagged when its delta's magnitude meets the threshold:
the checklist parameter or the firm's variance policy, whose version is pinned on the comparison.
An acceptance carries the hash of the values it accepted and goes stale when a value changes.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

ZERO: Final = Decimal("0")
ONE: Final = Decimal("0.1")


@dataclass(frozen=True, slots=True)
class Threshold:
    pct: Decimal
    amount: Decimal
    policy_version: str


@dataclass(frozen=True, slots=True)
class ComparisonLine:
    code: str
    label: str
    current: Decimal
    prior: Decimal
    delta: Decimal
    delta_pct: Decimal | None
    flagged: bool


def compare(
    current: Mapping[str, Decimal],
    prior: Mapping[str, Decimal],
    line_map: Sequence[tuple[str, str]],
    threshold: Threshold,
) -> list[ComparisonLine]:
    out = []
    for code, label in line_map:
        cy, py = current.get(code, ZERO), prior.get(code, ZERO)
        delta = cy - py
        pct = None if py == ZERO else (delta * 100 / abs(py)).quantize(ONE, ROUND_HALF_UP)
        flagged = abs(delta) >= threshold.amount and (pct is None or abs(pct) >= threshold.pct)
        out.append(ComparisonLine(code, label, cy, py, delta, pct, flagged))
    return out


def values_hash(lines: Sequence[ComparisonLine]) -> str:
    body = "|".join(f"{ln.code}:{ln.current}:{ln.prior}" for ln in lines)
    return hashlib.sha256(body.encode()).hexdigest()


def stale(accepted_hash: str, lines: Sequence[ComparisonLine]) -> bool:
    return accepted_hash != values_hash(lines)


__all__ = ["ComparisonLine", "Threshold", "compare", "stale", "values_hash"]
