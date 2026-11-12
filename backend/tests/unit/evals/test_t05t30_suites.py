"""T-05-T30 (TASK-7525; T-05 §6.4): "Both suites have frozen thresholds and pass on the fake model
before N starts the prompts." Every grader has a seeded case that it catches."""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools.evals import tax_entity_part2 as p2


@pytest.mark.parametrize("agent", p2.AGENTS)
def test_the_suite_passes_on_the_fake_model_with_frozen_thresholds(agent: p2.Agent) -> None:
    report = p2.run_suite(agent, p2.load(agent))
    assert report["status"] == "passed", report
    assert report["graders_without_a_seeded_case"] == []


@pytest.mark.parametrize("agent", p2.AGENTS)
def test_a_lowered_threshold_is_refused(agent: p2.Agent, tmp_path: Path) -> None:
    raw = (p2.ROOT / agent / "suite.yaml").read_text(encoding="utf-8")
    (tmp_path / agent).mkdir()
    (tmp_path / agent / "suite.yaml").write_text(
        raw.replace(": 1.0\n", ": 0.9\n", 1), encoding="utf-8"
    )
    with pytest.raises(p2.ThresholdsChanged):
        p2.load(agent, tmp_path)


def test_the_fast_subset_runs_on_the_marked_cases() -> None:
    report = p2.run_suite("tax_recommender_modes", p2.load("tax_recommender_modes"), "fast")
    assert report["cases"] == 1
