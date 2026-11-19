"""T-06-T27 (TASK-8722; ADR-005, ADR-050; DEC-5716): every depth mode returns suggestions or
proposals only, never a reserved action; a TRI read without both consents fails consent_required
before any model call; model sentences carrying a number code did not compute are dropped."""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus.modules.tax.analyst_depth_modes import MODES, require_consents, settle
from abacus.modules.tax.analyst_modes import NEVER


def test_ac_every_mode_writes_a_suggestion_or_a_proposal_only() -> None:
    assert set(MODES) == {
        "asset_evidence", "sourcing_position", "provision_explainer", "time_study_allocation",
    }  # fmt: skip
    for spec in MODES.values():
        assert spec.write in ("suggestion.create", "proposal.create")
        assert spec.write not in NEVER
        assert spec.prompt.startswith("tax.return_analyst.") and spec.prompt.endswith("@v1")


@pytest.mark.parametrize("granted", [(), ("use",), ("ai_disclosure",)])
def test_ac_a_tri_read_without_both_consents_fails(granted: tuple[str, ...]) -> None:
    with pytest.raises(Exception) as refused:
        require_consents(granted)
    assert getattr(refused.value, "code", None) == "consent_required"
    require_consents(("use", "ai_disclosure"))


def test_ac_only_code_numbers_survive() -> None:
    out = settle(
        "provision_explainer",
        "The unclassified difference is 1,200. The rate is 31.4 percent.",
        [Decimal("1200")],
    )
    assert out.text == "The unclassified difference is 1,200."
    assert out.figures == (Decimal("1200"),)
