"""A-05-T55 (TASK-6112; A-05 F9; DEC-2710): mode `ebp_form5500` on the section drafter (spec v12).

Row acceptance: "The mode reads every Schedule H line with a verified field citation and proposes,
never records, the Note 8 classification." The citation half is the drafter's verifier (every
value needs a verified citation or is dropped, A-04-T11) and the eval case
`northwind_ebp_form5500_part_iv`; here the mode runs on its own prompt, which classifies nothing,
and its mapping hands code's differences as facts.
"""

from __future__ import annotations

from decimal import Decimal

from abacus.ai_gateway.prompts import prompt
from abacus.modules.agents.section_sources import mode_mapping
from abacus.modules.agents.specs._specs import SPECS
from abacus.modules.assurance.ebp_form5500_mode import difference_facts


def test_ebp_form5500_runs_on_its_own_prompt_in_spec_version_12() -> None:
    spec: dict[str, object] = SPECS["workpapers.section_drafter"]
    modes = spec["modes"]
    version = spec["version"]
    assert isinstance(version, int) and version >= 12
    assert isinstance(modes, dict)
    assert modes["ebp_form5500"]["prompt"] == "workpapers.section_draft.ebp_form5500@v1"


def test_the_prompt_never_ties_classifies_or_records() -> None:
    text = prompt("workpapers.section_draft.ebp_form5500@v1").text
    assert "Never add, subtract, total or compare amounts" in text
    assert "a person on the team classifies every difference" in text
    assert "classify, record" in text
    assert "<untrusted>" in text


def test_code_s_differences_reach_the_model_as_named_facts() -> None:
    facts = dict(difference_facts([("1b(2)", Decimal("48600.00"))], Decimal("33540.00")))
    assert facts["diff.1b(2)"] == {"t": "decimal", "v": "48600.00"}
    assert facts["late_deposits_4a"] == {"t": "decimal", "v": "33540.00"}


def test_the_mapping_is_registered() -> None:
    import abacus.modules.assurance.api

    assert abacus.modules.assurance.api is not None
    assert mode_mapping("ebp_form5500") is not None
