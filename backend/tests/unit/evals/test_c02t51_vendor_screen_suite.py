"""ac-test-author ayushkbhatia

C-02-T51 (TASK-8816): the close vendor-screen suite is frozen and graded on the fake model.
"The cases and frozen thresholds merge in the protected file before T34 opens, run on the fake
model in CI, and no case uses kit sample data."
"""

from __future__ import annotations

import yaml

from abacus_tools.evals import close_vendor_screen as s


def test_ac_thresholds_are_frozen_in_the_file() -> None:
    suite = s.load()
    assert dict(suite.thresholds) == dict(s.FROZEN)
    assert s.FROZEN["attorney_recall"] == 1.0 and s.FROZEN["individuals_marked_exempt"] == 0.0
    assert s.FROZEN["entity_accuracy"] == 0.95


def test_ac_eighty_cases_plus_one_seeded_per_grader() -> None:
    suite = s.load()
    graded = [c for c in suite.cases if c.category != "seeded"]
    assert len(graded) == 80
    assert sum(c.category == "copperleaf" for c in graded) == 12
    assert sum(c.category == "adversarial" for c in graded) == 20
    assert {c.error for c in suite.cases if c.category == "seeded"} == set(s.DANGEROUS)


def test_ac_the_suite_passes_and_the_naive_baseline_fails_every_class() -> None:
    suite = s.load()
    assert s.run(suite).passed
    baseline = s.run(suite, s.naive_baseline(suite))
    assert not baseline.passed


def test_ac_no_case_uses_kit_sample_data() -> None:
    text = (s.ROOT / s.SUITE / "suite.yaml").read_text()
    for banned in ("ACME", "Acme", "lorem", "John Doe", "Jane Doe"):
        assert banned not in text
    assert yaml.safe_load(text)["suite"] == s.SUITE


def test_changing_a_threshold_is_refused(tmp_path) -> None:  # type: ignore[no-untyped-def]
    data = yaml.safe_load((s.ROOT / s.SUITE / "suite.yaml").read_text())
    data["thresholds"]["entity_accuracy"] = 0.5
    p = tmp_path / "suite.yaml"
    p.write_text(yaml.safe_dump(data))
    try:
        s.load(p)
    except s.ThresholdsChanged:
        return
    raise AssertionError("a changed threshold must be refused")
