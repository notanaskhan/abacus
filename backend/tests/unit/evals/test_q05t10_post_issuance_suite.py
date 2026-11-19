"""Q-05-T10 (TASK-8717; ADR-078 separate author; ADR-079; DEC-5713): the suite loader accepts the
suite with thresholds frozen, the recorded outputs pass, every grader catches its seeded case, and
a fake-model baseline fails every dangerous class the suite seeds."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from abacus_tools.evals import post_issuance_analysis as pi


def test_ac_the_loader_accepts_the_frozen_suite_of_30_labelled_cases() -> None:
    suite = pi.load()
    labelled = [c for c in suite.cases if c.category == "pass"]
    assert len(labelled) == 30
    assert any(c.id == "golden_pi_01_northwind" for c in suite.cases)
    assert sum(c.injected for c in labelled) == 6


def test_ac_the_recorded_outputs_pass_and_every_grader_catches_its_seeded_case() -> None:
    result = pi.run(pi.load())
    assert result.passed and result.seeded_caught


def test_ac_a_fake_baseline_fails_every_dangerous_class() -> None:
    suite = pi.load()
    result = pi.run(suite, pi.naive_baseline(suite.cases))
    assert not result.passed
    assert all(result.rates[name] < pi.FROZEN[name] for name in pi.DANGEROUS)


def test_ac_changed_thresholds_are_refused(tmp_path: Path) -> None:
    doc = yaml.safe_load((pi.ROOT / pi.SUITE / "suite.yaml").read_text(encoding="utf-8"))
    doc["thresholds"]["recommendation_consistency"] = 0.9
    path = tmp_path / "suite.yaml"
    path.write_text(yaml.safe_dump(doc))
    with pytest.raises(pi.ThresholdsChanged):
        pi.load(path)


def test_ac_the_golden_case_is_below_clearly_trivial_and_eligible() -> None:
    golden = next(c for c in pi.load().cases if c.id == "golden_pi_01_northwind")
    assert pi.eligible_no_action(golden)
    assert golden.facts["pct_of_overall"] == "4.9"
