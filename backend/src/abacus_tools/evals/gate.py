"""The gate (SPEC-005 AC-9, AC-12; TASK-020 design §6): a run passes only if every threshold
holds, calibration is within tolerance, cost per case hasn't regressed, and no case errored."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from statistics import median

from abacus_tools.evals.calibration import Calibration
from abacus_tools.evals.suite import Suite

COST_TOLERANCE = Decimal("0.10")  # Q5: at most 10% over the protected baseline


def reasons(
    suite: Suite,
    metrics: Mapping[str, float],
    calibration: Calibration,
    case_costs: Sequence[Decimal],
    baseline: Decimal | None,
    errored: int,
) -> list[str]:
    found: list[str] = []
    for threshold in suite.thresholds:
        if metrics.get(threshold.metric, 0.0) < threshold.minimum:
            found.append(f"threshold:{threshold.metric}")
    if calibration.ece > suite.calibration_tolerance or not calibration.current_meets_threshold:
        found.append("calibration")
    if (
        baseline is not None
        and case_costs
        and (Decimal(str(median(case_costs))) > baseline * (1 + COST_TOLERANCE))
    ):
        found.append("cost_regression")
    if errored:
        found.append("case_errors")
    return found
