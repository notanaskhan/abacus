"""P-10-T33 (SPEC-647 AC-W1, AC-W10; C6 v2 §9): the pure parts of a person's run commands.

The routes, the rows and the signals: `tests/integration/agent_tests/test_p10t33_run_commands.py`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.agents.commands import (
    PlanEditInvalid,
    _edited,  # pyright: ignore[reportPrivateUsage] -- the edit rule, pure
    require_live_human,
    run_actions,
)
from abacus.modules.agents.run_plan import PlanStep
from abacus.modules.identity.api import AuthContext, Forbidden

ALL = ("agent_run.approve_plan", "agent_run.answer", "agent_run.control", "agent_run.sign_off")


def _s(key: str, *deps: str) -> PlanStep:
    return PlanStep.parse({"key": key, "level": 0, "kind": "tool", "depends_on": list(deps)})


def _ctx(kind: str) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        tenant=TenantContext(uuid.uuid4(), kind, str(user)),  # pyright: ignore[reportArgumentType]
        user_id=user,
        membership_id=uuid.uuid4(),
        firm_role=None,
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


def test_an_edit_keeps_and_reorders_and_never_drops_a_dependency() -> None:
    plan = [_s("tb"), _s("materiality", "tb"), _s("analytics")]
    assert [s.key for s in _edited(plan, ["analytics", "tb"])] == ["analytics", "tb"]
    for keys in (["materiality"], ["tb", "tb"], ["tb", "new_step"]):
        with pytest.raises(PlanEditInvalid):
            _edited(plan, keys)


def test_allowed_actions_follow_the_state_and_the_callers_matrix() -> None:
    assert run_actions("awaiting_plan_approval", ALL, False)[:3] == [
        "approve_plan",
        "edit_plan",
        "cancel_plan",
    ]
    assert run_actions("needs_input", ALL, False) == [
        "answer",
        "skip",
        "redirect",
        "retry",
        "stop",
    ]
    assert run_actions("succeeded", ALL, False) == ["sign_off"]
    assert run_actions("succeeded", ALL, True) == []
    assert run_actions("running", ("agent_run.read",), False) == []
    assert run_actions("cancelled", ALL, False) == []


@pytest.mark.parametrize("kind", ["agent", "system"])
def test_only_a_live_person_commands_a_run(kind: str) -> None:
    require_live_human(_ctx("human"), "agent_run.approve_plan")
    with pytest.raises(Forbidden):
        require_live_human(_ctx(kind), "agent_run.approve_plan")
