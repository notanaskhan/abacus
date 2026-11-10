"""P-10-T25 (TASK-6515; SPEC-647 AC-H1, AC-H2, AC-H3, AC-H5; DEC-3115): the loop harness.

Row acceptance: "A trajectory repeating an identical call stops with max_repeat, an uncited number
is marked Unsupported and never emitted as fact, and active_ms excludes waits."
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from decimal import Decimal

import pytest

from abacus.modules.agents import harness as h
from abacus.modules.agents.blocks import Fact

pytestmark = pytest.mark.asyncio
LIMITS = h.Limits(
    max_steps=10, max_seconds=600, max_cost_usd=Decimal("1.00"), max_tool_calls=8,
    max_repeat_identical_calls=3,
)  # fmt: skip


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class Scripted:
    """A FakeModel trajectory: each turn answers the next scripted result."""

    def __init__(self, clock: Clock, turns: list[h.TurnResult], turn_s: float = 1.0) -> None:
        self.clock, self.turns, self.turn_s = clock, list(turns), turn_s
        self.tools: list[str] = []

    async def turn(self, history: tuple[Mapping[str, object], ...]) -> h.TurnResult:
        del history
        result = self.turns.pop(0)
        self.clock.now += self.turn_s + result.waited_ms / 1000
        return result

    async def tool(self, request: h.ToolRequest) -> h.ToolResult:
        self.tools.append(request.name)
        self.clock.now += 0.5
        return h.ToolResult(request.name, True, records_read=3)


def _list_items() -> h.TurnResult:
    call = h.ToolRequest("t", "requests.list_items", {"engagement_id": "e1", "status": "open"})
    return h.TurnResult("tool_calls", Decimal("0.01"), (call,))


async def test_ac_h1_an_identical_third_call_stops_with_max_repeat() -> None:
    clock = Clock()
    ports = Scripted(clock, [_list_items(), _list_items(), _list_items()])
    out = await h.run_step(ports, LIMITS, facts={}, citations=set(), first_turn={}, clock=clock)
    assert (out.status, out.failure) == ("failed", "max_repeat")
    assert ports.tools == ["requests.list_items", "requests.list_items"]  # the third never ran


async def test_ac_h2_an_uncited_number_is_unsupported_and_never_a_fact() -> None:
    clock = Clock()
    blocks = {
        "version": 1,
        "parts": [
            {
                "kind": "p",
                "segments": [{"kind": "text", "text": "Deferrals of $48,600 were late."}],
            },
            {
                "kind": "p",
                "segments": [
                    {"kind": "fact", "fact_id": "late"},
                    {"kind": "text", "text": " remittances."},
                ],
            },
        ],
    }
    ports = Scripted(clock, [h.TurnResult("ok", Decimal("0.02"), output={"blocks": blocks})])
    facts = {"late": Fact(id="late", kind="count", value="1", basis="remittance test")}
    out = await h.run_step(ports, LIMITS, facts=facts, citations=set(), first_turn={}, clock=clock)
    assert out.status == "completed" and out.blocks is not None
    first = out.blocks["parts"][0]  # type: ignore[index]  # an AgentBlocks payload
    assert first == {"kind": "p", "segments": [{"kind": "text", "text": h.UNSUPPORTED}]}
    assert out.unsupported == (h.UnsupportedPart(0, "free_number"),)


async def test_ac_h3_an_unverified_citation_is_not_shown_as_fact() -> None:
    clock = Clock()
    cite = str(uuid.uuid4())
    blocks = {
        "version": 1,
        "parts": [{"kind": "p", "segments": [{"kind": "cite", "citation_id": cite, "n": 1}]}],
    }
    ports = Scripted(clock, [h.TurnResult("ok", Decimal("0"), output={"blocks": blocks})])
    out = await h.run_step(ports, LIMITS, facts={}, citations=set(), first_turn={}, clock=clock)
    assert out.unsupported == (h.UnsupportedPart(0, "unknown_citation"),)


async def test_ac_h5_active_ms_excludes_waits() -> None:
    clock = Clock()
    waited = h.TurnResult(
        "tool_calls",
        Decimal("0"),
        (h.ToolRequest("t", "requests.read_item", {"id": "1"}),),
        waited_ms=30_000,
    )
    ports = Scripted(clock, [waited, h.TurnResult("ok", Decimal("0"), output={})])
    out = await h.run_step(ports, LIMITS, facts={}, citations=set(), first_turn={}, clock=clock)
    # two 1 s turns and one 0.5 s tool call; the 30 s admission wait is not counted
    assert out.active_ms == 2500


async def test_questions_and_plans_are_handed_back_never_acted_on() -> None:
    clock = Clock()
    question = {"text": "Which population should eligibility testing start from?"}
    ports = Scripted(clock, [h.TurnResult("ok", Decimal("0"), output={"question": question})])
    out = await h.run_step(ports, LIMITS, facts={}, citations=set(), first_turn={}, clock=clock)
    assert (out.status, out.question) == ("needs_input", question)


async def test_an_escalated_turn_goes_to_needs_input() -> None:
    clock = Clock()
    ports = Scripted(clock, [h.TurnResult("escalated", Decimal("0"), failure="schema_invalid")])
    out = await h.run_step(ports, LIMITS, facts={}, citations=set(), first_turn={}, clock=clock)
    assert (out.status, out.failure) == ("needs_input", "schema_invalid")


async def test_the_cost_and_turn_limits_stop_the_step() -> None:
    clock = Clock()
    dear = h.TurnResult("tool_calls", Decimal("0.80"), (h.ToolRequest("t", "a.b", {"n": 1}),))
    dearer = h.TurnResult("tool_calls", Decimal("0.80"), (h.ToolRequest("t", "a.b", {"n": 2}),))
    out = await h.run_step(
        Scripted(clock, [dear, dearer]),
        LIMITS,
        facts={},
        citations=set(),
        first_turn={},
        clock=clock,
    )
    assert out.failure == "max_cost"
