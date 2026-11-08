"""A-05-T36 (TASK-3269; DEC-2249): mode `ebp_trust` on the section drafter (spec v11).

The mode runs on its own prompt, its mapping hands the model no figures to total, and the
prompt keeps certification evaluation and totals away from the model.
"""

from __future__ import annotations

from abacus.ai_gateway.prompts import prompt
from abacus.modules.agents.section_sources import mode_mapping
from abacus.modules.agents.specs._specs import SPECS


def test_ebp_trust_runs_on_its_own_prompt_in_spec_version_11() -> None:
    spec: dict[str, object] = SPECS["workpapers.section_drafter"]
    modes = spec["modes"]
    version = spec["version"]  # later modes bump the spec (v12: A-05-T55)
    assert isinstance(version, int) and version >= 11
    assert isinstance(modes, dict)
    assert modes["ebp_trust"]["prompt"] == "workpapers.section_draft.ebp_trust@v1"


def test_the_prompt_never_totals_or_evaluates_the_certification() -> None:
    text = prompt("workpapers.section_draft.ebp_trust@v1").text
    assert "Never add, subtract or total the lines" in text
    assert "do not say whether the\ncertification is sufficient" in text
    assert "<untrusted>" in text


def test_the_mapping_is_registered() -> None:
    import abacus.modules.assurance.api

    assert abacus.modules.assurance.api is not None
    assert mode_mapping("ebp_trust") is not None
