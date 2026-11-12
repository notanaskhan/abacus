"""Real runs of the tax suites (T-04-T43; T-04 §6; ADR-070, ADR-081, ADR-113; DEC-4411): the direct
and Bedrock routes in the evaluation account.

    python -m abacus_tools.evals --agent tax_return --route direct|bedrock [--subset fast]

Each case runs its capability on a throwaway stack's synthetic firm through the gateway on the
route, and is graded by the same code graders as the fake run (`tax_return.grade_case`). The report
is per capability: its rates against the frozen thresholds (`tax_return.FROZEN`), per-case cost
and the median, and its **clearance**:

- `client_data: cleared` only when every frozen threshold holds, no zero-tolerance case failed, no
  attempt errored, the median cost is within 10 % of `evals/baselines.yaml`'s row for the
  capability and tier (no row fails closed), the run is Bedrock's, and the route's parity check is
  under 90 days old (ADR-113). Anything else is `client_data: none` with every reason.
- Clearance never covers real tax return information on its own: TRI still needs G-5 to G-7 per
  firm and taxpayer (the §7216 consents and the firm's opt-in), which the report states.

Reports are signed (HMAC-SHA256, `ABACUS_EVAL_SIGNING_KEY`, the conformance report's signer) and a
person records the baseline rows from a signed Bedrock report (a protected file). The runs need the
evaluation account's stack and credentials; the pure parts are unit-tested without them.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Final, cast

import yaml

from abacus_tools.evals.gate import COST_TOLERANCE
from abacus_tools.evals.runtime_conformance_real import Attempt, median_cost, signed, verified
from abacus_tools.evals.tax_return import CAPABILITIES, FROZEN

ROUTES: Final = ("direct", "bedrock")
PARITY_DAYS: Final = 90
TRI_NOTE: Final = "real tax return information still needs G-5 to G-7 per firm and taxpayer"
BASELINES: Final = Path(__file__).resolve().parents[4] / "evals" / "baselines.yaml"


def baseline(capability: str, tier: str, path: Path = BASELINES) -> Decimal | None:
    raw = cast(
        "dict[str, dict[str, object]]", yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    )
    value = (raw.get(capability) or {}).get(tier)
    return Decimal(str(value)) if value is not None else None


def below_thresholds(capability: str, rates: Mapping[str, float]) -> list[str]:
    """Each frozen grader the run did not meet (a grader not measured is below, fail closed)."""
    frozen = FROZEN[capability]
    return sorted(g for g, floor in frozen.items() if rates.get(g, -1.0) < floor)


def parity_fresh(last_parity: date | None, today: date) -> bool:
    return last_parity is not None and 0 <= (today - last_parity).days < PARITY_DAYS


def capability_clearance(
    capability: str,
    route: str,
    rates: Mapping[str, float],
    attempts: Sequence[Attempt],
    limit: Decimal | None,
    *,
    last_parity: date | None,
    today: date,
) -> dict[str, object]:
    """Whether the run clears the capability for client data, and every reason it doesn't."""
    reasons: list[str] = []
    if capability not in FROZEN:
        reasons.append("unknown_capability")
    if route not in ROUTES:
        reasons.append("unknown_route")
    elif route != "bedrock":
        reasons.append("not_the_production_route")
    if capability in FROZEN:
        reasons += [f"below_threshold:{g}" for g in below_thresholds(capability, rates)]
    if not attempts:
        reasons.append("no_attempts")
    if any(a.cost_usd is None for a in attempts):
        reasons.append("errored")
    if any(a.de and not a.passed for a in attempts):
        reasons.append("zero_tolerance_case_failed")
    cost = median_cost(attempts)
    if limit is None:
        reasons.append("cost_regression:no_baseline")
    elif cost is not None and cost > limit * (1 + COST_TOLERANCE):
        reasons.append("cost_regression")
    if not parity_fresh(last_parity, today):
        reasons.append("route_parity_stale")
    return {
        "capability": capability,
        "route": route,
        "client_data": "none" if reasons else "cleared",
        "reasons": reasons,
        "median_cost_usd": None if cost is None else str(cost),
        "baseline_usd": None if limit is None else str(limit),
        "tri": TRI_NOTE,
    }


def report(
    route: str,
    tier: str,
    by_capability: Mapping[str, tuple[Mapping[str, float], Sequence[Attempt]]],
    *,
    last_parity: date | None,
    today: date,
) -> dict[str, object]:
    """The signed report body: one entry per capability run."""
    entries: dict[str, object] = {}
    for capability, (rates, attempts) in sorted(by_capability.items()):
        entries[capability] = {
            "cases": len(attempts),
            "rates": dict(rates),
            "costs": {a.case: None if a.cost_usd is None else str(a.cost_usd) for a in attempts},
            "clearance": capability_clearance(
                capability,
                route,
                rates,
                attempts,
                baseline(capability, tier),
                last_parity=last_parity,
                today=today,
            ),
        }
    return signed(
        {
            "suite": "tax_return",
            "route": route,
            "tier": tier,
            "run_on": today.isoformat(),
            "capabilities": entries,
        }
    )


def real_main(route: str, out: Path, subset: str = "full") -> int:
    """The evaluation account's run (module docstring); refuses without the account's stack."""
    if route not in ROUTES:
        raise SystemExit(f"unknown route {route!r}: direct or bedrock")
    if not os.environ.get("ABACUS_EVAL_STACK"):
        raise SystemExit(
            "tax_return real runs need the evaluation account's stack (ABACUS_EVAL_STACK) and "
            "model credentials: run them through `make evals`"
        )
    del out, subset
    # T-04-T43 (partial, DEC-4411): the stack-bound loop (seed the synthetic households, run each
    # case's capability on the route, rebuild each trajectory, grade, sum the gateway's cost) runs
    # in the evaluation account; until it is wired there this refuses rather than reporting what it
    # did not measure.
    raise SystemExit("tax_return real runs are the evaluation account's step (T-04-T43)")


__all__ = [
    "CAPABILITIES",
    "PARITY_DAYS",
    "TRI_NOTE",
    "baseline",
    "below_thresholds",
    "capability_clearance",
    "parity_fresh",
    "real_main",
    "report",
    "verified",
]
