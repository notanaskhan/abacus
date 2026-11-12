"""W-02-T07 (TASK-7607; W-02 §6; DEC-4606): `evals/workbench_assistant` holds at least 60 cases
across the five groups, its thresholds are W-02 §6's and frozen, every DE-3 to DE-6 case passes
3 of 3, and each grader fails a deliberately wrong FakeModel trajectory."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from abacus_tools.evals import workbench_assistant as wa


def test_the_suite_has_sixty_cases_across_the_five_groups() -> None:
    _, cases = wa.load()
    passing = [c for c in cases if c.category == "pass"]
    assert len(passing) >= 60
    by_group = {g: sum(1 for c in passing if c.group == g) for g in wa.FROZEN}
    assert by_group["read_only"] >= 20
    assert by_group["ambiguity"] >= 8
    assert by_group["plans"] >= 15
    assert by_group["scope"] >= 8
    assert by_group["adversarial"] >= 10


def test_de_cases_have_threshold_one_and_repeat_three() -> None:
    _, cases = wa.load()
    de = [c for c in cases if c.de]
    assert {tag for c in de for tag in c.de} == {"DE-3", "DE-4", "DE-5", "DE-6"}
    assert all(c.repeat == 3 for c in de)
    for group in ("scope", "adversarial"):
        assert all(v == 1.0 for v in wa.FROZEN[group].values())  # type: ignore[index]


def test_the_full_suite_passes_on_the_fake_model() -> None:
    _, cases = wa.load()
    report = wa.run_suite(cases)
    assert report["status"] == "passed", report


def test_every_grader_is_proven_by_a_seeded_case() -> None:
    _, cases = wa.load()
    assert wa.run_suite(cases)["graders_without_a_seeded_case"] == []
    for case in (c for c in cases if c.category == "seeded"):
        assert set(wa.grade_case(case).failed) == set(case.seeded_failures), case.id


def test_changing_a_threshold_is_refused(tmp_path: Path) -> None:
    raw = yaml.safe_load(wa.SUITE.read_text(encoding="utf-8"))
    raw["thresholds"]["read_only"]["citations_verified"] = 0.9
    edited = tmp_path / "suite.yaml"
    edited.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(wa.ThresholdsChanged):
        wa.load(edited)


def test_a_de_case_needs_three_of_three() -> None:
    _, cases = wa.load()
    de = next(c for c in cases if c.de and c.category == "pass")
    broken = de.model_copy(
        update={"turn": de.turn.model_copy(update={"acted_on": de.expected.injection_targets})}
    )
    if not de.expected.injection_targets:
        broken = de.model_copy(update={"turn": de.turn.model_copy(update={"claims_write": True})})
    result = wa.grade_case(broken)
    assert not result.passed and result.runs_passed == 0 and result.runs == 3
