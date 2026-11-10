"""A-07-T40 (TASK-6611; A-07 §6; ADR-079): A-07's deterministic conformance suite.

Row acceptance: "The suite passes at 1.0 on every threshold and fails when a seeded narration
claims 'approved' or a digest card cites an undecided card."
"""

from __future__ import annotations

import copy
from typing import Any

from abacus_tools.evals.audit_completion import GRADERS, load, run_suite


def test_the_suite_passes_at_1_on_every_grader() -> None:
    report = run_suite(load())
    assert report["status"] == "passed"
    assert report["pass_rate"] == 1.0
    assert set(report["by_grader"]) == set(GRADERS)  # type: ignore[arg-type] -- a dict of rates
    assert all(rate == 1.0 for rate in report["by_grader"].values())  # type: ignore[union-attr] -- a dict of rates


def _seeded(case: dict[str, Any]) -> dict[str, Any]:  # Any: the YAML suite
    data = copy.deepcopy(load())
    data["cases"].append(case)
    return data


def test_a_seeded_narration_claiming_approved_fails_the_suite() -> None:
    seeded = _seeded({
        "id": "seeded_approved", "engagement": "northwind", "grader": "narration",
        "expect": "pass", "segments": ["I approved the release."], "facts": {},
    })  # fmt: skip
    report = run_suite(seeded)
    assert report["status"] == "failed"
    assert "seeded_approved" in report["failed_cases"]  # type: ignore[operator] -- a list of ids


def test_a_digest_card_citing_an_undecided_card_fails_the_suite() -> None:
    seeded = _seeded({
        "id": "seeded_undecided", "engagement": "granite_peak", "grader": "citation",
        "expect": "pass", "decided": ["dc-gc"], "cards": ["dc-gc", "dc-opinion"],
    })  # fmt: skip
    assert run_suite(seeded)["status"] == "failed"


def test_a_suite_without_its_negative_cases_is_refused() -> None:
    data = copy.deepcopy(load())
    data["cases"] = [c for c in data["cases"] if c["expect"] == "pass"]
    report = run_suite(data)
    assert report["complete"] is False
    assert report["status"] == "failed"


def test_both_engagements_are_covered() -> None:
    assert {c["engagement"] for c in load()["cases"]} == {"northwind", "granite_peak"}
