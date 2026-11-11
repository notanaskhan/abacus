"""P-10-T20 (TASK-6202; SPEC-647 AC-R8; DEC-2802): capability spec v2 and its codegen.

Row acceptance: "Codegen refuses a tool outside task_scope, an approved_write tool whose action is
not agent deny, tri without the consent registration, and a loop without max_tool_calls." The v1
specs load unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

# C19's consent checks: the v1 specs it loads beside v2 refuse to load without them.
import abacus.modules.organisations.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the consent checks
from abacus.modules.agents import spec as v1
from abacus.modules.agents import spec_v2
from abacus.modules.agents.spec_v2 import AgentSpecV2, ToolFacts, registry_problems, spec_problems
from abacus_tools.codegen import agent_specs_v2

MATRIX: Mapping[str, Mapping[str, object]] = {
    "evidence.read": {"agent": "task_scope"},
    "file.propose": {"agent": "task_scope"},
    "file.save": {"agent": "deny"},
    "request_item.read": {"agent": "task_scope"},
}


def _doc(**over: object) -> dict[str, Any]:  # Any: a test double
    doc: dict[str, Any] = {  # Any: a test double
        "id": "runtime.conformance",
        "version": 1,
        "purpose": "Prove the runtime end to end on synthetic data.",
        "shape": "loop",
        "prompt": "runtime.conformance@v1",
        "tier": "medium",
        "escalation_tier": "large",
        "input_schema": "SessionTurnInput",
        "output_schema": "AssistantTurn",
        "tools": {
            "read": ["evidence.search"],
            "propose": ["files.propose_save"],
            "approved_write": ["files.save_approved"],
        },
        "task_scope": ["evidence.read", "file.propose", "file.save"],
        "limits": {
            "max_output_tokens": 4000,
            "max_cost_usd": "0.60",
            "max_steps": 24,
            "max_seconds": 900,
            "max_tool_calls": 40,
            "max_repeat_identical_calls": 2,
        },
        "plan": "required_when_writes",
        "untrusted_inputs": ["tool_results.evidence"],
        "evaluation_suite": "evals/runtime_conformance",
        "work_class": "interactive",
        "routes": ["bedrock", "direct"],
    }
    doc.update(over)
    return doc


TOOLS = {
    "evidence.search": ToolFacts("read", "evidence.read"),
    "files.propose_save": ToolFacts("propose", "file.propose"),
    "files.save_approved": ToolFacts("approved_write", "file.save"),
}


Doc = dict[str, Any]  # Any: a spec document as JSON


def _registry(doc: Doc, tools: Mapping[str, ToolFacts] = TOOLS) -> list[str]:
    def cell(a: str) -> object:
        return MATRIX.get(a, {}).get("agent")

    return registry_problems(
        AgentSpecV2.model_validate(doc),
        tools,
        denied=lambda a: cell(a) == "deny",
        holdable=lambda a: cell(a) == "task_scope",
    )


def test_a_valid_loop_spec_has_no_problems() -> None:
    spec = AgentSpecV2.model_validate(_doc())
    assert spec_problems(spec, consents=lambda _p: True, holdable=lambda _a: True) == []
    assert _registry(_doc()) == []


def test_ac_r8_a_tool_outside_task_scope_is_refused() -> None:
    found = _registry(_doc(task_scope=["file.propose", "file.save"]))
    assert any("evidence.search" in f and "outside task_scope" in f for f in found)


def test_ac_r1_an_approved_write_tool_whose_action_is_not_agent_deny_is_refused() -> None:
    tools = {**TOOLS, "files.save_approved": ToolFacts("approved_write", "file.propose")}
    found = _registry(_doc(task_scope=["evidence.read", "file.propose"]), tools)
    assert any("must be agent: deny" in f for f in found)


def test_ac_r8_tri_without_the_consent_registration_is_refused() -> None:
    spec = AgentSpecV2.model_validate(_doc(data_classes=["confidential", "tri"]))
    found = spec_problems(spec, consents=lambda _p: False, holdable=lambda _a: True)
    assert any("tri" in f for f in found)
    assert spec_problems(spec, consents=lambda _p: True, holdable=lambda _a: True) == []


@pytest.mark.parametrize("missing", ["max_tool_calls", "max_repeat_identical_calls"])
def test_ac_r8_a_loop_without_its_call_limits_is_refused(missing: str) -> None:
    doc = _doc()
    doc["limits"] = {k: v for k, v in doc["limits"].items() if k != missing}
    found = spec_problems(
        AgentSpecV2.model_validate(doc), consents=lambda _p: True, holdable=lambda _a: True
    )
    assert any("max_tool_calls and max_repeat_identical_calls" in f for f in found)


def test_ac_r8_a_write_tool_without_a_plan_is_refused() -> None:
    found = spec_problems(
        AgentSpecV2.model_validate(_doc(plan="never")),
        consents=lambda _p: True,
        holdable=lambda _a: True,
    )
    assert any("plan" in f for f in found)


def test_an_unregistered_tool_and_a_wrong_kind_are_refused() -> None:
    tools = {"evidence.search": ToolFacts("compute", "evidence.read")}
    found = _registry(_doc(), tools)
    assert any("files.propose_save is not registered" in f for f in found)
    assert any("is a compute tool, listed as read" in f for f in found)


def test_a_denied_scope_action_needs_its_own_approved_write_tool() -> None:
    doc = _doc(tools={"read": ["evidence.search"]}, plan="never")
    found = _registry(doc, {"evidence.search": TOOLS["evidence.search"]})
    assert any("task scope may not include file.save" in f for f in found)


def test_a_single_call_takes_one_step_and_no_tools() -> None:
    doc = _doc(shape="single_call", tools={"read": ["evidence.search"]})
    found = spec_problems(
        AgentSpecV2.model_validate(doc), consents=lambda _p: True, holdable=lambda _a: True
    )
    assert any("exactly one step" in f for f in found)
    assert any("uses no tools" in f for f in found)


def test_the_codegen_refuses_through_the_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    registered = {
        "evidence.search": type("T", (), {"kind": "read", "action": "evidence.read"})(),
    }
    monkeypatch.setattr(
        "abacus.modules.agents.api.registered_tools", lambda: registered, raising=True
    )
    found = agent_specs_v2.refusals(_doc(), MATRIX)
    assert any("files.propose_save is not registered" in f for f in found)


def test_v1_specs_load_unchanged_and_v2_holds_only_the_drafter_until_t40() -> None:
    assert "evidence.screener" in v1.AGENTS
    assert all(s.shape == "single_call" for s in v1.AGENTS.values())
    # T-04-T25 lands the first v2 spec (the return drafter); P-10-T40 the reference capability;
    # T-04-T31 the tax fix runner and the analyst's explain mode; T-04-T37 the TAX-08 assistant
    # (DEC-4316). The v1 agents stay v1.
    assert set(spec_v2.AGENTS_V2) == {
        "tax.return_drafter",
        "runtime.conformance",
        "issues.fix_runner",
        "tax.return_analyst",
        "tax.assistant",
    }
    assert agent_specs_v2.main(["--check"]) == 0
