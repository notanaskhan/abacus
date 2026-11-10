"""T-04-T19: the tax tools on C17 (SPEC-649; DEC-3211). Shapes the runtime relies on; the
consent refusal, masking and scope pinning are the runtime's (P-10-T22) and are exercised through
it in the integration suite."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
import yaml

from abacus.modules.agents.tools.registry import registered_tools
from abacus.modules.identity.api import AgentContext
from abacus.modules.tax import tools  # registers at import
from abacus.modules.tax.worksheet_review import WORKSHEET

ROOT = Path(__file__).resolve().parents[4]
PROMPTS = ROOT / "backend/src/abacus/ai_gateway/prompts"

READS = (
    "tax.read_return",
    "tax.list_documents",
    "tax.read_worksheet",
    "tax.read_pass_through_activity",
    "tax.read_prior_year",
)
COMPUTES = (
    "tax.compare_years",
    "tax.compute_pass_through_facts",
    "tax.compute_residency_facts",
    "tax.compute_state_allocation",
)
PROPOSES = (
    "tax.propose_field_changes",
    "tax.propose_pass_through_treatments",
    "tax.propose_residency",
)
ALL = READS + COMPUTES + PROPOSES


def _agent_rule(action: str) -> str:
    module = "agents" if action.startswith("proposal.") else "tax"
    matrix = yaml.safe_load(
        (ROOT / f"docs/architecture/permission-matrix/{module}.yaml").read_text()
    )
    for section in cast(dict[str, object], matrix).values():
        if isinstance(section, dict) and action in section:
            cells = cast(dict[str, dict[str, object]], section)[action]
            return str(cells.get("agent"))
    raise AssertionError(f"{action} is not in the {module} matrix")


def test_ac1_every_tool_is_registered_with_its_kind() -> None:
    found = registered_tools()
    for name in ALL:
        assert name in found, name
    assert {found[n].kind for n in READS} == {"read"}
    assert {found[n].kind for n in COMPUTES} == {"compute"}
    assert {found[n].kind for n in PROPOSES} == {"propose"}


@pytest.mark.parametrize("name", ALL)
def test_ac1_each_tool_carries_tax_return_information(name: str) -> None:
    """Consent is checked before the read for every `tri` tool (the runtime's C19 gate)."""
    assert registered_tools()[name].data_class == "tri"


@pytest.mark.parametrize("name", ALL)
def test_each_description_is_a_registry_prompt(name: str) -> None:
    assert registered_tools()[name].description == f"tool.{name}@v1"
    assert (PROMPTS / f"tool.{name}" / "v1.txt").read_text().strip()


@pytest.mark.parametrize("name", ALL)
def test_each_action_is_the_agents_task_scope(name: str) -> None:
    assert _agent_rule(registered_tools()[name].action) == "task_scope"


@pytest.mark.parametrize("name", PROPOSES)
def test_ac3_propose_tools_answer_a_proposal_never_a_value(name: str) -> None:
    out = registered_tools()[name].output_model
    assert set(out.model_fields) == {"proposal_id", "state", "row_count"}


@pytest.mark.parametrize("name", PROPOSES)
def test_propose_tools_pin_the_taxpayer_and_year(name: str) -> None:
    tool = registered_tools()[name]
    assert callable(getattr(tool.input_model, "tool_targets", None))


def test_ac1_tool_targets_name_the_7216_subject() -> None:
    entity = uuid4()
    args = tools.ResidencyProposalIn(
        client_entity_id=entity, tax_year=2025, determination_id=uuid4(), option="part_year"
    )

    engagement = uuid4()
    agent = cast("AgentContext", SimpleNamespace(engagement_id=engagement))  # reads one field
    targets = args.tool_targets(agent)
    assert targets.engagement_ids == (engagement,)
    assert [(s.entity_id, s.tax_year) for s in targets.tri_subjects] == [(entity, 2025)]


def test_field_change_rows_target_the_worksheet_the_applier_reads() -> None:
    """T-04-T15's `apply_field_proposal` reads `field_ref.target_type == return_worksheet`."""
    from abacus.modules.agents.proposal_slots import check_suggestion_target

    check_suggestion_target(WORKSHEET)


def test_no_tool_name_holds_a_digit() -> None:
    assert not [
        n for n in registered_tools() if n.startswith("tax.") and any(c.isdigit() for c in n)
    ]
