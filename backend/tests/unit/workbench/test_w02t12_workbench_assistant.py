"""W-02-T12 (TASK-7715; W-02 §6; DEC-4718): `workbench.assistant` v1.

Row acceptance: "Codegen accepts it; fast subset passes; no final verb or tri." The spec compiles
with the W-02 tools, `confidential` only, propose autonomy and plans required for writes; the turn
schema carries at most one of question, plan or notice; code refuses a turn naming a reserved verb
or an agent approver.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from abacus.modules.agents.api import spec_v2
from abacus.modules.workbench.assistant import (
    CAPABILITY,
    AssistantNotice,
    AssistantPlan,
    AssistantQuestion,
    AssistantTurn,
    check_turn,
)

NEVER = ("decide", "approve", "sign_off", "release", "send", "post", "export", "transmit",
         "adopt", "publish", "resolve", "accept", "reject")  # fmt: skip


def test_the_spec_compiles_with_the_w02_tools_and_never_tri() -> None:
    spec = spec_v2(CAPABILITY)
    assert spec.prompt == "workbench.assistant@v1"
    assert spec.autonomy == "propose" and spec.plan == "required_when_writes"
    assert "tri" not in spec.data_classes
    tools = [t for group in spec.tools.values() for t in group]  # type: ignore[union-attr]
    for name in (
        "tax.season_counts",
        "binders.read",
        "workpapers.read_section",
        "assurance.read_materiality",
        "files.propose_save",
        "files.save_approved",
    ):
        assert name in tools  # fmt: skip
    assert not any(verb in t.split(".")[-1] for t in tools for verb in NEVER)


def _plan(approver: str = "Hannah Leclerc") -> AssistantPlan:
    return AssistantPlan.model_validate(
        {
            "steps": [{"label": "Count the season's returns", "tool": "tax.season_counts"}],
            "reads": [{"source": "Tax returns", "count": 224}],
            "writes": [{"op": "save_file", "target": "TY2025 season.xlsx", "approver": approver}],
        }
    )


def test_a_turn_carries_at_most_one_of_question_plan_or_notice() -> None:
    question = AssistantQuestion.model_validate(
        {"steps": [{"q": "Which offices?", "options": [{"key": "all", "title": "All three"},
                                                       {"key": "chicago", "title": "Chicago"}]}]}
    )  # fmt: skip
    notice = AssistantNotice(code="nothing_to_do", text="There is nothing to change.")
    with pytest.raises(ValidationError):
        AssistantTurn(question=question, plan=_plan())
    with pytest.raises(ValidationError):
        AssistantTurn()
    assert AssistantTurn(notice=notice).notice == notice


def test_code_refuses_a_reserved_verb_or_an_agent_approver() -> None:
    assert check_turn(AssistantTurn(plan=_plan())) is None
    assert check_turn(AssistantTurn(plan=_plan("Accrued Agent"))) == "agent_cannot_approve"
    sneaky = AssistantTurn(
        notice=AssistantNotice(code="nothing_to_do", text="I approved the plan for you.")
    )
    assert check_turn(sneaky) == "reserved_action_named"
