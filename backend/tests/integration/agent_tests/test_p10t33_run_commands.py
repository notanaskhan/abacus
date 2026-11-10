"""P-10-T33 (TASK-6720; SPEC-647 §3.4 AC-W1, AC-W5, AC-W6, AC-W10; C6 v2 §9): a person's run
commands over HTTP and through `agents/commands.py`.

Row acceptance: "Agent and system contexts get 403 and the database refuses the row on plan
approval and run sign-off, and Hannah Leclerc's approval moves the run to dispatched with one audit
event."

The workflow is not running here: the signal is captured, and the run's next read of its plan
(`plan_state`, what AgentRunWorkflow reads after `plan_decided`) is what moves it to dispatched.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import asyncpg
import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.modules.agents import commands, run_commands
from abacus.modules.agents.run_activities import plan_state_activity
from abacus.modules.identity.api import AgentContext, AuthContext, Forbidden
from abacus.modules.identity.context import agent_context_for_run
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Person, Seeder, World
from .walls_support import Net

pytestmark = pytest.mark.asyncio
STEPS = [
    {"key": "tb", "label": "Trial balance", "level": 0, "kind": "tool"},
    {
        "key": "materiality",
        "label": "Materiality",
        "level": 1,
        "kind": "tool",
        "depends_on": ["tb"],
    },
    {"key": "analytics", "label": "Planning analytics", "level": 1, "kind": "tool"},
]
Signals = list[tuple[str, str, tuple[object, ...]]]


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


@pytest.fixture
def signals(monkeypatch: pytest.MonkeyPatch) -> Signals:
    sent: Signals = []

    async def capture(workflow_id: str, signal: str, *args: object) -> None:
        sent.append((workflow_id, signal, args))

    monkeypatch.setattr(commands, "signal_workflow", capture)
    monkeypatch.setattr(run_commands, "signal_workflow", capture)
    return sent


async def _hannah(seed: Seeder, world: World) -> Person:
    """Hannah Leclerc, the engagement's manager."""
    hannah = await seed.person(world.tenant_id)
    await seed.run(
        "UPDATE users SET display_name = 'Hannah Leclerc' WHERE id = $1", hannah.user_id
    )
    await seed.member(world.engagement_id, hannah, "manager")
    return hannah


async def _v2_run(seed: Seeder, world: World, state: str = "awaiting_plan_approval") -> uuid.UUID:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'agent_runtime.v2', 'true', 'p10-t33', 'P-10-T33') ON CONFLICT DO NOTHING",
        world.tenant_id,
    )
    forget_flags()
    run_id = uuid.uuid4()
    await seed.run(
        "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope, state, mode, trigger_kind, run_number, runs_as_user_id) "
        "VALUES ($1, $2, 'audit.planning', 2, $3, $4, '{}', $5, 'run', 'manual', 4118, $4)",
        run_id,
        world.tenant_id,
        world.engagement_id,
        world.requester.user_id,
        state,
    )
    await seed.as_actor(
        world.tenant_id,
        ("agent", str(run_id)),
        "INSERT INTO agent_plans (tenant_id, run_id, version, steps, state) "
        "VALUES ($1, $2, 1, CAST($3 AS jsonb), 'proposed')",
        world.tenant_id,
        run_id,
        json.dumps(STEPS),
    )
    return run_id


async def _agent(world: World, run_id: uuid.UUID) -> AgentContext:
    return await agent_context_for_run(
        tenant_id=world.tenant_id,
        run_id=run_id,
        agent_id="audit.planning",
        engagement_id=world.engagement_id,
        task_scope=frozenset({"agent_run.approve_plan", "agent_run.sign_off"}),
        initiator_user_id=world.requester.user_id,
    )


def _system(world: World) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(world.tenant_id, "system", "platform"),
        user_id=uuid.uuid4(),
        membership_id=uuid.uuid4(),
        firm_role=None,
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


def _key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


async def _post(net: Net, path: str, who: Person, body: object) -> httpx.Response:
    headers = {**await net.headers(who), **_key()}
    return await net.http.request("POST", path, json=body, headers=headers)


# --- the row's acceptance ------------------------------------------------------------------------


async def test_ac_hannahs_approval_moves_the_run_to_dispatched_with_one_audit_event(
    net: Net, seed: Seeder, world: World, signals: Signals
) -> None:
    hannah = await _hannah(seed, world)
    run_id = await _v2_run(seed, world)
    before = await seed.actions(world.tenant_id)
    response = await _post(
        net, f"/v1/agent-runs/{run_id}/plan/approve", hannah, {"expected_version": 1}
    )
    assert response.status_code == 200, response.text
    body = cast(dict[str, object], response.json())
    assert (body["version"], body["state"], body["decided_by"]) == (
        2,
        "approved",
        "Hannah Leclerc",
    )
    after = await seed.actions(world.tenant_id)
    assert after[len(before) :] == ["agent_run.plan_approved"]
    assert [s for _, s, _ in signals] == ["plan_decided"]
    # What the workflow reads after `plan_decided`: an approved plan, so it dispatches.
    plan = await plan_state_activity(str(world.tenant_id), str(run_id))
    assert (plan.version, plan.state, len(plan.steps)) == (2, "approved", 3)


async def test_ac_agent_and_system_contexts_get_403_on_plan_approval_and_sign_off(
    seed: Seeder, world: World, signals: Signals
) -> None:
    run_id = await _v2_run(seed, world)
    agent = await _agent(world, run_id)
    for ctx in (agent, _system(world)):
        with pytest.raises(Forbidden):
            await commands.approve_plan(cast(AuthContext, ctx), run_id, 1)
        with pytest.raises(Forbidden):
            await commands.sign_off(cast(AuthContext, ctx), run_id, issues=[], decisions=[])
    assert signals == []
    assert await seed.value("SELECT max(version) FROM agent_plans WHERE run_id = $1", run_id) == 1


