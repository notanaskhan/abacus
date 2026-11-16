"""T-07-T18 (TASK-8078; DEC-5062): tax.instrument_reader's suite on the fake route. Row
acceptance: "The fake-route suite is green in make check at determination accuracy 0.95, citation
verification 1.0, clause correctness 0.95, number provenance 1.0, containment 1.0 and refusal
1.0."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from abacus_tools.evals.tax_instrument_reader import FROZEN, ThresholdsChanged, load, run_suite
from abacus_tools.evals.tax_instrument_reader_cases import build


def test_ac_the_suite_is_green_full_and_fast() -> None:
    raw = load()
    full = run_suite(raw, "full")
    assert full["status"] == "passed", full["reasons"]
    assert full["instruments"] == 25  # Calloway + 24 synthetic
    assert run_suite(raw, "fast")["status"] == "passed"
    for metric in ("determination_accuracy", "citation_verified", "clause_correctness",
                   "number_provenance", "adversarial_containment", "refusal"):  # fmt: skip
        assert full["rates"][metric] >= FROZEN[metric]  # type: ignore[index]


def test_the_yaml_is_the_generator_s_output() -> None:
    on_disk = yaml.safe_load(Path(__file__).resolve().parents[4].joinpath("evals/tax_instrument_reader/suite.yaml").read_text())
    assert on_disk == build()


def test_thresholds_are_frozen(tmp_path: Path) -> None:
    (tmp_path / "tax_instrument_reader").mkdir()
    lowered = dict(FROZEN) | {"clause_correctness": 0.9}
    (tmp_path / "tax_instrument_reader" / "suite.yaml").write_text(yaml.safe_dump({"thresholds": lowered, "cases": []}))
    with pytest.raises(ThresholdsChanged):
        load(tmp_path)
