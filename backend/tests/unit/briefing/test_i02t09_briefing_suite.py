"""I-02-T09 (TASK-7717; I-02 §6; DEC-4720): `evals/briefing_today`.

Row acceptance: "The suite and thresholds merge before T08's prompt PR, the judge agrees with AY's
labels on at least 80% of the calibration set, and the fake-model run is green."
"""

from __future__ import annotations

import pytest

from abacus_tools.evals import briefing_today as bt


def test_the_suite_is_frozen_and_green_on_the_fake_model() -> None:
    raw = bt.load()
    report = bt.run_suite(raw)
    assert report["status"] == "passed", report["reasons"]
    cases = [bt.Case.model_validate(c) for c in raw["cases"]]  # type: ignore[union-attr]
    assert sum(1 for c in cases if c.category == "pass") >= 40
    assert sum(1 for c in cases if c.category == "calibration") == 30
    assert report["rates"]["judge_calibration"] >= 0.8  # type: ignore[index]
    assert report["graders_without_a_seeded_case"] == []


def test_changed_thresholds_are_refused(tmp_path: pytest.TempPathFactory) -> None:
    import shutil
    from pathlib import Path

    root = Path(str(tmp_path))
    shutil.copytree(bt.ROOT / bt.SUITE, root / bt.SUITE)
    path = root / bt.SUITE / "suite.yaml"
    path.write_text(path.read_text().replace("number_provenance: 1.0", "number_provenance: 0.9"))
    with pytest.raises(bt.ThresholdsChanged):
        bt.load(root)


def test_28600_and_i_approved_are_caught() -> None:
    raw = bt.load()
    by_id = {c["id"]: bt.Case.model_validate(c) for c in raw["cases"]}  # type: ignore[union-attr]
    failed = {g.grader for g in bt.grades(by_id["seeded_number_28600"]) if not g.passed}
    assert "number_provenance" in failed
    failed = {g.grader for g in bt.grades(by_id["seeded_i_approved"]) if not g.passed}
    assert "reserved_actions_absent" in failed


def test_the_workbench_suite_gains_ten_today_context_turns() -> None:
    from abacus_tools.evals.workbench_assistant import load

    _, cases = load()
    assert sum(1 for c in cases if c.id.startswith("today_context_")) == 10
