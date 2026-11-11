"""P-10-T40 (TASK-6803; SPEC-647 §3.3, §6; DEC-3403): `runtime.conformance` v1, the reference loop
capability, and the harness's first concrete ports.

Row acceptance: "The capability runs end to end on FakeModel and the direct route in the
evaluation account, and no firm-facing endpoint can start it."
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

import abacus.modules.agents.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers every tool
from abacus.ai_gateway import providers as p
from abacus.ai_gateway.prompts import registry as prompts
from abacus.modules.agents import conformance
from abacus.modules.agents.api import ToolCallIn
from abacus.modules.agents.conformance import (
    CAPABILITY,
    ConformanceOutput,
    ConversePorts,
    converse_tools,
    limits_of,
)
from abacus.modules.agents.harness import ToolRequest
from abacus.modules.agents.spec_v2 import TEST_ONLY, spec_problems, spec_v2
from abacus.modules.agents.tools.runtime import ToolOutcome
from abacus.modules.identity.api import AgentContext

SRC = Path(__file__).resolve().parents[3] / "src" / "abacus"


def test_the_spec_loads_as_a_loop_over_t28_and_t38_tools() -> None:
    spec = spec_v2(CAPABILITY)
    assert spec.shape == "loop" and spec.prompt == "runtime.conformance@v1"
    assert spec.client_data == "none" and spec.plan == "required_when_writes"
    assert set(spec.tools.propose) == {"files.propose_save"}
    assert set(spec.tools.approved_write) == {"files.save_approved"}
    assert len(spec.tools.read) == 13 and "ledger.read_tb" in spec.tools.read
    assert spec_problems(spec) == []


def test_it_is_test_only_and_no_route_names_it() -> None:
    assert CAPABILITY in TEST_ONLY
    for path in SRC.glob("modules/*/*.py"):
        if "route" in path.name or path.name.endswith("_contract.py"):
            assert CAPABILITY not in path.read_text(encoding="utf-8"), path
    assert CAPABILITY not in (SRC / "api" / "app.py").read_text(encoding="utf-8")


def test_its_prompt_and_every_tool_prompt_are_registered() -> None:
    registered = prompts()
    assert "runtime.conformance@v1" in registered
    tools = converse_tools(spec_v2(CAPABILITY))
    assert len(tools) == len(spec_v2(CAPABILITY).tools.names()) == 18
    for offered in tools:
        assert offered.spec.description in registered, offered.spec.name


def test_limits_come_from_the_spec() -> None:
    limits = limits_of(spec_v2(CAPABILITY))
    assert (limits.max_tool_calls, limits.max_repeat_identical_calls) == (20, 2)
    assert limits.max_cost_usd == Decimal("0.50")


def test_the_output_schema_holds_a_question_a_plan_or_blocks() -> None:
    asked = ConformanceOutput.model_validate(
        {"question": {"text": "Which returns?", "options": ["All TY2025", "Open only"]}}
    )
    assert asked.question is not None and asked.plan is None
    with pytest.raises(ValueError):
        ConformanceOutput.model_validate({"question": {"text": "x", "options": ["only one"]}})


class _Agent:
    agent_run_id = uuid.uuid4()
    engagement_id = uuid.uuid4()
    tenant = None


@pytest.mark.asyncio
async def test_the_ports_pair_tool_results_with_their_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, int]] = []

    async def fake_call_tool(agent: object, call: ToolCallIn) -> ToolOutcome:
        seen.append((call.name, call.attempt))
        return ToolOutcome(name=call.name, ok=True, result={"id": "x"}, active_ms=1)

    monkeypatch.setattr(conformance, "call_tool", fake_call_tool)
    ports = ConversePorts(
        cast(AgentContext, _Agent()), spec_v2(CAPABILITY), 1, "How many requests are open?"
    )
    assert ports.messages[0].role == "user"
    for request in (
        ToolRequest("t1", "requests.list_items", {}),
        ToolRequest("t2", "engagements.read", {}),
    ):
        result = await ports.tool(request)
        assert result.ok
    assert seen == [("requests.list_items", 1), ("engagements.read", 2)]
    ports._flush()  # pyright: ignore[reportPrivateUsage] -- the port's own flush under test
    last = ports.messages[-1]
    assert last.role == "user" and len(last.content) == 2
    assert all(isinstance(b, p.ToolResultBlock) for b in last.content)
