"""A-04-T23 (TASK-3009; A-04 §3.2 AC2.1, AC2.2; DEC-2059): the risk_narrative mode.

Row acceptance: "The Northwind draft cites 9 sources, prepopulates both presumed risks exactly,
raises PBC GAP flags only, and shows reserved actions absent 1.0." The citations and reserved-
action metric are the suite's (fake model); here: the mode's own prompt, its mapping and preparer,
the presumed risks code inserts (management override never rebuttable), and that only this mode
may raise a flag, of kind pbc_gap only.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

import abacus.modules.assurance.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the mode slots
from abacus.modules.agents.handoff import DraftedFlag, SectionDraft
from abacus.modules.agents.section_draft import DRAFTER, mode_call
from abacus.modules.agents.section_sources import FLAG_MODES, mode_mapping, mode_preparer
from abacus.modules.agents.spec import spec
from abacus.modules.assurance import draft_mappings, risks


def test_ac2_1_the_mode_has_its_own_prompt_mapping_and_preparer() -> None:
    prompt, _ = mode_call(spec(DRAFTER), "risk_narrative")
    assert prompt == "workpapers.section_draft.risk_narrative@v1"
    assert mode_mapping("risk_narrative") is draft_mappings.risk_narrative_inputs
    assert mode_preparer("risk_narrative") is risks.presumed_preparer


def test_ac2_1_code_prepopulates_both_presumptions_exactly() -> None:
    kinds = [p.presumption_kind for p in risks._PRESUMED]  # pyright: ignore[reportPrivateUsage]
    assert kinds == ["management_override", "revenue_recognition"]
    override = risks._PRESUMED[0]  # pyright: ignore[reportPrivateUsage]
    assert (override.level, override.inherent_risk, override.control_risk) == (
        "financial_statement",
        "high",
        "max",
    )
    assert risks.PRESUMED_TARGET == "risk_assessment.presumed_fraud_risks"


def test_ac2_2_only_risk_narrative_raises_flags_and_only_pbc_gap() -> None:
    assert frozenset({"risk_narrative"}) == FLAG_MODES
    with pytest.raises(ValidationError):
        DraftedFlag.model_validate(
            {
                "cell": "main!B4",
                "kind": "scope_limitation",
                "text": "x",
                "citations": [{"step": "S1", "quote": "q"}],
            }
        )
    with pytest.raises(ValidationError):  # a flag is always cited
        DraftedFlag.model_validate({"cell": "main!B4", "text": "x", "citations": []})
    draft = SectionDraft.model_validate(
        {
            "flags": [
                {
                    "cell": "main!B4",
                    "text": "The trust report is not in the PBC.",
                    "citations": [{"step": "S1", "quote": "Obtain the trust report"}],
                }
            ]
        }
    )
    assert draft.flags[0].kind == "pbc_gap"


def test_ac2_2_the_prompt_never_offers_to_rebut_management_override() -> None:
    from pathlib import Path

    text = (
        Path(risks.__file__).parents[2]
        / "ai_gateway"
        / "prompts"
        / "workpapers.section_draft.risk_narrative"
        / "v1.txt"
    ).read_text(encoding="utf-8")
    assert "Never propose removing or rebutting management override" in text
    assert "never call it a scope limitation" in text
