"""Bedrock clearance for the entity return capabilities (T-05-T64; T-05 §6; ADR-070, ADR-081,
ADR-113; DEC-4936): `tax.account_mapper`, `tax.agreement_reader`, `tax.memo_drafter` and the
recommender's tax modes, run in full in the evaluation account.

    python -m abacus_tools.evals --agent tax_account_mapper|tax_agreement_reader|tax_memo_drafter|
        tax_recommender_modes --route direct|bedrock [--subset fast]

Each suite is graded by its fake run's code graders (`tax_entity`, `tax_entity_part2`), against
the thresholds frozen there before any prompt work (ADR-079: never lowered). One signed report
per capability carries the rates, per-case cost and its median, and the **clearance**:

- `client_data: cleared` only when every frozen threshold holds, no zero-tolerance case failed,
  no attempt errored, the median cost is within 10 % of the capability's `evals/baselines.yaml` row
  (the spec's own budget, no row fails closed), the run is Bedrock's, and the route's parity check
  is under 90 days old. Anything else is `client_data: none` with every reason.
- Clearance never covers real tax return information on its own (G-5 to G-7 per firm and
  taxpayer). The plan needs all four cleared before the Jul 10 shadow on pilot 1065s.

Reports are signed (HMAC-SHA256, `ABACUS_EVAL_SIGNING_KEY`). The runs need the evaluation account's
stack; until its loop is wired this refuses rather than reporting what it did not measure.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Final

from abacus_tools.evals import tax_entity, tax_entity_part2
from abacus_tools.evals.gate import COST_TOLERANCE
from abacus_tools.evals.runtime_conformance_real import Attempt, median_cost, signed, verified
from abacus_tools.evals.tax_return_real import TRI_NOTE, baseline, parity_fresh

ROUTES: Final = ("direct", "bedrock")
# The suite, its capability and the tier its spec runs on (the baseline row's key).
SUITES: Final[Mapping[str, tuple[str, str]]] = {
    "tax_account_mapper": ("tax.account_mapper", "small"),
    "tax_agreement_reader": ("tax.agreement_reader", "medium"),
    "tax_memo_drafter": ("tax.memo_drafter", "medium"),
    "tax_recommender_modes": ("decisions.recommender", "medium"),
}
FROZEN: Final[Mapping[str, Mapping[str, float]]] = {
    **tax_entity.FROZEN,
    **tax_entity_part2.FROZEN,
}


def clearance(
    suite: str,
    route: str,
    rates: Mapping[str, float],
    attempts: Sequence[Attempt],
    *,
    last_parity: date | None,
    today: date,
    limit: Decimal | None = None,
) -> dict[str, object]:
    """Whether the run clears the suite's capability for client data, and every reason not."""
    reasons: list[str] = []
    capability, tier = SUITES.get(suite, (suite, "medium"))
    if suite not in SUITES:
        reasons.append("unknown_suite")
    if route not in ROUTES:
        reasons.append("unknown_route")
    elif route != "bedrock":
        reasons.append("not_the_production_route")
    frozen = FROZEN.get(suite, {})
    reasons += [f"below_threshold:{g}" for g, floor in sorted(frozen.items())
                if rates.get(g, -1.0) < floor]  # fmt: skip
    if not attempts:
        reasons.append("no_attempts")
    if any(a.cost_usd is None for a in attempts):
        reasons.append("errored")
    if any(a.de and not a.passed for a in attempts):
        reasons.append("zero_tolerance_case_failed")
    budget = limit if limit is not None else baseline(capability, tier)
    cost = median_cost(attempts)
    if budget is None:
        reasons.append("cost_regression:no_baseline")
    elif cost is not None and cost > budget * (1 + COST_TOLERANCE):
        reasons.append("cost_regression")
    if not parity_fresh(last_parity, today):
        reasons.append("route_parity_stale")
    return {
        "capability": capability,
        "route": route,
        "client_data": "none" if reasons else "cleared",
        "reasons": reasons,
        "median_cost_usd": None if cost is None else str(cost),
        "baseline_usd": None if budget is None else str(budget),
        "tri": TRI_NOTE,
    }


def report(
    suite: str,
    route: str,
    rates: Mapping[str, float],
    attempts: Sequence[Attempt],
    *,
    last_parity: date | None,
    today: date,
) -> dict[str, object]:
    capability, tier = SUITES[suite]
    return signed(
        {
            "suite": suite,
            "capability": capability,
            "route": route,
            "tier": tier,
            "run_on": today.isoformat(),
            "cases": len(attempts),
            "rates": dict(rates),
            "costs": {a.case: None if a.cost_usd is None else str(a.cost_usd) for a in attempts},
            "clearance": clearance(
                suite, route, rates, attempts, last_parity=last_parity, today=today
            ),
        }
    )


def real_main(suite: str, route: str, out: Path, subset: str = "full") -> int:
    if suite not in SUITES:
        raise SystemExit(f"unknown suite {suite!r}")
    if route not in ROUTES:
        raise SystemExit(f"unknown route {route!r}: direct or bedrock")
    if not os.environ.get("ABACUS_EVAL_STACK"):
        raise SystemExit(
            f"{suite} real runs need the evaluation account's stack (ABACUS_EVAL_STACK) and model "
            "credentials: run them through `make evals`"
        )
    del out, subset
    # T-05-T64 (partial, DEC-4936): the stack-bound loop runs in the evaluation account; until it
    # is wired there this refuses rather than reporting what it did not measure.
    raise SystemExit(f"{suite} real runs are the evaluation account's step (T-05-T64)")


__all__ = ["FROZEN", "SUITES", "clearance", "real_main", "report", "verified"]
