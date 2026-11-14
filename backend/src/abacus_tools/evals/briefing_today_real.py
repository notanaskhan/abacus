"""Real runs of `briefing.today` (I-02-T20; I-02 §6.3; chapter 05 §5.5.3, chapter 10 §10.8.5;
ADR-070, ADR-081, ADR-113; DEC-4935): the direct route and Bedrock in the evaluation account.

    python -m abacus_tools.evals --agent briefing_today --route direct|bedrock [--subset fast]

Cadence: the fast subset on every PR touching an agent path (CI stage 3, `make
evals-briefing-fast`, the fake model), the full suite nightly on the fake model (`evals.yml`), and
these real runs on the direct route and on Bedrock in the evaluation account (OIDC, synthetic
data only), each producing one signed report.

Each case builds its persona's briefing on a throwaway stack's synthetic firm through the gateway
on the route and is graded by the fake run's graders (`briefing_today.grade`). The report holds the
rates against the frozen thresholds (`briefing_today.FROZEN`), the prioritisation judge's mean
(≥ 4.0), per-case cost and its median, per-case latency and its p95 (recorded: it drives the 20 s
first-open budget), and the **clearance**:

- `client_data: cleared` only when every frozen threshold holds (the DE-3 to DE-6 cases at 1.0 on
  every repeat), the judge's mean is at least 4.0, no attempt errored, the median cost is at most
  $0.10 a briefing and within 10 % of `evals/baselines.yaml`'s `briefing.today` row, the run is
  Bedrock's, and the route's parity check is under 90 days old. Anything else is `client_data:
  none` with every reason.
- Clearance never covers real tax return information on its own (G-5 to G-7 per firm and
  taxpayer).

Reports are signed (HMAC-SHA256, `ABACUS_EVAL_SIGNING_KEY`). The runs need the evaluation account's
stack and credentials; until that loop is wired there this refuses rather than reporting what it
did not measure. The pure parts are unit-tested without them.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Final

from abacus_tools.evals.briefing_today import CAPABILITY, FROZEN
from abacus_tools.evals.gate import COST_TOLERANCE
from abacus_tools.evals.runtime_conformance_real import median_cost, signed, verified
from abacus_tools.evals.runtime_conformance_real import Attempt as _CostAttempt
from abacus_tools.evals.tax_return_real import TRI_NOTE, baseline, parity_fresh

ROUTES: Final = ("direct", "bedrock")
TIER: Final = "medium"
COST_CAP: Final = Decimal("0.10")  # I-02 §6.3: at most $0.10 a briefing
JUDGE_FLOOR: Final = 4.0
P95_BUDGET_MS: Final = 12_000  # recorded; the first-open build budget is 20 s


@dataclass(frozen=True)
class BriefingAttempt:
    case: str
    passed: bool
    de: bool  # a DE-3 to DE-6 case: zero tolerance
    cost_usd: Decimal | None  # None: the attempt errored
    latency_ms: int | None = None
    judge: float | None = None  # the prioritisation judge's score, when the case is judged


def p95(values: Sequence[int]) -> int | None:
    """The nearest-rank 95th percentile."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def judge_mean(attempts: Sequence[BriefingAttempt]) -> float | None:
    scores = [a.judge for a in attempts if a.judge is not None]
    return sum(scores) / len(scores) if scores else None


def clearance(
    route: str,
    rates: Mapping[str, float],
    attempts: Sequence[BriefingAttempt],
    limit: Decimal | None,
    *,
    last_parity: date | None,
    today: date,
) -> dict[str, object]:
    """Whether the run clears `briefing.today` for client data, with every reason it doesn't."""
    reasons: list[str] = []
    if route not in ROUTES:
        reasons.append("unknown_route")
    elif route != "bedrock":
        reasons.append("not_the_production_route")
    reasons += [f"below_threshold:{g}" for g, floor in sorted(FROZEN.items())
                if rates.get(g, -1.0) < floor]  # fmt: skip
    if not attempts:
        reasons.append("no_attempts")
    if any(a.cost_usd is None for a in attempts):
        reasons.append("errored")
    if any(a.de and not a.passed for a in attempts):
        reasons.append("zero_tolerance_case_failed")
    judged = judge_mean(attempts)
    if judged is None or judged < JUDGE_FLOOR:
        reasons.append("judge_below_floor")
    cost = median_cost([_CostAttempt(a.case, a.passed, a.de, a.cost_usd) for a in attempts])
    if cost is not None and cost > COST_CAP:
        reasons.append("over_cost_cap")
    if limit is None:
        reasons.append("cost_regression:no_baseline")
    elif cost is not None and cost > limit * (1 + COST_TOLERANCE):
        reasons.append("cost_regression")
    if not parity_fresh(last_parity, today):
        reasons.append("route_parity_stale")
    latency = p95([a.latency_ms for a in attempts if a.latency_ms is not None])
    return {
        "capability": CAPABILITY,
        "route": route,
        "client_data": "none" if reasons else "cleared",
        "reasons": reasons,
        "median_cost_usd": None if cost is None else str(cost),
        "baseline_usd": None if limit is None else str(limit),
        "judge_mean": judged,
        "p95_latency_ms": latency,
        "p95_within_budget": latency is not None and latency <= P95_BUDGET_MS,
        "tri": TRI_NOTE,
    }


def report(
    route: str,
    rates: Mapping[str, float],
    attempts: Sequence[BriefingAttempt],
    *,
    last_parity: date | None,
    today: date,
) -> dict[str, object]:
    """The signed report body."""
    return signed(
        {
            "suite": "briefing_today",
            "route": route,
            "tier": TIER,
            "run_on": today.isoformat(),
            "cases": len(attempts),
            "rates": dict(rates),
            "costs": {a.case: None if a.cost_usd is None else str(a.cost_usd) for a in attempts},
            "latencies_ms": {a.case: a.latency_ms for a in attempts},
            "clearance": clearance(
                route, rates, attempts, baseline(CAPABILITY, TIER),
                last_parity=last_parity, today=today,
            ),
        }
    )  # fmt: skip


def real_main(route: str, out: Path, subset: str = "full") -> int:
    """The evaluation account's run (module docstring); refuses without the account's stack."""
    if route not in ROUTES:
        raise SystemExit(f"unknown route {route!r}: direct or bedrock")
    if not os.environ.get("ABACUS_EVAL_STACK"):
        raise SystemExit(
            "briefing_today real runs need the evaluation account's stack (ABACUS_EVAL_STACK) and "
            "model credentials: run them through `make evals`"
        )
    del out, subset
    # I-02-T20 (partial, DEC-4935): the stack-bound loop (seed the persona days, build each
    # briefing on the route, grade, sum the gateway's cost and latency) runs in the evaluation
    # account; until it is wired there this refuses rather than reporting what it did not measure.
    raise SystemExit("briefing_today real runs are the evaluation account's step (I-02-T20)")


__all__ = [
    "COST_CAP",
    "JUDGE_FLOOR",
    "P95_BUDGET_MS",
    "BriefingAttempt",
    "clearance",
    "judge_mean",
    "p95",
    "real_main",
    "report",
    "verified",
]
