"""Real runs of the group audit suites (A-09-T41; A-09 §6; ADR-079, ADR-081, ADR-113; DEC-5640):
`ledger.tb_mapper` on `evals/tb_mapping` and `consolidation.elimination_proposer` on
`evals/elimination_proposal`, on the direct and Bedrock routes in the evaluation account.

    python -m abacus_tools.evals --agent group_audit --route direct|bedrock [--subset fast]

Each case runs its capability on a throwaway stack's synthetic firm through the gateway on the
route and is graded by the same code graders as the recorded run (`group_audit.grade_mapping`,
`grade_elimination`). The report is per capability: its rates against the frozen thresholds
(`group_audit.FROZEN`), per-case cost and the median, and its **clearance**:

- `client_data: cleared` only when every frozen threshold holds, no zero-tolerance case failed (the
  elimination suite's weight-3 graders and the mapper's adversarial abstain), no attempt errored,
  the median cost is within 10 % of `evals/baselines.yaml`'s row (no row fails closed), the run is
  Bedrock's, and the route's parity check is under 90 days old (ADR-113). Anything else is
  `client_data: none` with every reason.
- Clearance is the route's, never a firm's: each capability stays `client_data: none` for a firm
  until that firm opts in (A-09 §6), which the report states.

Reports are signed (HMAC-SHA256, `ABACUS_EVAL_SIGNING_KEY`, the conformance report's signer); a
person records the baseline rows from a signed Bedrock report (a protected file). The runs need the
evaluation account's stack and credentials; the pure parts are unit-tested without them.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Final

from abacus_tools.evals.gate import COST_TOLERANCE
from abacus_tools.evals.group_audit import FROZEN as SUITE_FROZEN
from abacus_tools.evals.runtime_conformance_real import Attempt, median_cost, signed, verified
from abacus_tools.evals.tax_return_real import baseline, parity_fresh

ROUTES: Final = ("direct", "bedrock")
# Each capability's suite and its baseline tier (evals/baselines.yaml, A-09-T09's reserved rows).
SUITES: Final[Mapping[str, str]] = {
    "ledger.tb_mapper": "tb_mapping",
    "consolidation.elimination_proposer": "elimination_proposal",
}
TIERS: Final[Mapping[str, str]] = {
    "ledger.tb_mapper": "small",
    "consolidation.elimination_proposer": "medium",
}
FIRM_NOTE: Final = "client data stays off for each firm until that firm opts in (A-09 §6)"


def below_thresholds(capability: str, rates: Mapping[str, float]) -> list[str]:
    """Each frozen grader the run did not meet (a grader not measured is below, fail closed)."""
    frozen = SUITE_FROZEN[SUITES[capability]]
    return sorted(g for g, floor in frozen.items() if rates.get(g, -1.0) < floor)


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
    """Whether the run clears the capability's route for client data, and every reason not."""
    reasons: list[str] = []
    if capability not in SUITES:
        reasons.append("unknown_capability")
    if route not in ROUTES:
        reasons.append("unknown_route")
    elif route != "bedrock":
        reasons.append("not_the_production_route")
    if capability in SUITES:
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
        "firm_opt_in": FIRM_NOTE,
    }


def report(
    route: str,
    by_capability: Mapping[str, tuple[Mapping[str, float], Sequence[Attempt]]],
    *,
    last_parity: date | None,
    today: date,
    baselines: Path | None = None,
) -> dict[str, object]:
    """The signed report body: one entry per capability run, each on its own baseline tier."""
    entries: dict[str, object] = {}
    for capability, (rates, attempts) in sorted(by_capability.items()):
        tier = TIERS.get(capability, "small")
        limit = (
            baseline(capability, tier)
            if baselines is None
            else baseline(capability, tier, baselines)
        )
        entries[capability] = {
            "suite": SUITES.get(capability),
            "tier": tier,
            "cases": len(attempts),
            "rates": dict(rates),
            "costs": {a.case: None if a.cost_usd is None else str(a.cost_usd) for a in attempts},
            "clearance": capability_clearance(
                capability, route, rates, attempts, limit, last_parity=last_parity, today=today
            ),
        }
    return signed(
        {
            "suite": "group_audit",
            "route": route,
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
            "group_audit real runs need the evaluation account's stack (ABACUS_EVAL_STACK) and "
            "model credentials: run them through `make evals`"
        )
    del out, subset
    # A-09-T41 (partial, DEC-5640): the stack-bound loop (load Harlow & Pike and the synthetic
    # groups, run each case's capability on the route, grade with the group_audit graders, sum the
    # gateway's cost) runs in the evaluation account; until it is wired there this refuses rather
    # than reporting what it did not measure.
    raise SystemExit("group_audit real runs are the evaluation account's step (A-09-T41)")


__all__ = [
    "FIRM_NOTE",
    "ROUTES",
    "SUITES",
    "TIERS",
    "below_thresholds",
    "capability_clearance",
    "real_main",
    "report",
    "verified",
]
