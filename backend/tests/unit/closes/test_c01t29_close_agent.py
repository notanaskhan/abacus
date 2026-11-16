"""C-01-T29: `close.agent` v1 (red). Every model sentence carrying a number references a code
fact, citations verify before display, options are code's, and any tool outside the
capability's scope is refused `out_of_scope`."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from abacus.ai_gateway._eval_suites import EVAL_SUITE_MODES, EVAL_SUITES
from abacus.modules.agents.api import spec_v2
from abacus.modules.agents.tools.registry import registered_tools
from abacus.modules.closes import agent

PROMPTS = Path(__file__).parents[3] / "src/abacus/ai_gateway/prompts"
FACTS = [
    agent.FactIn(id=k, kind="money", value=v, basis="code")
    for k, v in {
        "procedures_done": "9",
        "open_issues": "7",
        "gross": "73166.90",
        "fees": "1684.54",
        "net": "71482.36",
        "amount": "3200.00",
        "usual": "640.00",
        "change_pct": "400.0",
    }.items()
]


def _given(mode: agent.Mode, **kw: object) -> agent.CloseAgentInput:
    return agent.CloseAgentInput(mode=mode, close_id=uuid.uuid4(), facts=FACTS, **kw)  # type: ignore[arg-type] -- the optional fields


@pytest.mark.parametrize("mode", agent.MODES)
def test_ac_every_fake_response_settles_with_numbers_only_as_facts(mode: agent.Mode) -> None:
    given = _given(mode, options=["5010", "6100"] if mode == "aje" else [])
    settled = agent.settle(given, agent.FAKE_RESPONSES[mode])
    assert settled.mode == mode


def test_ac_a_free_number_in_prose_is_refused() -> None:
    answer = agent.CloseAgentOutput(
        blocks={"version": 1, "parts": [{"kind": "p", "segments": [
            {"kind": "text", "text": "The payment is $3,200.00, five times usual."}]}]},
    )  # fmt: skip
    with pytest.raises(agent.OutputRefused) as refused:
        agent.settle(_given("bank_rec"), answer)
    assert refused.value.facts["reason"] == "number_in_text" or refused.value.facts["reason"]


def test_ac_an_unknown_fact_or_citation_is_refused() -> None:
    unknown = agent.CloseAgentOutput(
        blocks={"version": 1, "parts": [{"kind": "p", "segments": [
            {"kind": "text", "text": "Total "}, {"kind": "fact", "fact_id": "made_up"}]}]},
    )  # fmt: skip
    with pytest.raises(agent.OutputRefused):
        agent.settle(_given("intake"), unknown)
    cited = agent.CloseAgentOutput(
        blocks={"version": 1, "parts": [{"kind": "p", "segments": [
            {"kind": "text", "text": "See the statement"},
            {"kind": "cite", "citation_id": str(uuid.uuid4()), "n": 1}]}]},
    )  # fmt: skip
    with pytest.raises(agent.OutputRefused):
        agent.settle(_given("intake"), cited)


def test_the_aje_option_must_be_one_code_offered() -> None:
    given = _given("aje", options=["6100"])
    with pytest.raises(agent.OutputRefused):
        agent.settle(given, agent.FAKE_RESPONSES["aje"])  # chose 5010, not offered


def test_ac_a_tool_outside_the_scope_is_refused_out_of_scope() -> None:
    assert agent.scoped_tool("close.reconcile") == "close.reconcile"
    with pytest.raises(agent.OutOfScope) as refused:
        agent.scoped_tool("adjustments.propose_entry")
    assert refused.value.code == "out_of_scope"


def test_the_spec_binds_the_tools_scope_prompts_and_suite() -> None:
    spec = spec_v2(agent.CAPABILITY)
    assert set(spec.tools.names()) == set(agent.TOOLS)
    assert spec.task_scope == agent.TASK_SCOPE
    tools = registered_tools()
    assert all(tools[n].action in spec.task_scope for n in spec.tools.names())
    assert "tri" not in spec.data_classes
    assert EVAL_SUITES[agent.CAPABILITY][0] == agent.PROMPTS["run"]
    assert set(EVAL_SUITE_MODES[agent.CAPABILITY]) == {
        agent.PROMPTS[m] for m in ("intake", "bank_rec", "aje")
    }
    for prompt in agent.PROMPTS.values():
        name, _, version = prompt.partition("@")
        assert (PROMPTS / name / f"{version}.txt").is_file()
    assert agent.run_plan_provider() == "closes.close_run"
