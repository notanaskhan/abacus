"""P-10-T10 (TASK-5110; SPEC-647 AC-R1; ADR-233): C17's stub. A final verb can only be
`approved_write`, at the rule, at `register_tool` and in the registry check; an unregistered tool
fails closed; an `approved_write` action must be `agent: deny`."""

from __future__ import annotations

import ast

import pytest
from pydantic import BaseModel

from abacus.modules.agents.tools.registry import (
    AgentTool,
    ToolInvalid,
    ToolKind,
    ToolNotRegistered,
    has_never_verb,
    register_tool,
    tool,
    unregistered,
    validate_tool,
)
from abacus_tools.quality.banned_patterns import RULES, Rule, SourceFile
from abacus_tools.quality.tool_registry import problems


class _In(BaseModel):
    id: str


class _Out(BaseModel):
    id: str


async def _handler(_: object, args: _In) -> _Out:
    return _Out(id=args.id)


def _tool(name: str, kind: ToolKind, action: str) -> AgentTool:
    return AgentTool(
        name=name,
        kind=kind,
        action=action,
        description=f"tool.{name}@v1",
        data_class="internal",
        input_model=_In,
        output_model=_Out,
        handler=_handler,
    )


@pytest.mark.parametrize(
    "action",
    [
        "tax_return.approve",
        "run.sign_off",
        "report.release",
        "letter.send",
        "entry.post",
        "binder.export",
        "efile.transmit",
        "card.decide",
        "template.publish",
        "suggestion.adopt",
        "issue.resolve",
        "evidence.accept",
        "evidence.reject",
    ],
)
@pytest.mark.parametrize("kind", ["read", "compute", "propose"])
def test_a_final_verb_is_refused_on_any_other_kind(kind: ToolKind, action: str) -> None:
    with pytest.raises(ToolInvalid, match="TOOL-001"):
        validate_tool(_tool("tax.read_return", kind, action))


def test_a_final_verb_is_allowed_as_an_approved_write() -> None:
    validate_tool(_tool("files.save_artifact", "approved_write", "letter.send"))


def test_reads_with_a_near_word_are_not_verbs() -> None:
    assert not has_never_verb("engagement.read")
    assert not has_never_verb("posted_entry.read")
    assert has_never_verb("run.sign_off")


def test_an_unregistered_tool_fails_closed() -> None:
    with pytest.raises(ToolNotRegistered):
        tool("nobody.registered_this")
    assert unregistered(["nobody.registered_this"]) == ["nobody.registered_this"]


def test_a_name_is_module_dot_verb_noun() -> None:
    with pytest.raises(ToolInvalid):
        register_tool(_tool("NoDots", "read", "engagement.read"))


def test_the_registry_check_holds_tools_to_the_matrix() -> None:
    tools = {
        "a.write_it": _tool("a.write_it", "approved_write", "x.send"),
        "b.read_it": _tool("b.read_it", "read", "y.read"),
        "c.read_it": _tool("c.read_it", "read", "z.gone"),
    }
    found = problems(tools, {"x.send": {"agent": "task_scope"}, "y.read": {"agent": "deny"}})
    assert len(found) == 3


def _rule_findings(name: str) -> list[object]:
    rule = next(r for r in RULES if isinstance(r, Rule) and r.id == "TOOL-001")
    code = (
        f'@agent_tool(name="{name}", kind="read", action="tax_return.read")\nasync def f(): ...\n'
    )
    src = SourceFile(
        rel="src/abacus/modules/tax/agent_tools.py",
        module="abacus.modules.tax.agent_tools",
        tree=ast.parse(code),
        comments={},
    )
    return list(rule.check(src))


def test_tool_001_reads_the_decorator() -> None:
    assert _rule_findings("tax.approve_return")
    assert not _rule_findings("tax.read_return")
