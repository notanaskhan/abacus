"""A-08-T23 (red): the section drafter's fieldwork modes. The spec loads, the modes write
suggestions only, and no tool reaches a reserved action."""

from __future__ import annotations

from pathlib import Path

from abacus.modules.agents.api import spec
from abacus.modules.agents.tools.registry import registered_tools
from abacus_tools.quality.tool_registry import import_agent_tools, load_matrix, problems

MODES = ("fieldwork_attribute", "flux_explain", "confirmation_reconcile")
TOOLS = {
    "sampling.read_selected_entry": ("read", "sample_set.read"),
    "ledger.counterparty_activity": ("compute", "trial_balance.read"),
    "assurance.propose_explanation": ("propose", "suggestion.create"),
    "assurance.propose_reconciliation": ("propose", "suggestion.create"),
}
PROMPTS = Path(__file__).parents[3] / "src/abacus/ai_gateway/prompts"


def test_ac_the_spec_validator_passes_with_the_three_modes() -> None:
    drafter = spec("workpapers.section_drafter")
    assert drafter.version == 15
    for mode in MODES:
        name, _, version = drafter.modes[mode].prompt.partition("@")
        assert (PROMPTS / name / f"{version}.txt").is_file()
    assert "respondent_text" in drafter.untrusted_inputs
    assert set(drafter.tools) == set(TOOLS)


def test_ac_the_modes_write_suggestions_only_and_no_reserved_action_is_reachable() -> None:
    import_agent_tools()
    tools = registered_tools()
    drafter = spec("workpapers.section_drafter")
    for name, (kind, action) in TOOLS.items():
        assert (tools[name].kind, tools[name].action) == (kind, action)
        assert action in drafter.task_scope
    writes = {tools[n].action for n in TOOLS if tools[n].kind in ("propose", "approved_write")}
    assert writes == {"suggestion.create"}
    assert problems(tools, load_matrix()) == []
