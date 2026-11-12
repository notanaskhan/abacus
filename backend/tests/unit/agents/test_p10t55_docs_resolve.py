"""P-10-T55 (TASK-7423): "a fresh session can register a tool and a run-step kind from the docs
alone". The reference's recipe names real things: every API, file and command it gives resolves on
this tree, so the docs cannot drift from the code without this failing."""

from __future__ import annotations

import importlib
import importlib.util
import inspect
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
REFERENCE = (REPO / "docs/architecture/reference/ai-agent.md").read_text(encoding="utf-8")
SKILL = (REPO / ".claude/skills/ai-agent/SKILL.md").read_text(encoding="utf-8")
NOTES = (REPO / "docs/contracts/p10-consumer-notes.md").read_text(encoding="utf-8")

AGENTS_API = (
    "agent_tool",
    "call_tool",
    "register_run_step",
    "RunStepFacts",
    "RunStepResult",
    "create_proposal",
    "register_suggestion_target",
    "register_proposal_adapter",
    "open_turn_run",
    "adopted_run_traces",
)


@pytest.mark.parametrize("name", AGENTS_API)
def test_every_api_the_docs_name_is_exported_by_agents_api(name: str) -> None:
    api = importlib.import_module("abacus.modules.agents.api")
    assert name in REFERENCE or name in NOTES or name in SKILL
    assert hasattr(api, name), f"agents.api has no {name}"


def test_the_decorator_takes_the_keywords_the_recipe_uses() -> None:
    from abacus.modules.agents.api import agent_tool

    params = set(inspect.signature(agent_tool).parameters)
    for keyword in ("name", "kind", "action", "data_class", "input_model", "output_model"):
        assert f"{keyword}=" in REFERENCE and keyword in params
    assert {"untrusted", "records_read"} <= params


def test_run_step_facts_and_results_have_the_documented_fields() -> None:
    from abacus.modules.agents.api import RunStepFacts, RunStepResult

    assert set(RunStepFacts.__dataclass_fields__) == {
        "run_id", "engagement_id", "step_key", "level", "arguments",
    }  # fmt: skip
    assert set(RunStepResult.__dataclass_fields__) == {"state", "error_code", "records_read"}
    assert "run_step_unavailable" in REFERENCE


def test_the_files_and_commands_the_recipe_names_exist() -> None:
    for path in (
        "backend/src/abacus/modules/workpapers/run_steps.py",
        "backend/src/abacus/modules/agents/tools/catalogue.py",
        "backend/src/abacus/modules/agents/specs/v2/tax.account_mapper.yaml",
        "backend/src/abacus/ai_gateway/prompts/tool.tax.read_return/v1.txt",
        "docs/contracts/tool-registry.md",
        "docs/contracts/agent-runs.md",
    ):
        assert (REPO / path).exists(), path
    assert importlib.util.find_spec("abacus_tools.codegen.agent_specs_v2") is not None
    assert "python -m abacus_tools.codegen.agent_specs_v2" in REFERENCE


def test_a_registered_run_step_kind_is_refused_twice_and_must_be_snake_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.modules.agents import engagement_run
    from abacus.modules.agents.api import RunStepFacts, RunStepResult, register_run_step
    from abacus.modules.identity.api import AgentContext

    monkeypatch.setattr(engagement_run, "_HANDLERS", {})  # leave the real registry as it was

    async def one(agent: AgentContext, facts: RunStepFacts) -> RunStepResult:
        return RunStepResult("succeeded")

    async def two(agent: AgentContext, facts: RunStepFacts) -> RunStepResult:
        return RunStepResult("failed", "x")

    register_run_step("docs_example_step", one)
    register_run_step("docs_example_step", one)  # the same handler again: fine
    with pytest.raises(ValueError, match="already registered"):
        register_run_step("docs_example_step", two)
    with pytest.raises(ValueError, match="snake_case"):
        register_run_step("Docs-Step", one)
