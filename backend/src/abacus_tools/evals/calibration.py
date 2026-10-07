"""Calibration (SPEC-005 AC-8, AC-9; TASK-020 design §5): does stated confidence mean anything?

Ten equal confidence bands; per band, how often the model's own answer was right (before the
code's routing) against how confident it said it was; the expected calibration error (ECE)
weights each band's gap by its share of answers. The recommended routing threshold is the lowest
`confidence_routing.below` that keeps the dangerous-error metric (needs-revision recall) at or
above its threshold: answers below it are routed to the spec's `confidence_routing.route`, as the
screener's code does.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from abacus_tools.evals.metrics import Attempt, needs_revision_recall

BANDS = 10


@dataclass(frozen=True)
class Calibration:
    ece: float
    bands: list[dict[str, float]]
    recommended_below: float | None
    current_below: float
    current_meets_threshold: bool


def _band(confidence: float) -> int:
    return min(int(confidence * BANDS), BANDS - 1)


def expected_calibration_error(
    points: Sequence[tuple[float, bool]],
) -> tuple[float, list[dict[str, float]]]:
    if not points:
        return 0.0, []
    grouped: dict[int, list[tuple[float, bool]]] = {}
    for confidence, correct in points:
        grouped.setdefault(_band(confidence), []).append((confidence, correct))
    ece = 0.0
    bands: list[dict[str, float]] = []
    for band in sorted(grouped):
        members = grouped[band]
        accuracy = sum(c for _, c in members) / len(members)
        confidence = sum(c for c, _ in members) / len(members)
        ece += len(members) / len(points) * abs(accuracy - confidence)
        bands.append(
            {
                "band": band / BANDS,
                "count": float(len(members)),
                "accuracy": accuracy,
                "confidence": confidence,
            }
        )
    return ece, bands


def routed(attempts: Sequence[Attempt], below: float, route: str) -> list[Attempt]:
    """The attempts as the code would route them with `below` as the threshold."""
    result: list[Attempt] = []
    for case, seen in attempts:
        if (
            seen.stage == "screened"
            and seen.confidence is not None
            and seen.model_action is not None
        ):
            action = route if seen.confidence < below else seen.model_action
            seen = replace(seen, action=action)
        result.append((case, seen))
    return result


def calibrate(
    attempts: Sequence[Attempt],
    *,
    current_below: float,
    route: str,
    dangerous_minimum: float,
) -> Calibration:
    points = [
        (seen.confidence, seen.model_action == case.expected.action)
        for case, seen in attempts
        if seen.stage == "screened"
        and case.expected.stage == "screened"
        and seen.confidence is not None
    ]
    ece, bands = expected_calibration_error(points)
    recommended = next(
        (
            step / 20
            for step in range(21)
            if needs_revision_recall(routed(attempts, step / 20, route)) >= dangerous_minimum
        ),
        None,
    )
    meets = needs_revision_recall(routed(attempts, current_below, route)) >= dangerous_minimum
    return Calibration(ece, bands, recommended, current_below, meets)
