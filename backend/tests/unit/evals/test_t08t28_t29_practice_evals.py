"""T-08-T28 / T-08-T29 (TASK-9035; DEC-6040): the season_planner and tax_practice suites load
with their frozen thresholds, every non-seeded case passes on the fake model, every seeded case
fails exactly on its defect, every grader has a seeded case, every section and ask code has a
case, and a lowered threshold is refused (ADR-079)."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus_tools.evals import tax_practice as tp


@pytest.mark.parametrize("agent", tp.AGENTS)
def test_the_suite_passes_its_frozen_gate(agent: tp.Agent) -> None:
    assert tp.gate(agent) == []
    results, rates = tp.run(agent)
    assert all(r.passed for r in results)
    assert set(rates) == set(tp.FROZEN[agent])


def test_the_planner_suite_covers_every_ask_code_traps_and_an_ambiguity() -> None:
    items = cast("list[dict[str, object]]", tp.load("season_planner")["cases"])
    cases = [tp.PlannerCase.model_validate(c) for c in items]
    asked = {a.ask_code for c in cases if c.category != "seeded" for a in c.asks}
    assert asked == set(tp.ASK_CODES)
    assert {c.category for c in cases} >= {"pass", "trap", "ambiguity", "seeded"}
    assert all(c.label_status == "pending_cpa" for c in cases)  # the reviewer's sign is human


def test_the_practice_suite_covers_four_sections_attacks_and_consent() -> None:
    items = cast("list[dict[str, object]]", tp.load("tax_practice")["cases"])
    cases = [tp.PracticeCase.model_validate(c) for c in items]
    assert {c.section for c in cases if c.category == "pass"} == set(tp.SECTIONS)
    assert {c.attack for c in cases if c.category == "adversarial"} == {"instruction_in_document"}
    assert any(not c.consent for c in cases if c.category == "consent")


def test_a_lowered_threshold_is_refused(tmp_path: Path) -> None:
    for agent, metric in (
        ("season_planner", "assignee_eligible"),
        ("tax_practice", "section_accuracy"),
    ):
        suite = cast(
            "dict[str, dict[str, float]]",
            yaml.safe_load((tp.ROOT / agent / "suite.yaml").read_text("utf-8")),
        )
        suite["thresholds"][metric] = 0.5
        (tmp_path / agent).mkdir()
        (tmp_path / agent / "suite.yaml").write_text(yaml.safe_dump(suite), "utf-8")
        with pytest.raises(tp.ThresholdsChanged):
            tp.load(cast(tp.Agent, agent), tmp_path)
