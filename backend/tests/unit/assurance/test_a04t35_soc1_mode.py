"""A-04-T35 (TASK-3267; DEC-2247): mode `soc1` (SOC 1 reader and CUEC mapper).

The mode has its own prompt on the one section-drafter spec (version 10), its own mapping
registered, and the prompt never asks the model to compute a gap or to rely.
"""

from __future__ import annotations

from abacus.ai_gateway.prompts import prompt
from abacus.modules.agents.specs._specs import SPECS


def test_soc1_runs_on_its_own_prompt_in_spec_version_10() -> None:
    spec: dict[str, object] = SPECS["workpapers.section_drafter"]
    modes = spec["modes"]
    assert spec["version"] == 10
    assert (
        isinstance(modes, dict) and modes["soc1"]["prompt"] == "workpapers.section_draft.soc1@v1"
    )


def test_the_prompt_keeps_reliance_and_the_gap_away_from_the_model() -> None:
    text = prompt("workpapers.section_draft.soc1@v1").text
    assert "engagement partner alone decides whether to rely" in text
    assert "Never compute a" in text and "code does that" in text
    assert "<untrusted>" in text


def test_the_mapping_is_registered() -> None:
    import abacus.modules.assurance.api  # registers
    from abacus.modules.agents.section_sources import mode_mapping

    assert abacus.modules.assurance.api is not None
    assert mode_mapping("soc1") is not None
