"""A run's verdict from its attempts (SPEC-005 AC-3, AC-9, AC-12; TASK-020 design §6). The runner
and `publish` both use it, so a published summary's status is recomputed, never trusted.

Outcomes: `passed`; `failed` with reasons (`threshold:<metric>`, `calibration`,
`cost_regression`, `cost_regression:no_baseline`, `case_errors`, and `cases:<ids>` naming key cases
below the suite's pass rate); `aborted_cost` (stopped at the cost limit); `errored` (an exception,
or more than `MAX_ERRORED` of the attempts erroring).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal
from statistics import median

from abacus_tools.evals.calibration import calibrate
from abacus_tools.evals.gate import reasons
from abacus_tools.evals.graders import Grade, grade
from abacus_tools.evals.metrics import METRICS, Attempt
from abacus_tools.evals.suite import Suite

MAX_ERRORED = 0.2  # more errored attempts than this, and the run says nothing: `errored`


@dataclass(frozen=True)
class Verdict:
    status: str
    reasons: list[str]
    metrics: dict[str, float]
    calibration: dict[str, object]
    case_rows: list[dict[str, object]]
    total_cost_usd: Decimal
    median_case_cost_usd: Decimal


def judge(
    suite: Suite,
    attempts: Sequence[Attempt],
    *,
    fake: bool,
    aborted: bool,
    baseline: Decimal | None,
    current_below: float,
    route: str,
    model_grades: Mapping[tuple[str, int], Grade] | None = None,
) -> Verdict:
    """Grade every attempt (a model judge's grades, when the suite lists one, come in already
    awaited), compute the metrics and calibration, and apply the gate."""
    names = tuple(n for n in suite.graders if n != "model_judge")
    rows: list[dict[str, object]] = []
    by_case: dict[str, list[bool]] = {}
    for case, seen in attempts:
        grades = grade(names, case, seen)
        if "model_judge" in suite.graders:
            found = (model_grades or {}).get((case.id, seen.attempt))
            grades.append(found or Grade("model_judge", False, "grader_error: no verdict"))
        passed = all(g.passed for g in grades)
        by_case.setdefault(case.id, []).append(passed)
        row = {k: (str(v) if isinstance(v, Decimal) else v) for k, v in asdict(seen).items()}
        rows.append({**row, "passed": passed, "grades": [asdict(g) for g in grades]})
    metrics = {name: METRICS[name](attempts) for name in METRICS}
    dangerous = next(t.minimum for t in suite.thresholds if t.metric == suite.dangerous_error)
    calibration = calibrate(
        attempts, current_below=current_below, route=route, dangerous_minimum=dangerous
    )
    screened_costs = [s.cost_usd for _, s in attempts if s.stage == "screened"]
    errored = sum(s.stage == "errored" for _, s in attempts)
    found = reasons(suite, metrics, calibration, screened_costs, baseline, errored)
    if baseline is None and not fake:
        found.append("cost_regression:no_baseline")
    short = [
        case_id
        for case_id, results in by_case.items()
        if sum(results) / len(results) < suite.required_pass_rate
    ]
    if short:
        found.append("cases:" + ",".join(short))
    if aborted:
        status = "aborted_cost"
    elif attempts and errored / len(attempts) > MAX_ERRORED:
        status = "errored"
    else:
        status = "failed" if found else "passed"
    total = sum((s.cost_usd for _, s in attempts), Decimal(0))
    return Verdict(
        status,
        found,
        metrics,
        asdict(calibration),
        rows,
        total,
        Decimal(str(median(screened_costs))) if screened_costs else Decimal(0),
    )
