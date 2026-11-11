"""T-05-T18 (TASK-7308; T-05 §6.4; DEC-4308): the entity return agents' suites part 1.

Row acceptance: "Both suites exist with frozen thresholds and pass on the fake model before any
prompt work starts." Every per-case grader has a seeded case it fails on; the thresholds in
`suite.yaml` are the frozen set, and a changed one is refused."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from abacus_tools.evals import tax_entity as te


@pytest.mark.parametrize("agent", te.AGENTS)
def test_the_suite_passes_on_the_fake_model_with_every_grader_seeded(agent: te.Agent) -> None:
    report = te.run_suite(agent, te.load(agent))
    assert report["status"] == "passed", report["reasons"]
    assert report["graders_without_a_seeded_case"] == []


@pytest.mark.parametrize("agent", te.AGENTS)
def test_a_changed_threshold_is_refused(agent: te.Agent, tmp_path: Path) -> None:
    raw = yaml.safe_load((te.ROOT / agent / "suite.yaml").read_text(encoding="utf-8"))
    first = next(iter(raw["thresholds"]))
    raw["thresholds"][first] = 0.5
    (tmp_path / agent).mkdir()
    (tmp_path / agent / "suite.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(te.ThresholdsChanged):
        te.load(agent, tmp_path)


def test_the_mapper_context_never_carries_an_amount() -> None:
    raw = te.load("tax_account_mapper")
    cases = [te.MapperCase.model_validate(c) for c in raw["cases"]]  # type: ignore[union-attr]  # a JSON value or a test double
    clean = [c for c in cases if c.category != "seeded"]
    published = frozenset(str(k) for k in raw["published_keys"])  # type: ignore[union-attr]  # a JSON value or a test double
    for case in clean:
        grades = {g.grader: g.passed for g in te.mapper_grades(case, published)}
        assert grades["no_amount_in_context"], case.id
