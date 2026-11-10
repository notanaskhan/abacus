"""A-05-T56 (TASK-6113; A-05 F11; DEC-2711): mode `related_parties` (spec v13).

Row acceptance: "Peakline Freight LLC is proposed with the Feb 12, 2026 minutes reference, and the
output contains no director name." The eval case `granite_peak_related_parties_peakline` holds
both (its `forbidden` list carries the director's name and any conclusion); here the mode's own
prompt forbids a person's name and a conclusion, and its mapping is registered.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from abacus.ai_gateway.prompts import prompt
from abacus.modules.agents.section_sources import mode_mapping
from abacus.modules.agents.specs._specs import SPECS

REPO = Path(__file__).resolve().parents[4]


def test_related_parties_runs_on_its_own_prompt_in_spec_version_13() -> None:
    spec: dict[str, object] = SPECS["workpapers.section_drafter"]
    version = spec["version"]
    assert isinstance(version, int) and version >= 13
    modes = spec["modes"]
    assert isinstance(modes, dict)
    assert modes["related_parties"]["prompt"] == "workpapers.section_draft.related_parties@v1"


def test_the_prompt_names_no_person_and_concludes_nothing() -> None:
    text = prompt("workpapers.section_draft.related_parties@v1").text
    assert "Never write the name of a person from the minutes or the roster" in text
    assert "never conclude" in text
    assert "management should\nconfirm each one" in text
    assert "<untrusted>" in text


def test_the_peakline_case_forbids_the_director_s_name() -> None:
    suite = yaml.safe_load((REPO / "evals/workpapers_section_drafter/suite.yaml").read_text())
    case = next(c for c in suite["cases"] if c["id"] == "granite_peak_related_parties_peakline")
    assert case["labels"]["values"]["B2"] == "Peakline Freight LLC"
    assert "Avery Lindqvist" in case["labels"]["forbidden"]
    drafted = " ".join(c["text"] for c in case["fake_answer"]["cells"])
    assert "Avery Lindqvist" not in drafted
    # names the source without a figure the cited quote doesn't show (C2 number provenance)
    assert "in the board minutes" in drafted


def test_the_mapping_is_registered() -> None:
    import abacus.modules.assurance.api

    assert abacus.modules.assurance.api is not None
    assert mode_mapping("related_parties") is not None
