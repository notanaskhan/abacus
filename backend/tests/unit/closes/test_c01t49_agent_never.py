"""C-01-T49 (TASK-8537; ADR-078; I-AGENT-NEVER): the close agent never resolves, approves, signs,
publishes, adopts, incorporates or sends.

Proven at three layers, written from SPEC-655 and C-01 §5: the tool layer (the close agent's C17
tools only read, compute and propose; no tool is named for a never-verb), the route layer (every
matrix action whose verb is a never-verb denies the agent and the system) and the database layer
(the human-only CHECKs on the resolution, acceptance and sign-off columns in the closes
migrations).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from abacus.modules.closes.agent_tools import AGENT_TOOLS

ROOT = Path(__file__).resolve().parents[4]
MATRIX = ROOT / "docs" / "architecture" / "permission-matrix"
MIGRATIONS = ROOT / "backend" / "migrations" / "versions"
NEVER = (
    "resolve", "approve", "sign", "sign_off", "publish", "adopt", "incorporate", "send", "accept",
    "post", "decide", "release", "reopen", "not_applicable",
)  # fmt: skip
MODULES = ("closes", "review")


def _actions() -> list[tuple[str, str, dict[str, object]]]:
    out: list[tuple[str, str, dict[str, object]]] = []
    for module in MODULES:
        doc = yaml.safe_load((MATRIX / f"{module}.yaml").read_text(encoding="utf-8"))
        out += [(module, a, row) for a, row in doc["actions"].items()]
    return out


def _verb(action: str) -> str:
    return action.split(".", 1)[1]


# ---- tool layer ----------------------------------------------------------------------------


def test_no_close_tool_is_named_for_a_never_verb() -> None:
    for tool in AGENT_TOOLS:
        verb = tool.name.split(".", 1)[1]
        assert not any(re.search(rf"(^|_){v}($|_)", verb) for v in NEVER), tool.name


def test_the_only_write_the_close_agent_has_is_a_suggestion() -> None:
    writes = [t for t in AGENT_TOOLS if t.kind not in ("read", "compute")]
    assert [t.kind for t in writes] == ["propose"]
    assert {t.action for t in writes} == {"suggestion.create"}


# ---- route layer ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("module", "action", "row"),
    [x for x in _actions() if any(_verb(x[1]).startswith(v) for v in NEVER)],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_every_never_verb_action_denies_the_agent_and_the_system(
    module: str, action: str, row: dict[str, object]
) -> None:
    assert row.get("agent") == "deny", (module, action)
    assert row.get("system") in (None, "deny"), (module, action)


def test_the_never_verbs_are_present_in_the_matrix() -> None:
    verbs = {_verb(a) for _, a, _ in _actions()}
    assert any(v.startswith("resolve") for v in verbs)
    assert any(v.startswith(("approve", "accept")) for v in verbs)


# ---- database layer ------------------------------------------------------------------------


def test_the_closes_migrations_hold_resolutions_and_acceptances_to_a_human() -> None:
    body = (MIGRATIONS / "0885_closes_v2_requests_cas.py").read_text(encoding="utf-8")
    assert "actor_kind text NOT NULL CHECK (actor_kind = 'human')" in body
    assert "accepted_actor_kind text NULL CHECK (accepted_actor_kind = 'human')" in body
    assert "CHECK ((accepted_by IS NULL) = (accepted_actor_kind IS NULL))" in body
