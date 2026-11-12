"""P-10-T57 (ADR-078): P-10-T08's matrix rows, written from P-10 §9's T08 acceptance ("Generated
tests deny agent, system and support principals approve_plan, answer, sign_off,
engagement_ai.configure and file.save, and portal principals hold no agent_run or session
action"), read from the generated matrix the server enforces."""

from __future__ import annotations

from typing import Final

import pytest

from abacus.modules.identity.api import RULES
from abacus.modules.identity.authz import CLIENT_ROLES

HUMAN_ONLY: Final = (
    "agent_run.approve_plan",
    "agent_run.answer",
    "agent_run.sign_off",
    "engagement_ai.configure",
    "file.save",
)


@pytest.mark.parametrize("action", HUMAN_ONLY)
def test_t08_agent_system_and_support_never_hold_the_human_only_actions(action: str) -> None:
    rule = RULES[action]
    for principal in ("agent", "system", "support"):
        assert rule.decisions.get(principal, "deny") == "deny", (action, principal)


def test_t08_portal_principals_hold_no_run_or_session_action() -> None:
    for action, rule in RULES.items():
        if not action.startswith(("agent_run.", "session.")):
            continue
        for role in CLIENT_ROLES:
            assert rule.decisions.get(role, "deny") == "deny", (action, role)
