"""P-10-T08 (ADR-005, I-AGENT-NEVER; SPEC-647 INV-1): a plan decision, an answer, a run sign-off,
Auto mode and filing an artifact are a person's, whatever facts a person would need. Portal
principals hold no run or session action."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from .matrix_harness import Principal, principal_outcome

NEVER = (
    "agent_run.start",
    "agent_run.approve_plan",
    "agent_run.answer",
    "agent_run.control",
    "agent_run.sign_off",
    "engagement_ai.configure",
    "file.save",
    "session.create",
    "session.manage",
)
PRINCIPALS: tuple[Principal, ...] = ("agent", "system", "support")
MATRIX = Path(__file__).resolve().parents[3] / "docs/architecture/permission-matrix"


@pytest.mark.parametrize("action", NEVER)
@pytest.mark.parametrize("principal", PRINCIPALS)
async def test_the_principal_is_denied(
    monkeypatch: pytest.MonkeyPatch, action: str, principal: Principal
) -> None:
    assert await principal_outcome(monkeypatch, action, principal) == "deny"


@pytest.mark.parametrize("action", ["file.propose", "todo.propose", "issue.create"])
def test_propose_tools_are_task_scope(action: str) -> None:
    rows: dict[str, dict[str, str]] = {}
    for name in ("agents", "review"):
        rows |= yaml.safe_load((MATRIX / f"{name}.yaml").read_text())["actions"]
    assert rows[action]["agent"] == "task_scope"


def test_portal_principals_hold_no_run_or_session_action() -> None:
    client_roles = {"client_admin", "client_contributor", "third_party"}
    rows: dict[str, dict[str, str]] = {}
    for name in ("agents", "workbench"):
        rows |= yaml.safe_load((MATRIX / f"{name}.yaml").read_text())["actions"]
    for action, row in rows.items():
        if action.startswith(("agent_run.", "session.")):
            assert not client_roles & set(row), action
