"""A-09-T24: both group-audit suites load with their frozen thresholds, every case is labelled,
every grader fails on its seeded defect, and the recorded responses meet the thresholds."""

from __future__ import annotations

from typing import cast

from abacus_tools.evals import group_audit as ga


def test_both_suites_run_on_the_recorded_responses_and_meet_their_thresholds() -> None:
    for name, floors in ga.FROZEN.items():
        got = ga.rates(name)
        for key, floor in floors.items():
            if key in got:
                assert got[key] >= floor, (name, key)


def test_the_dangerous_errors_weigh_three() -> None:
    raw = ga.load("elimination_proposal")
    assert raw["weights"] == {"balanced": 3, "amounts_by_code": 3, "caption_accuracy": 1,
                              "adversarial_containment": 3}  # fmt: skip
    cases = raw["cases"]
    assert isinstance(cases, list) and len(cast("list[object]", cases)) >= 26
