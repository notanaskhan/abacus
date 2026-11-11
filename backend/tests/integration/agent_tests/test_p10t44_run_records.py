"""P-10-T44 (TASK-7302; SPEC-647 §3.9 AC-RR2 to AC-RR5; DEC-4302): durable run records.

Row acceptance: "A run adopted 90 days earlier still exports with its tool calls through P-09's
export route after run_events are pruned" and re-renders byte-identical. The run is seeded as
P-10's durable rows (run, plan, steps, events) back-dated 90 days; the prune runs through its
definer as its own actor; the export route is P-09-T11's (fresh MFA).
"""

from __future__ import annotations

import uuid
from typing import cast

import httpx
import pytest

from abacus.modules.agents import trace_records
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Person, Seeder, World
from .walls_support import Net

pytestmark = pytest.mark.asyncio


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


async def _adopted_run(seed: Seeder, world: World, who: Person) -> uuid.UUID:
    run_id = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
            "initiator_user_id, task_scope, state, mode, trigger_kind, run_number, "
            "runs_as_user_id, inputs, started_at) VALUES ($1, 'runtime.conformance', 1, $2, $3, "
            "'{}', 'queued', 'run', 'manual', 4118, $3, '{}', "
            "clock_timestamp() - interval '90 days') RETURNING id",
            world.tenant_id,
            world.engagement_id,
            who.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO agent_run_steps (tenant_id, run_id, seq, plan_step_key, level, kind, "
        "tool_name, state, started_at, ended_at, records_read) VALUES ($1, $2, 1, 's1', 0, "
        "'tool', 'files.list', 'succeeded', clock_timestamp() - interval '90 days', "
        "clock_timestamp() - interval '90 days', 224)",
        world.tenant_id,
        run_id,
    )
    for state in ("running", "succeeded", "approved"):
        await seed.run("UPDATE agent_runs SET state = $2 WHERE id = $1", run_id, state)
    await seed.run(
        "INSERT INTO run_events (tenant_id, run_id, run_seq, type, payload, created_at) "
        "VALUES ($1, $2, 1, 'run.state_changed', '{}', clock_timestamp() - interval '90 days')",
        world.tenant_id,
        run_id,
    )
    return run_id


async def test_acrr2_an_adopted_run_exports_the_same_bytes_after_its_events_are_pruned(
    net: Net, seed: Seeder, world: World
) -> None:
    hannah = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, hannah, "manager")
    run_id = await _adopted_run(seed, world, hannah)
    path = f"/v1/agent-runs/{run_id}/trace-exports"
    headers = {**await net.headers(hannah), "Idempotency-Key": str(uuid.uuid4())}
    before = await net.http.post(path, headers=headers)
    assert before.status_code in (200, 201), before.text
    gone = await trace_records.prune_firm(world.tenant_id)
    assert gone >= 1
    assert await seed.value("SELECT count(*) FROM run_events WHERE run_id = $1", run_id) == 0
    headers = {**await net.headers(hannah), "Idempotency-Key": str(uuid.uuid4())}
    after = await net.http.post(path, headers=headers)
    assert after.status_code in (200, 201), after.text
    first = cast(dict[str, object], before.json())
    second = cast(dict[str, object], after.json())
    assert first["trace"] == second["trace"]  # byte-identical body
    assert "files.list" in str(second["trace"]) or "s1" in str(second["trace"])
    versions = await seed.value("SELECT count(*) FROM agent_run_traces WHERE run_id = $1", run_id)
    assert versions == 1


async def test_acrr5_the_archive_hook_names_each_adopted_runs_frozen_trace(
    net: Net, seed: Seeder, world: World
) -> None:
    hannah = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, hannah, "manager")
    run_id = await _adopted_run(seed, world, hannah)
    headers = {**await net.headers(hannah), "Idempotency-Key": str(uuid.uuid4())}
    await net.http.post(f"/v1/agent-runs/{run_id}/trace-exports", headers=headers)
    from abacus.kernel.db import TenantContext

    hooked = await trace_records.adopted_run_traces(
        TenantContext(world.tenant_id, "system", "test"), world.engagement_id
    )
    assert [(t.run_id, t.version) for t in hooked] == [(run_id, 1)]


async def test_a_person_cannot_prune_run_events(seed: Seeder, world: World) -> None:
    with pytest.raises(Exception, match="only the run events prune"):
        await seed.run("SELECT prune_run_events(10)")
