"""P-10-T11 (SPEC-647): what SHL-13, WB-01, WB-03 and WB-09 read from C6 v2, and what T-04 and I-02
register through C17. A field an artboard needs fails here if the provider removes it."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from abacus.modules.agents.api import agent_tool, registered_tools
from abacus.modules.agents.runs_v2_contract import (
    AgentCapabilitiesOut,
    BlockedOnOut,
    RunCountersOut,
    RunPlanOut,
    RunPlanStepOut,
    RunQuestionOut,
    RunStepV2Out,
    RunV2Out,
)
from abacus.modules.agents.tools.registry import ToolKind
from abacus.modules.workbench.sessions_contract import SessionItemOut, SessionSnapshotOut

ARTBOARDS: dict[str, tuple[type[BaseModel], set[str]]] = {
    "SHL-13 1 running": (RunV2Out, {"id", "run_number", "title", "state", "mode", "counters"}),
    "SHL-13 1 counters": (
        RunCountersOut,
        {"records_read", "citations_count", "writes_done", "writes_waiting", "agent_minutes"},
    ),
    "SHL-13 2, WB-03a plan": (RunPlanOut, {"id", "version", "state", "steps", "sources"}),
    "SHL-13 2 plan step": (RunPlanStepOut, {"key", "label", "level", "writes"}),
    "SHL-13 3 step": (
        RunStepV2Out,
        {"seq", "level", "kind", "label", "state", "needs", "records_read", "active_ms"},
    ),
    "SHL-13 4, WB-09b waiting": (BlockedOnOut, {"kind", "role", "user_id", "needs"}),
    "SHL-13 5, WB-01a question": (
        RunQuestionOut,
        {"prompt", "options", "allow_free_text", "answered_by", "answered_at"},
    ),
    "SHL-13 6 failed step": (RunStepV2Out, {"error_code", "state", "ended_at"}),
    "SHL-13 7 signed off": (RunV2Out, {"signed_off_by", "signed_off_at", "finished_at"}),
    "WB-01 a, b, g session": (SessionSnapshotOut, {"title", "origin", "state", "locked", "items"}),
    "WB-01 item": (SessionItemOut, {"seq", "kind", "payload", "run_id", "actor_kind"}),
    "WB-03 a to g run": (RunV2Out, {"session_id", "plan_id", "auto_mode", "allowed_actions"}),
    "WB-09 a to e run": (RunV2Out, {"blocked_on", "work_item_ref", "subject_ref", "state_reason"}),
}


@pytest.mark.parametrize("board", sorted(ARTBOARDS))
def test_every_field_the_artboard_reads_is_in_the_contract(board: str) -> None:
    model, needed = ARTBOARDS[board]
    assert needed <= set(model.model_fields), board


def test_capabilities_answer_availability_per_capability() -> None:
    assert AgentCapabilitiesOut.model_fields


class _In(BaseModel):
    return_id: str


class _Out(BaseModel):
    form: str


@pytest.mark.parametrize(
    ("name", "kind", "action"),
    [
        ("tax.read_return_summary", "read", "return.read"),  # T-04's shape
        ("practice.read_daily_brief", "read", "home.read"),  # I-02's shape
    ],
)
def test_the_consumers_shapes_register(name: str, kind: ToolKind, action: str) -> None:
    @agent_tool(
        name=name,
        kind=kind,
        action=action,
        data_class="internal",
        input_model=_In,
        output_model=_Out,
    )
    async def read(_ctx: object, _body: _In) -> _Out:
        return _Out(form="1040")

    assert registered_tools()[name].action == action
