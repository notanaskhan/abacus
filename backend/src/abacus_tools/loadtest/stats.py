"""Client-side latency statistics and the pass rule (Q-03-T035; Q-03 E1, E2).

Percentiles are nearest-rank over every sample of a group (no sampling, no histogram buckets),
in milliseconds. A group passes when its p95 target, if it has one, holds; a run passes when
every group does and the error rate stays below the scenario's ceiling (0.1% by default).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field


def percentile(samples: Sequence[float], p: float) -> float | None:
    """Nearest-rank percentile `p` (0 < p <= 100) of `samples`; None with no samples."""
    if not 0 < p <= 100:
        raise ValueError("p must be in (0, 100]")
    if not samples:
        return None
    ordered = sorted(samples)
    rank = math.ceil(p / 100 * len(ordered))
    return ordered[max(rank, 1) - 1]


@dataclass
class Samples:
    """One group's timings (ms) and outcomes, as the runner records them."""

    kind: str  # http | sse | temporal
    target_p95_ms: float | None = None
    latencies_ms: list[float] = field(default_factory=list[float])
    calls: int = 0
    errors: int = 0
    error_codes: dict[str, int] = field(default_factory=dict[str, int])

    def ok(self, ms: float) -> None:
        self.calls += 1
        self.latencies_ms.append(ms)

    def failed(self, code: str, ms: float | None = None) -> None:
        self.calls += 1
        self.errors += 1
        self.error_codes[code] = self.error_codes.get(code, 0) + 1
        if ms is not None:
            self.latencies_ms.append(ms)  # a failed call still took this long


@dataclass(frozen=True)
class GroupResult:
    name: str
    kind: str
    count: int
    errors: int
    error_codes: dict[str, int]
    p50_ms: float | None
    p95_ms: float | None
    p99_ms: float | None
    max_ms: float | None
    per_second: float
    target_p95_ms: float | None
    passed: bool


def summarise(name: str, samples: Samples, seconds: float) -> GroupResult:
    lat = samples.latencies_ms
    count = samples.calls
    p95 = percentile(lat, 95)
    target = samples.target_p95_ms
    return GroupResult(
        name,
        samples.kind,
        count,
        samples.errors,
        dict(sorted(samples.error_codes.items())),
        _round(percentile(lat, 50)),
        _round(p95),
        _round(percentile(lat, 99)),
        _round(max(lat) if lat else None),
        round(count / seconds, 2) if seconds > 0 else 0.0,
        target,
        target is None or (p95 is not None and p95 <= target),
    )


def _round(ms: float | None) -> float | None:
    return None if ms is None else round(ms, 1)


@dataclass(frozen=True)
class Verdict:
    passed: bool
    error_rate: float
    reasons: list[str]


def verdict(groups: Sequence[GroupResult], max_error_rate: float) -> Verdict:
    total = sum(g.count for g in groups)
    errors = sum(g.errors for g in groups)
    rate = errors / total if total else 1.0
    reasons = [
        f"{g.name}: p95 {g.p95_ms} ms over {g.target_p95_ms} ms" for g in groups if not g.passed
    ]
    if total == 0:
        reasons.append("no requests completed")
    elif rate >= max_error_rate and errors:
        reasons.append(f"error rate {rate:.4%} at or over {max_error_rate:.4%}")
    return Verdict(not reasons, round(rate, 6), reasons)