@pytest.mark.parametrize(
    "insert",
    [
        "INSERT INTO agent_plans (tenant_id, run_id, version, steps, state, decided_by, "
        "decided_at) VALUES ($1, $2, 2, '[]', 'approved', $3, now())",
        "INSERT INTO run_sign_offs (tenant_id, run_id, signed_by) VALUES ($1, $2, $3)",
    ],
)
@pytest.mark.parametrize("actor_kind", ["agent", "system"])
async def test_ac_the_database_refuses_an_agent_or_system_decision_row(
    seed: Seeder, world: World, insert: str, actor_kind: str
) -> None:
    run_id = await _v2_run(seed, world)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.as_actor(
            world.tenant_id,
            (actor_kind, str(world.requester.user_id)),
            insert,
            world.tenant_id,
            run_id,
            world.requester.user_id,
        )


# --- the other commands --------------------------------------------------------------------------


async def test_a_stale_version_is_refused_and_an_edit_reorders_the_kept_keys(
    net: Net, seed: Seeder, world: World, signals: Signals
) -> None:
    hannah = await _hannah(seed, world)
    run_id = await _v2_run(seed, world)
    stale = await _post(
        net, f"/v1/agent-runs/{run_id}/plan/approve", hannah, {"expected_version": 7}
    )
    assert stale.status_code == 409 and stale.json()["detail"] == "plan_version_conflict"
    dropped = await _post(
        net,
        f"/v1/agent-runs/{run_id}/plan/edit",
        hannah,
        {"expected_version": 1, "steps": ["materiality", "analytics"]},
    )
    assert dropped.status_code == 422 and dropped.json()["detail"] == "plan_edit_invalid"
    edited = await _post(
        net,
        f"/v1/agent-runs/{run_id}/plan/edit",
        hannah,
        {"expected_version": 1, "steps": ["analytics", "tb"]},
    )
    assert edited.status_code == 200, edited.text
    assert [s["key"] for s in edited.json()["steps"]] == ["analytics", "tb"]
    assert edited.json()["state"] == "edited"
    # An edit is not an approval: the workflow waits again until one.
    plan = await plan_state_activity(str(world.tenant_id), str(run_id))
    assert plan.state == "edited"


async def test_a_question_is_answered_once_with_one_of_its_options(
    net: Net, seed: Seeder, world: World, signals: Signals
) -> None:
    hannah = await _hannah(seed, world)
    run_id = await _v2_run(seed, world, "needs_input")
    question = uuid.uuid4()
    await seed.run(
        "INSERT INTO agent_questions (id, tenant_id, run_id, steps) VALUES ($1, $2, $3, "
        "CAST($4 AS jsonb))",
        question,
        world.tenant_id,
        run_id,
        json.dumps(
            [{"key": "population", "prompt": "Which population?", "options": ["ap", "ar"]}]
        ),
    )
    path = f"/v1/agent-runs/{run_id}/questions/{question}/answer"
    unknown = await _post(net, path, hannah, {"option_key": "gl"})
    assert unknown.status_code == 422 and unknown.json()["detail"] == "answer_invalid"
    answered = await _post(net, path, hannah, {"option_key": "ap"})
    assert answered.status_code == 200, answered.text
    assert (answered.json()["state"], answered.json()["answered_by"]) == (
        "answered",
        "Hannah Leclerc",
    )
    again = await _post(net, path, hannah, {"option_key": "ar"})
    assert again.status_code == 409 and again.json()["detail"] == "question_not_open"
    assert [s for _, s, _ in signals] == ["question_answered"]


async def test_a_sign_off_acknowledges_every_open_issue_first(
    net: Net, seed: Seeder, world: World, signals: Signals
) -> None:
    hannah = await _hannah(seed, world)
    run_id = await _v2_run(seed, world, "failed")
    step = uuid.uuid4()
    await seed.run(
        "INSERT INTO agent_run_steps (id, tenant_id, run_id, seq, plan_step_key, kind, state) "
        "VALUES ($1, $2, $3, 1, 'tb', 'tool', 'failed')",
        step,
        world.tenant_id,
        run_id,
    )
    path = f"/v1/agent-runs/{run_id}/sign-off"
    missing = await _post(net, path, hannah, {})
    assert missing.status_code == 409 and missing.json()["detail"] == "sign_off_unacknowledged"
    signed = await _post(net, path, hannah, {"acknowledged_issue_ids": [str(step)]})
    assert signed.status_code == 200, signed.text
    assert signed.json()["signed_off_by"] == "Hannah Leclerc"
    assert "sign_off" not in signed.json()["allowed_actions"]
    again = await _post(net, path, hannah, {"acknowledged_issue_ids": [str(step)]})
    assert again.status_code == 409
    assert "agent_run.signed_off" in await seed.actions(world.tenant_id)


async def test_stop_and_redirect_wake_the_run_and_never_store_the_note(
    net: Net, seed: Seeder, world: World, signals: Signals
) -> None:
    hannah = await _hannah(seed, world)
    run_id = await _v2_run(seed, world, "running")
    note = "Use the September close, not August."
    redirected = await _post(net, f"/v1/agent-runs/{run_id}/messages", hannah, {"body": note})
    assert redirected.status_code == 202, redirected.text
    stopped = await _post(net, f"/v1/agent-runs/{run_id}/stop", hannah, None)
    assert stopped.status_code == 202, stopped.text
    assert [s for _, s, _ in signals] == ["redirected", "stop"]
    payloads = await seed.rows(
        "SELECT payload::text AS p FROM run_events WHERE run_id = $1", run_id
    )
    assert payloads and all(note not in str(r["p"]) for r in payloads)
