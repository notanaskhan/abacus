"""K-03-T14 (TASK-8908; K-03 §6; SPEC-721 §3; ADR-078, ADR-079): `workpapers.column_filler`'s
suite skeleton, frozen before any prompt work.

Row acceptance: "suite.yaml with exception recall >= 0.97, accuracy >= 0.90, needs-input recall
>= 0.95 and options, citations and reason at 1.0 merges ... before any column_filler prompt work
starts." Here: the file's thresholds are FROZEN; the 40 SURL seed rows are there with the
scenario's counts (31 / 8 / 1); every label follows the SURL rule from the invoice's own facts;
there are at least 12 true exceptions; each grader catches its seeded defect; the recorded run
passes and the naive baseline fails; a changed threshold is refused; no prompt exists yet.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

import pytest
import yaml

from abacus_tools.evals import column_filler as cf

SUITE_FILE = cf.ROOT / cf.SUITE / "suite.yaml"
PROMPTS = Path(cf.__file__).resolve().parents[2] / "abacus" / "ai_gateway" / "prompts"


def test_the_thresholds_are_the_frozen_ones() -> None:
    raw = yaml.safe_load(SUITE_FILE.read_text(encoding="utf-8"))
    assert raw["thresholds"] == dict(cf.FROZEN)
    assert cf.FROZEN["exception_recall"] == 0.97
    assert cf.FROZEN["accuracy"] == 0.90
    assert cf.FROZEN["needs_input_recall"] == 0.95
    for name in ("output_in_options", "citations_verified", "first_person_reason"):
        assert cf.FROZEN[name] == 1.0, name


def test_a_changed_threshold_is_refused(tmp_path: Path) -> None:
    raw = yaml.safe_load(SUITE_FILE.read_text(encoding="utf-8"))
    raw["thresholds"]["exception_recall"] = 0.9
    changed = tmp_path / "suite.yaml"
    changed.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(cf.ThresholdsChanged):
        cf.load(changed)


def test_the_forty_surl_seed_rows_foot_to_the_scenario() -> None:
    seed = [c for c in cf.load().cases if c.category == "seed"]
    assert [c.row_key for c in seed] == [f"SURL-{n:02d}" for n in range(1, 41)]
    assert Counter(c.expected for c in seed) == {
        "properly_excluded": 31, "properly_included": 8, "improperly_excluded": 1,
    }  # fmt: skip


def _rule(c: cf.Case) -> str:
    """The SURL rule, recomputed from the invoice text and the recorded month."""
    import re

    found = re.search(r"Invoice date (\w{3}) (\d+), (\d{4})", c.invoice_text)
    if found is None or "Service period:" not in c.invoice_text:
        return "needs_input"
    month = date(int(found.group(3)), 1, 1).replace(
        month=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
               "Dec"].index(found.group(1)) + 1, day=int(found.group(2)))  # fmt: skip
    if month > cf.PERIOD_END:
        return "properly_excluded"
    return "properly_included" if c.recorded_in.startswith("Jun AP") else "improperly_excluded"


def test_every_label_follows_the_surl_rule() -> None:
    for c in cf.load().cases:
        if c.category != "seeded":
            assert c.expected == _rule(c), c.id


def test_exception_recall_rests_on_at_least_twelve_true_exceptions() -> None:
    graded = [c for c in cf.load().cases if c.category != "seeded"]
    assert sum(c.expected == cf.EXCEPTION for c in graded) >= 12
    assert sum(c.expected == cf.NEEDS_INPUT for c in graded) >= 8


def test_each_grader_catches_its_seeded_defect_and_the_run_passes() -> None:
    result = cf.run(cf.load())
    assert result.seeded_caught and result.passed
    assert all(result.rates[n] >= cf.FROZEN[n] for n in cf.DANGEROUS)


def test_the_naive_baseline_fails_the_dangerous_classes() -> None:
    suite = cf.load()
    result = cf.run(suite, cf.naive_baseline(suite))
    assert not result.passed
    for name in ("exception_recall", "needs_input_recall", "citations_verified",
                 "first_person_reason", "number_provenance"):  # fmt: skip
        assert result.rates[name] < cf.FROZEN[name], name


def test_adversarial_rows_cover_the_file_and_the_firm_text() -> None:
    kinds = Counter(c.injected for c in cf.load().cases if c.category == "adversarial")
    assert kinds == {"file": 3, "firm_text": 3}


def test_no_column_filler_prompt_exists_before_the_suite() -> None:
    assert not (PROMPTS / "workpapers.column_filler").exists()
