"""P-10-T52 (ADR-079; SPEC-647 §4.7; DEC-4402): query counts on the run reads.

Each run read answers in a fixed number of statements whatever the run's size: the same count for
a 3-step and a 14-step run (no per-step query), within the read's budget. The counter listens on
every engine's `before_cursor_execute`, as the slow-statement recorder does, for one request.
"""

from __future__ import annotations

import json
import uuid
from typing import Final

import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

from abacus.kernel.flags import forget_flags
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Person, Seeder, World
from .walls_support import Net

pytestmark = pytest.mark.asyncio

# The budget per read: every statement the request runs (sign-in, tenant context, flags,
# authorise and visibility, then the run head, its steps and counters). Set at the S38 end pass
# from the first measurement (run 151, items 125, trace 168, list 105; TASK-7426) plus about
# 10%; the hard rule is the equality above it: the count never grows with the run's size.
BUDGETS: Final = {
    "run": 166,
    "items": 138,
    "trace": 185,
    "list": 116,
}


class counted:
    """Counts every statement any engine runs while the block runs."""

    def __init__(self) -> None:
        self.n = 0

    def __call__(self, *_: object) -> None:
        self.n += 1

    def __enter__(self) -> counted:
        event.listen(Engine, "before_cursor_execute", self)
        return self

    def __exit__(self, *_: object) -> None:
        event.remove(Engine, "before_cursor_execute", self)


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


async def _manager(seed: Seeder, world: World) -> Person:
    hannah = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, hannah, "manager")
    return hannah


async def _run(seed: Seeder, world: World, steps: int, number: int) -> uuid.UUID:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'agent_runtime.v2', 'true', 'p10-t52', 'P-10-T52') ON CONFLICT DO NOTHING",
        world.tenant_id,
    )
    forget_flags()
    run_id = uuid.uuid4()
    await seed.run(
        "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope, state, mode, trigger_kind, run_number, runs_as_user_id) "
        "VALUES ($1, $2, 'engagements.run', 2, $3, $4, '{}', 'running', 'run', "
        "'engagement_plan', $5, $4)",
        run_id,
        world.tenant_id,
        world.engagement_id,
        world.requester.user_id,
        number,
    )
    plan = [
        {"key": f"s{n}", "label": f"Step {n}", "level": 1 + n % 5, "kind": "compute"}
        for n in range(steps)
    ]
    await seed.as_actor(
        world.tenant_id,
        ("agent", str(run_id)),
        "INSERT INTO agent_plans (tenant_id, run_id, version, steps, state) "
        "VALUES ($1, $2, 1, CAST($3 AS jsonb), 'proposed')",
        world.tenant_id,
        run_id,
        json.dumps(plan),
    )
    for n in range(steps):
        await seed.run(
            "INSERT INTO agent_run_steps (tenant_id, run_id, seq, plan_step_key, level, kind, "
            "tool_name, args_hash, state, started_at) VALUES ($1, $2, $3, $4, $5, 'compute', "
            "'run_step.workpaper', $6, $7, now())",
            world.tenant_id,
            run_id,
            n + 1,
            f"s{n}",
            1 + n % 5,
            "0" * 64,
            "succeeded" if n % 3 else "running",
        )
    return run_id


def _paths(world: World, run_id: uuid.UUID) -> dict[str, str]:
    return {
        "run": f"/v1/agent-runs/{run_id}",
        "items": f"/v1/agent-runs/{run_id}/items",
        "trace": f"/v1/agent-runs/{run_id}/trace",
        "list": f"/v1/engagements/{world.engagement_id}/agent-runs?state=active",
    }


async def _statements(net: Net, who: Person, path: str) -> int:
    headers = await net.headers(who)
    await net.http.get(path, headers=headers)  # warm: the caches and the flag read
    with counted() as counter:
        response = await net.http.get(path, headers=headers)
    assert response.status_code == 200, (path, response.text)
    return counter.n


@pytest.mark.parametrize("read", sorted(BUDGETS))
async def test_a_run_read_is_constant_in_the_runs_size_and_within_budget(
    net: Net, seed: Seeder, world: World, read: str
) -> None:
    hannah = await _manager(seed, world)
    small = await _run(seed, world, 3, 4126)
    small_count = await _statements(net, hannah, _paths(world, small)[read])
    large = await _run(seed, world, 14, 4127)
    large_count = await _statements(net, hannah, _paths(world, large)[read])
    assert large_count == small_count, (read, small_count, large_count)
    assert large_count <= BUDGETS[read], (read, large_count)
