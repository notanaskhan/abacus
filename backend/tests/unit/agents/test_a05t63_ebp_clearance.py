"""A-05-T63 (TASK-6223; DEC-2818): the EBP modes' clearance path.

Row acceptance: "A signed passing run exists for every EBP mode, or the modes stay synthetic-only
with the gap recorded in the decision log." Here: the drafter's `client_data` is `cleared` only
when every mode is recorded in `clearance.yaml` from a signed report that exists, and the gap is
recorded while it isn't.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml

from abacus.modules.agents.section_draft import EBP_MODES
from abacus.modules.agents.specs._specs import SPECS

REPO = Path(__file__).resolve().parents[4]
CLEARANCE = REPO / "evals" / "workpapers_section_drafter" / "clearance.yaml"
EBP_AND_RELATED = EBP_MODES | {"related_parties"}


def _records() -> dict[str, dict[str, object]]:
    data = cast(dict[str, object], yaml.safe_load(CLEARANCE.read_text()))
    assert data["agent"] == "workpapers.section_drafter"
    return cast(dict[str, dict[str, object]], data.get("modes") or {})


def test_every_ebp_mode_is_on_the_drafter() -> None:
    modes = cast(dict[str, object], SPECS["workpapers.section_drafter"]["modes"])
    assert set(modes) >= EBP_AND_RELATED


def test_client_data_is_cleared_only_with_every_mode_recorded() -> None:
    spec = SPECS["workpapers.section_drafter"]
    modes = set(cast(dict[str, object], spec["modes"]))
    recorded = set(_records())
    if spec["client_data"] == "cleared":
        assert modes <= recorded, sorted(modes - recorded)
    else:
        assert spec["client_data"] == "none"


def test_each_record_names_a_signed_passing_bedrock_report_that_exists() -> None:
    for mode, record in _records().items():
        report = REPO / str(record["report"])
        assert report.is_file(), mode
        assert str(record["route"]) == "bedrock", mode
        for key in ("sha256", "signature", "recorded_by", "recorded_on"):
            assert record.get(key), (mode, key)


def test_while_uncleared_the_gap_is_recorded() -> None:
    if SPECS["workpapers.section_drafter"]["client_data"] == "cleared":
        return
    log = (REPO / "docs" / "product" / "decision-log.md").read_text()
    assert "| DEC-2818 |" in log and "synthetic-only" in log
    assert (REPO / "docs" / "operations" / "section-drafter" / "ebp-clearance.md").is_file()
