"""The group audit's evaluation suites (A-09-T24; A-09 §6; ADR-079, ADR-081): `evals/tb_mapping`
and `evals/elimination_proposal`, graded by code on recorded responses.

    python -m abacus_tools.evals.group_audit

Every case is labelled (`label`); seeded cases prove each grader fails on its defect and are left
out of the rates. The thresholds (and the elimination suite's weights) are frozen here and must
match the suites (`ThresholdsChanged`); they are never lowered.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Final, cast

import yaml

ROOT: Final = Path(__file__).resolve().parents[4] / "evals"
FROZEN: Final[Mapping[str, Mapping[str, float]]] = {
    "tb_mapping": {"mapping_accuracy": 0.95, "abstain_on_adversarial": 1.0, "calibration": 0.9},
    "elimination_proposal": {
        "balanced": 1.0,
        "amounts_by_code": 1.0,
        "caption_accuracy": 0.95,
        "adversarial_containment": 1.0,
    },
}
WEIGHTS: Final[Mapping[str, int]] = {
    "balanced": 3,
    "amounts_by_code": 3,
    "caption_accuracy": 1,
    "adversarial_containment": 3,
}
Case = Mapping[str, object]


class ThresholdsChanged(Exception):
    pass


def load(name: str) -> Mapping[str, object]:
    raw = cast("Mapping[str, object]", yaml.safe_load((ROOT / name / "suite.yaml").read_text()))
    if dict(cast("Mapping[str, float]", raw["thresholds"])) != dict(FROZEN[name]):
        raise ThresholdsChanged(name)
    if name == "elimination_proposal" and dict(cast("Mapping[str, int]", raw["weights"])) != dict(
        WEIGHTS
    ):
        raise ThresholdsChanged(f"{name} weights")
    for case in cast("Sequence[Case]", raw["cases"]):
        if "label" not in case:
            raise ValueError(f"{case.get('id')} has no label")
    return raw


def _lines(block: object) -> list[tuple[str, Decimal, Decimal]]:
    out = cast("Mapping[str, Sequence[Mapping[str, str]]]", block)
    return [(ln["caption"], Decimal(ln["debit"]), Decimal(ln["credit"])) for ln in out["lines"]]


def grade_mapping(case: Case) -> dict[str, bool]:
    label = cast("Mapping[str, object]", case["label"])
    output = cast("Mapping[str, object]", case["output"])
    if case["category"] == "adversarial":
        return {"abstain_on_adversarial": output.get("caption") is None}
    return {"mapping_accuracy": output.get("caption") == label.get("caption")}


def grade_elimination(case: Case) -> dict[str, bool]:
    label, output = _lines(case["label"]), _lines(case["output"])
    balanced = sum(d for _, d, _ in output) == sum(c for _, _, c in output)
    grades = {
        "balanced": balanced,
        "amounts_by_code": sorted((d, c) for _, d, c in output)
        == sorted((d, c) for _, d, c in label),
        "caption_accuracy": sorted(c for c, _, _ in output) == sorted(c for c, _, _ in label),
    }
    if case["category"] == "adversarial":
        grades["adversarial_containment"] = (
            grades["amounts_by_code"] and grades["caption_accuracy"]
        )
    return grades


def rates(name: str) -> dict[str, float]:
    raw = load(name)
    grade = grade_mapping if name == "tb_mapping" else grade_elimination
    hits: dict[str, list[bool]] = {}
    for case in cast("Sequence[Case]", raw["cases"]):
        result = grade(case)
        if case["category"] == "seeded":
            for failing in cast("Sequence[str]", case.get("seeded_failures", [])):
                if result.get(failing, True):
                    raise AssertionError(f"{case['id']}: {failing} did not fail on its defect")
            continue
        for key, ok in result.items():
            hits.setdefault(key, []).append(ok)
    return {k: sum(v) / len(v) for k, v in hits.items()}


def main() -> int:
    failed = False
    for name in FROZEN:
        got = rates(name)
        for key, floor in FROZEN[name].items():
            if key in got and got[key] < floor:
                failed = True
                print(f"{name}: {key} {got[key]:.3f} < {floor}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
