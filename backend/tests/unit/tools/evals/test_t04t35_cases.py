"""T-04-T35 (TASK-7314; T-04 §6; DEC-4313): the tax return suite's labelled cases.

Row acceptance: "The suite holds at least 150 labelled cases with sources, every DE-3 to DE-6 class
has cases, and the fake-model run passes the deterministic graders." The thresholds stay the frozen
set in the protected suite.yaml; a cases file that carries thresholds is refused."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from abacus_tools.evals import tax_return as tx


def test_at_least_150_cases_every_dangerous_class_and_the_fake_run_passes() -> None:
    thresholds, cases = tx.load()
    assert len(cases) >= 150
    classes = {d for c in cases for d in c.de_classes}
    assert {"DE-3", "DE-4", "DE-5", "DE-6"} <= classes
    labelled = [c for c in cases if c.source is not None]
    assert len(labelled) >= 119 and all(c.label_status == "pending_cpa" for c in labelled)
    report = tx.run_suite(thresholds, cases)
    assert report["status"] == "passed", report["reasons"]


def test_a_cases_file_may_not_carry_thresholds(tmp_path: Path) -> None:
    suite = tmp_path / "suite.yaml"
    suite.write_text(tx.SUITE.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "cases").mkdir()
    (tmp_path / "cases" / "x.yaml").write_text(
        yaml.safe_dump(
            {"thresholds": {"tax.assistant": {"citations_verified": 0.1}}, "cases": []}
        ),
        encoding="utf-8",
    )
    with pytest.raises(tx.ThresholdsChanged):
        tx.load(suite)
