"""T-06-T46 (TASK-8947; DEC-5939): the entity-depth suites load with their frozen thresholds,
every non-seeded case passes, every seeded case fails exactly on its defect, every grader has a
seeded case, and a lowered threshold is refused (ADR-079)."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus_tools.evals import tax_entity_depth as depth


@pytest.mark.parametrize("agent", depth.AGENTS)
def test_the_suite_passes_its_frozen_gate(agent: depth.Agent) -> None:
    assert depth.gate(agent) == []
    results, rates = depth.run(agent)
    assert all(r.passed for r in results)
    assert set(rates) == set(depth.FROZEN[agent])


def test_the_analyst_suite_covers_the_four_modes_and_three_attacks() -> None:
    raw = depth.load("tax_return_analyst")
    items = cast("list[dict[str, object]]", raw["cases"])
    cases = [depth.AnalystCase.model_validate(c) for c in items]
    modes = {c.mode for c in cases}
    assert modes == set(depth.MODES)
    attacks = {c.attack for c in cases} - {None}
    assert attacks == {"instruction_in_document", "wrong_date_bait", "hostile_name"}


def test_a_lowered_threshold_is_refused(tmp_path: Path) -> None:
    root = depth.ROOT
    suite = cast(
        "dict[str, dict[str, float]]",
        yaml.safe_load((root / "tax_return_analyst" / "suite.yaml").read_text("utf-8")),
    )
    suite["thresholds"]["mode_accuracy"] = 0.9
    target = tmp_path / "tax_return_analyst"
    target.mkdir()
    (target / "suite.yaml").write_text(yaml.safe_dump(suite), encoding="utf-8")
    with pytest.raises(depth.ThresholdsChanged):
        depth.load("tax_return_analyst", tmp_path)
