"""Agent override rates (Q-05-T07; TASK-8714; DEC-96; SPEC-711 AC-3; DEC-5710), pure.

One outcome per agent output (adopted, changed or rejected). An override is a change or a
rejection. An agent is rated once it has `SAMPLE_N` outputs in the window; its rate is overrides
over outputs as an exact `Decimal` to one place (half up), and it is above tolerance only when its
rate exceeds the published AI policy's tolerance (exact comparison, never a float).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal

Outcome = Literal["adopted", "changed", "rejected"]
SAMPLE_N: Final = 25
ONE_PLACE: Final = Decimal("0.1")


@dataclass(frozen=True, slots=True)
class OutcomeRow:
    agent_key: str
    outcome: Outcome
    reason_code: str | None = None


@dataclass(frozen=True, slots=True)
class AgentRate:
    agent_key: str
    outputs: int
    overrides: int
    rate: Decimal | None
    rated: bool
    above_tolerance: bool


def rate(overrides: int, outputs: int) -> Decimal | None:
    if outputs == 0:
        return None
    return (Decimal(overrides) * 100 / Decimal(outputs)).quantize(ONE_PLACE, ROUND_HALF_UP)


def per_agent(rows: Iterable[OutcomeRow], tolerance_pct: Decimal) -> list[AgentRate]:
    counts: dict[str, tuple[int, int]] = {}
    for r in rows:
        n, o = counts.get(r.agent_key, (0, 0))
        counts[r.agent_key] = (n + 1, o + int(r.outcome != "adopted"))
    out = []
    for key in sorted(counts):
        n, o = counts[key]
        rated = n >= SAMPLE_N
        r = rate(o, n)
        out.append(AgentRate(key, n, o, r, rated, rated and r is not None and r > tolerance_pct))
    return out


def totals(rows: Iterable[OutcomeRow]) -> tuple[int, int, Decimal | None]:
    """Firm-wide (or one office's): outputs, overrides and the rate (206 of 3,410 = 6.0%)."""
    listed = list(rows)
    overrides = sum(1 for r in listed if r.outcome != "adopted")
    return len(listed), overrides, rate(overrides, len(listed))


def reasons(rows: Iterable[OutcomeRow], agent_key: str) -> list[tuple[str, int]]:
    """An agent's override reasons, most frequent first (ties by code)."""
    counts: dict[str, int] = {}
    for r in rows:
        if r.agent_key == agent_key and r.outcome != "adopted" and r.reason_code:
            counts[r.reason_code] = counts.get(r.reason_code, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


__all__ = [
    "SAMPLE_N",
    "AgentRate",
    "Outcome",
    "OutcomeRow",
    "per_agent",
    "rate",
    "reasons",
    "totals",
]
