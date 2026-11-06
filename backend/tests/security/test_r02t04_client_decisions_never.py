"""R-02-T04 (ADR-005, I-AGENT-NEVER; SPEC-646 AC-5): every client decision and every portal read
R-02 added is denied to an agent, a system run and a support session, whatever a person would
need. The rule CLIENT-DECISION-001 names the only callers of a provider's `decide()`."""

from __future__ import annotations

import ast

import pytest

from abacus_tools.quality.banned_patterns import RULES, Rule, SourceFile

from .matrix_harness import Principal, principal_outcome

DECISIONS = (
    "proposed_entry.client_decide",
    "uncorrected_misstatements.acknowledge",
    "close_package.client_decide",
    "statement.client_approve",
    "tcwg.acknowledge",
)
READS = (
    "client_approval.read",
    "client_approval.ask",
    "deliverable.read",
    "deliverable.download",
    "deliverable.comment",
    "tcwg.read",
    "tcwg.ask",
)
PRINCIPALS: tuple[Principal, ...] = ("agent", "system", "support")


@pytest.mark.parametrize("action", DECISIONS + READS)
@pytest.mark.parametrize("principal", PRINCIPALS)
async def test_the_principal_is_denied(
    monkeypatch: pytest.MonkeyPatch, action: str, principal: Principal
) -> None:
    assert await principal_outcome(monkeypatch, action, principal) == "deny"


def _findings(code: str, path: str) -> list[object]:
    rule = next(r for r in RULES if isinstance(r, Rule) and r.id == "CLIENT-DECISION-001")
    src = SourceFile(rel=path, module="abacus.modules.agents.x", tree=ast.parse(code), comments={})
    return list(rule.check(src))


def test_the_rule_finds_a_decide_outside_the_allowed_files() -> None:
    assert _findings(
        "async def f(tx):\n    p = client_approval_provider('fs_draft')\n    await p.decide(tx)\n",
        "src/abacus/modules/agents/x.py",
    )
    assert _findings(
        "async def f(tx):\n    await client_approval_provider('fs_draft').decide(tx)\n",
        "src/abacus/modules/agents/x.py",
    )


def test_the_rule_ignores_other_decides() -> None:
    assert not _findings(
        "async def f(x):\n    await x.decide()\n", "src/abacus/modules/agents/x.py"
    )
