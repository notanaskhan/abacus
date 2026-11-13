"""W-02-T15 (TASK-7910; W-02 §4.4; SPEC-653 AC-L6, AC-A3, AC-Q*; DEC-4913, DEC-4914): the
session workflow v2 (red).

Row acceptance: "Recorded histories replay, a read-only turn never starts a child run and ends
with the code line, and a tool call outside the pinned client_scope returns out_of_scope."
"""

from __future__ import annotations

import asyncio
import inspect
import uuid
from types import SimpleNamespace

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.agents import session_turns
from abacus.modules.agents.harness import ToolRequest
from abacus.modules.workbench import session_turn_v2 as v2
from abacus.modules.workbench import session_workflow


def test_ac_the_workflow_branches_on_the_patch() -> None:
    """Guard: the v2 turn runs only behind `workflow.patched("w02-session-v2")`, so a v1 history
    replays on the v1 activity."""
    source = inspect.getsource(session_workflow.WorkbenchSessionWorkflow.run)
    assert 'workflow.patched("w02-session-v2")' in source
    assert '"workbench.session.turn_v2"' in source and '"workbench.session.turn"' in source


def test_ac_first_message_titles_the_session() -> None:
    body = "Pull together season progress for every office, with returns by status and binders"
    title = v2.first_title(body)
    assert len(title) <= v2.TITLE_CHARS
    assert body.startswith(title)
    assert not title.endswith(" ")
    assert v2.first_title("  Short   one ") == "Short one"


def test_ac_context_layer_is_codes_summary_lines() -> None:
    layer = v2.context_layer(
        [("Client record", "Northwind Robotics 401(k) Plan", ["PN 001 · plan year Jan 1–Dec 31"])]  # noqa: RUF001 -- the handoff's en dash
    )
    assert layer.startswith("Attached context")
    assert "Northwind Robotics 401(k) Plan" in layer and "PN 001" in layer
    assert v2.context_layer([]) == ""


def _turns(n: int) -> list[v2.PastItem]:
    out: list[v2.PastItem] = []
    for i in range(n):
        out.append(v2.PastItem(2 * i + 1, "user_message", {"body": f"q{i}"}))
        out.append(
            v2.PastItem(
                2 * i + 2,
                "agent_blocks",
                {"blocks": {"parts": [{"text": f"a{i}"}]}},
            )
        )
    return out


def test_ac_compaction_keeps_the_last_twelve_turns_whole() -> None:
    layer = v2.conversation_layer(_turns(15))
    assert "Earlier (3 turns, answers compacted):" in layer
    assert "Agent: a2" not in layer  # an older answer is dropped
    assert "Person: q0" in layer  # its question stays
    assert "Agent: a14" in layer and "Agent: a3" in layer
    assert v2.conversation_layer(_turns(15)) == layer  # deterministic


def test_ac_compaction_respects_the_budget() -> None:
    big = [v2.PastItem(i, "user_message", {"body": "x" * 2_000}) for i in range(1, 30)]
    assert len(v2.conversation_layer(big)) <= v2.BUDGET


def test_ac_edit_and_resend_names_the_replaced_message() -> None:
    request = v2.request_of("", "", "Use Denver too", 7)
    assert request.startswith("(This message replaces the person's message at item 7.)")


def test_ac_read_only_turn_ends_with_the_code_line() -> None:
    """Guard: a completed turn appends the `nothing_written` notice by code; a plan does not."""
    source = inspect.getsource(v2.turn_v2)
    assert 'if outcome.status == "completed":' in source
    assert "NOTHING_WRITTEN" in source
    assert v2.NOTHING_WRITTEN == "nothing_written"


class _Ports(session_turns.ReadOnlyPorts):
    def __init__(self, pinned: frozenset[str]) -> None:  # bypass the converse wiring
        self.offered = frozenset({"engagements.read"})
        self.pinned = pinned
        self.agent = SimpleNamespace(tenant=TenantContext(uuid.uuid4(), "agent", "run:1"))  # type: ignore[assignment] -- a stand-in agent


def test_ac_a_tool_call_outside_the_pinned_scope_is_out_of_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mine, theirs = str(uuid.uuid4()), str(uuid.uuid4())
    clients = {E_MINE: mine, E_THEIRS: theirs}

    async def client_of(_t: object, engagement: uuid.UUID) -> str:
        return clients[engagement]

    monkeypatch.setattr(session_turns, "client_of", client_of)
    ports = _Ports(frozenset({mine}))
    refused = asyncio.run(
        ports.tool(ToolRequest("t1", "engagements.read", {"engagement_id": str(E_THEIRS)}))
    )
    assert (refused.ok, refused.code) == (False, "out_of_scope")
    named = asyncio.run(ports.tool(ToolRequest("t2", "engagements.read", {"client_id": theirs})))
    assert named.code == "out_of_scope"


E_MINE = uuid.uuid4()
E_THEIRS = uuid.uuid4()


def test_ac_plans_off_withholds_the_plan() -> None:
    """Guard: `plans=False` ends a planning turn `plans_off` before any child run."""
    source = inspect.getsource(session_turns.run_session_turn)
    assert 'outcome.status == "plan_proposed" and not plans' in source
    assert '"plans_off"' in source
