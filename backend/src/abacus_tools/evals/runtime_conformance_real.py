"""Real runs of `runtime.conformance` (P-10-T46; P-10 §6; SPEC-647 §6; ADR-070, ADR-081;
DEC-4314): the direct and Bedrock routes in the evaluation account.

    python -m abacus_tools.evals --agent runtime_conformance --route direct|bedrock [--subset fast]

Each case's request runs through `agents.run_conformance` on a throwaway stack's synthetic firm (a
real `converse()` per turn with the spec's prompt, tier, budget and routes; C17 per tool call), and
its trajectory is graded by the same code graders as the fake run
(`runtime_conformance.grade_case`).
The report adds per-case cost and the run's median, and states whether the route **clears**
(`clearance`): every frozen threshold holds, no DE case failed, no attempt errored, and the median
cost per case is within 10 % of `evals/baselines.yaml`'s `runtime.conformance` row for the tier (no
row: `cost_regression:no_baseline`, fail closed). Only a Bedrock run clears for production. The
report is signed with CI's key (HMAC-SHA256 over canonical JSON, `ABACUS_EVAL_SIGNING_KEY`), and
a person records the baseline row from a signed report (a protected file).

The runs need the evaluation account's credentials and a stack (`make evals`); this module's
pure parts (cost, clearance, signing) are unit-tested without either.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Final

import yaml

from abacus_tools.evals.gate import COST_TOLERANCE

AGENT: Final = "runtime.conformance"
SIGNING_KEY_ENV: Final = "ABACUS_EVAL_SIGNING_KEY"
ROUTES: Final = ("direct", "bedrock")
BASELINES: Final = Path(__file__).resolve().parents[4] / "evals" / "baselines.yaml"


@dataclass(frozen=True)
class Attempt:
    case: str
    passed: bool
    de: bool
    cost_usd: Decimal | None  # None: the attempt errored before it finished


def median_cost(attempts: Sequence[Attempt]) -> Decimal | None:
    costs = [a.cost_usd for a in attempts if a.cost_usd is not None]
    return Decimal(str(statistics.median(costs))) if costs else None


def baseline(tier: str, path: Path = BASELINES) -> Decimal | None:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    row = raw.get(AGENT) or {}
    value = row.get(tier)
    return Decimal(str(value)) if value is not None else None


def clearance(
    route: str,
    below_threshold: Sequence[str],
    attempts: Sequence[Attempt],
    limit: Decimal | None,
) -> dict[str, object]:
    """Whether this run clears the route, and every reason it doesn't (fail closed)."""
    reasons: list[str] = []
    if route not in ROUTES:
        reasons.append("unknown_route")
    reasons += [f"below_threshold:{g}" for g in sorted(below_threshold)]
    if not attempts:
        reasons.append("no_attempts")
    if any(a.cost_usd is None for a in attempts):
        reasons.append("errored")
    if any(a.de and not a.passed for a in attempts):
        reasons.append("de_case_failed")
    cost = median_cost(attempts)
    if limit is None:
        reasons.append("cost_regression:no_baseline")
    elif cost is not None and cost > limit * (1 + COST_TOLERANCE):
        reasons.append("cost_regression")
    return {
        "route": route,
        "cleared": not reasons,
        "production": route == "bedrock" and not reasons,
        "reasons": reasons,
        "median_cost_usd": None if cost is None else str(cost),
        "baseline_usd": None if limit is None else str(limit),
    }


def _canonical(report: Mapping[str, object]) -> bytes:
    return json.dumps(report, sort_keys=True, separators=(",", ":"), default=str).encode()


def signed(report: dict[str, object]) -> dict[str, object]:
    key = os.environ.get(SIGNING_KEY_ENV)
    if not key:
        return report
    return {
        **report,
        "signature": hmac.new(key.encode(), _canonical(report), hashlib.sha256).hexdigest(),
    }


def verified(report: Mapping[str, object]) -> bool:
    key, signature = os.environ.get(SIGNING_KEY_ENV), report.get("signature")
    if not key or not isinstance(signature, str):
        return False
    body = {k: v for k, v in report.items() if k != "signature"}
    expected = hmac.new(key.encode(), _canonical(body), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def report(
    route: str,
    tier: str,
    rates: Mapping[str, float],
    below: Sequence[str],
    attempts: Sequence[Attempt],
) -> dict[str, object]:
    return {
        "suite": "runtime_conformance",
        "capability": AGENT,
        "route": route,
        "tier": tier,
        "cases": len(attempts),
        "rates": dict(rates),
        "costs": {a.case: None if a.cost_usd is None else str(a.cost_usd) for a in attempts},
        "clearance": clearance(route, below, attempts, baseline(tier)),
    }


def real_main(route: str, out: Path, subset: str = "full") -> int:
    """The evaluation account's run (module docstring); refuses without the account's stack."""
    if route not in ROUTES:
        raise SystemExit(f"unknown route {route!r}: direct or bedrock")
    if not os.environ.get("ABACUS_EVAL_STACK"):
        raise SystemExit(
            "runtime.conformance real runs need the evaluation account's stack "
            "(ABACUS_EVAL_STACK) and model credentials: run them through `make evals`"
        )
    del out, subset
    # P-10-T46 (partial, DEC-4314): the stack-bound loop (seed the synthetic firm's run rows, call
    # `run_conformance` per case on the route, rebuild each trajectory, grade, sum the gateway's
    # cost) runs in the evaluation account; until it is wired there this refuses rather than
    # reporting anything it did not measure.
    raise SystemExit("runtime.conformance real runs are the evaluation account's step (P-10-T46)")


__all__ = ["Attempt", "clearance", "median_cost", "real_main", "report", "signed", "verified"]
