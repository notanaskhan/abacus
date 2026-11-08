"""R-02-T04 (Q-03-T206, TASK-6129; ADR-078): an independent suite for protected bundle 1.

Written from the R-02-T04 row and R-02 §3 (agents propose, clients and partners decide), not from
the bundle's diff. Row acceptance: "generated allow and deny tests cover every new action, and
I-AGENT-NEVER lists every client decision action." Covered:

- every portal, reporting and assurance action a client role may take denies the agent and the
  system principals;
- every decision-shaped action in those files (approve, decide, acknowledge, confirm, sign) denies
  the agent;
- I-AGENT-NEVER (human-only audit actions) names R-02's three client decisions;
- the portal module may read reporting (the C10 registry and the management decision);
- CLIENT-DECISION-001 catches a planted `decide()` on the C18 slot outside its two allowed homes.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

from abacus_tools.quality.banned_patterns import MODULE_DEPENDENCIES, RULES, Rule, SourceFile

REPO = Path(__file__).resolve().parents[4]
MATRIX = REPO / "docs" / "architecture" / "permission-matrix"
FILES = ("portal", "reporting", "assurance")
CLIENT_ROLES = ("client_admin", "client_contributor", "third_party")
DECISION_VERBS = ("approve", "decide", "acknowledge", "confirm", "sign")
R02_CLIENT_DECISIONS = (
    "uncorrected_misstatements.acknowledged",
    "proposed_entry.client_decided",
    "statement.approved_by_management",
)


def _actions(name: str) -> dict[str, dict[str, object]]:
    data = yaml.safe_load((MATRIX / f"{name}.yaml").read_text(encoding="utf-8"))
    return {k: v for k, v in (data.get("actions") or {}).items() if isinstance(v, dict)}


ALL = [(f, a, row) for f in FILES for a, row in _actions(f).items()]


def test_the_three_matrices_carry_actions() -> None:
    assert all(_actions(f) for f in FILES)


@pytest.mark.parametrize(
    ("file", "action", "row"),
    [x for x in ALL if any(x[2].get(r) not in (None, "deny") for r in CLIENT_ROLES)],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_a_client_action_denies_the_agent_and_the_system(
    file: str, action: str, row: dict[str, object]
) -> None:
    assert row.get("agent") == "deny", (file, action)
    assert row.get("system") == "deny", (file, action)


@pytest.mark.parametrize(
    ("file", "action", "row"),
    [x for x in ALL if x[1].split(".", 1)[1].startswith(DECISION_VERBS)],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_a_decision_is_never_the_agent_s(file: str, action: str, row: dict[str, object]) -> None:
    assert row.get("agent") == "deny", (file, action)


def test_i_agent_never_lists_every_r02_client_decision() -> None:
    listed = yaml.safe_load(
        (REPO / "docs" / "architecture" / "human-only-actions.yaml").read_text(encoding="utf-8")
    )
    names = {a["action"] for a in listed["actions"]}
    assert set(R02_CLIENT_DECISIONS) <= names


def test_the_portal_may_read_reporting() -> None:
    assert "reporting" in MODULE_DEPENDENCIES["portal"]


def _rule() -> Rule:
    return next(r for r in RULES if isinstance(r, Rule) and r.id == "CLIENT-DECISION-001")


PLANTED = (
    "async def go(kind, tenant, item):\n"
    "    await client_approval_provider(kind).decide(tenant, item, 'approved')\n"
    "    slot = client_approval_provider(kind)\n"
    "    await slot.decide(tenant, item, 'rejected')\n"
)


def test_the_rule_catches_a_planted_client_decision() -> None:
    rel = "src/abacus/modules/engagements/sneaky.py"
    rule = _rule()
    assert rule.applies_to(rel)
    found = list(rule.check(SourceFile(rel, None, ast.parse(PLANTED), {})))
    assert len(found) == 2


@pytest.mark.parametrize(
    "rel",
    [
        "src/abacus/modules/portal/approvals.py",
        "src/abacus/modules/adjustments/client_decisions.py",
    ],
)
def test_the_two_allowed_homes_are_outside_the_rule(rel: str) -> None:
    assert not _rule().applies_to(rel)
