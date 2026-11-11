"""P-10-T42 (TASK-6801; SPEC-647 §3.10 AC-M1 to AC-M4; DEC-3401): the agent-minute ledger over
the database and HTTP.

Row acceptance: "ADM-14's 14,920 and ENG-06's 412 = 46 + 24 + 342 foot from the seed ledger, and
a sub-30-second run posts 0 minutes but counts as a run."

The seed's lines go through `record_synthetic_minutes` (the code `agent_run.completed` takes); a
v2 run's completion goes through `complete_run_activity` and the subscriber reading its outbox row.
"""

from __future__ import annotations

import json
import uuid
from typing import cast

import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.agents.run_activities import complete_run_activity
from abacus.modules.platform.metering import (
    RunMinutes,
    on_run_completed,
    record_synthetic_minutes,
)
from abacus_tools.fakes.identity import FakeIdentityProvider
from abacus_tools.synthetic.scenarios.brightwater_hale import usage_slice

from .support import Person, Seeder, World
from .walls_support import Net

pytestmark = pytest.mark.asyncio


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


async def _on(seed: Seeder, world: World) -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'agent_runtime.v2', 'true', 'p10-t42', 'P-10-T42') ON CONFLICT DO NOTHING",
        world.tenant_id,
    )
    forget_flags()


async def _admin(seed: Seeder, world: World) -> Person:
    grace = await seed.person(world.tenant_id)
    await seed.run(
        "UPDATE memberships SET firm_role = 'firm_admin' WHERE tenant_id = $1 AND user_id = $2",
        world.tenant_id,
        grace.user_id,
    )
    return grace


def _system(world: World) -> TenantContext:
    return TenantContext(world.tenant_id, "system", "test:agent-minutes")


def _seed_lines(world: World) -> list[RunMinutes]:
    lines = [
        RunMinutes(
            run_id=uuid.uuid4(),
            completed_on=on,
            agent_ms=minutes * 60_000,
            minutes=minutes,
            capability=capability,
            service_line="audit",
            engagement_id=world.engagement_id,
            run_number=number,
            phase=phase,
        )
        for number, capability, on, minutes, phase in usage_slice.NORTHWIND_RUNS
    ]
    lines += [
        RunMinutes(
            run_id=uuid.uuid4(),
            completed_on=usage_slice.SEPTEMBER_POSTED_ON,
            agent_ms=minutes * 60_000,
            minutes=minutes,
            capability="history",
            service_line=line,
        )
        for line, minutes in usage_slice.SEPTEMBER_BY_LINE
    ]
    return lines


async def _synthetic(seed: Seeder, world: World) -> None:
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", world.tenant_id)
    await seed.run(
        "INSERT INTO tenant_entitlements (tenant_id, module, agent_minutes_allowance, valid_from, "
        "set_by) VALUES ($1, 'tax_returns', 20000, '2000-01-01', 'p10-t42')",
        world.tenant_id,
    )


async def test_ac_m1_adm14a_foots_from_the_seed_ledger(
    net: Net, seed: Seeder, world: World
) -> None:
    await _on(seed, world)
    await _synthetic(seed, world)
    assert await record_synthetic_minutes(_system(world), _seed_lines(world)) == 8
    grace = await _admin(seed, world)
    response = await net.call("GET", "/v1/firm/usage?month=2026-09", grace)
    assert response.status_code == 200, response.text
    body = cast(dict[str, object], response.json())
    assert (body["used_minutes"], body["included_minutes"]) == (14_920, 20_000)
    assert (body["starts_on"], body["ends_on"]) == ("2026-09-15", "2026-10-14")
    lines = cast(list[dict[str, object]], body["by_service_line"])
    assert [(x["label"], x["minutes"]) for x in lines] == [
        ("Tax", 8_640),
        ("Audit & assurance", 4_610),
        ("Client accounting", 1_420),
        ("Advisory & attest", 120),
        ("Firm operations", 130),
    ]
    assert "cost_usd" not in response.text  # AC-M3: never USD


async def test_ac_m1_eng06a_foots_412(net: Net, seed: Seeder, world: World) -> None:
    await _on(seed, world)
    await _synthetic(seed, world)
    await record_synthetic_minutes(_system(world), _seed_lines(world))
    response = await net.call(
        "GET", f"/v1/engagements/{world.engagement_id}/effort", world.requester
    )
    assert response.status_code == 200, response.text
    body = cast(dict[str, object], response.json())
    assert (body["used_minutes"], body["runs"], body["budget_minutes"]) == (412, 3, 1_500)
    labels = [cast(str, x["label"]) for x in cast(list[dict[str, object]], body["lines"])]
    assert labels == [
        "Run #4019 · PBC list builder",
        "Run #4064 · Document classifier & matcher",
        "Run #4102 · Plan provisions extraction",
    ]


async def test_redelivery_posts_nothing_twice(seed: Seeder, world: World) -> None:
    await _synthetic(seed, world)
    lines = _seed_lines(world)
    assert await record_synthetic_minutes(_system(world), lines) == 8
    assert await record_synthetic_minutes(_system(world), lines) == 0


async def test_a_real_firm_cannot_write_synthetic_minutes(world: World) -> None:
    with pytest.raises(NotFound):
        await record_synthetic_minutes(_system(world), _seed_lines(world))


async def _v2_run(seed: Seeder, world: World, agent_ms: int) -> uuid.UUID:
    run_id = uuid.uuid4()
    await seed.run(
        "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope, state, mode, trigger_kind, run_number, agent_ms) "
        "VALUES ($1, $2, 'audit.planning', 2, $3, $4, '{}', 'running', 'run', 'manual', 4130, $5)",
        run_id,
        world.tenant_id,
        world.engagement_id,
        world.requester.user_id,
        agent_ms,
    )
    return run_id


async def _deliver(seed: Seeder, world: World, run_id: uuid.UUID) -> int:
    rows = await seed.rows(
        "SELECT id, payload FROM outbox WHERE tenant_id = $1 AND event_type = "
        "'agent_run.completed' AND payload->>'run_id' = $2",
        world.tenant_id,
        str(run_id),
    )
    for row in rows:
        payload = row["payload"]
        await on_run_completed(
            OutboxEvent(
                event_id=row["id"],
                tenant_id=world.tenant_id,
                event_type="agent_run.completed",
                payload=json.loads(payload) if isinstance(payload, str) else payload,
            )
        )
    return len(rows)


async def test_ac_m2_a_sub_30_second_run_posts_zero_but_counts(
    net: Net, seed: Seeder, world: World
) -> None:
    await _on(seed, world)
    run_id = await _v2_run(seed, world, agent_ms=29_999)
    await complete_run_activity(str(world.tenant_id), str(run_id), "succeeded", None)
    assert await _deliver(seed, world, run_id) == 1
    assert await seed.value("SELECT agent_minutes FROM agent_runs WHERE id = $1", run_id) == 0
    response = await net.call(
        "GET", f"/v1/engagements/{world.engagement_id}/effort", world.requester
    )
    body = cast(dict[str, object], response.json())
    assert (body["used_minutes"], body["runs"]) == (0, 1)


async def test_ac_m1_minutes_are_stored_once(seed: Seeder, world: World) -> None:
    run_id = await _v2_run(seed, world, agent_ms=161_000)
    await complete_run_activity(str(world.tenant_id), str(run_id), "succeeded", None)
    await seed.run("UPDATE agent_runs SET agent_ms = 999999 WHERE id = $1", run_id)
    await complete_run_activity(str(world.tenant_id), str(run_id), "succeeded", None)
    assert await seed.value("SELECT agent_minutes FROM agent_runs WHERE id = $1", run_id) == 3
    assert await _deliver(seed, world, run_id) == 1  # one event, at the first terminal state
    assert await _deliver(seed, world, run_id) == 1  # redelivered: the ledger keeps one row
    assert (
        await seed.value("SELECT count(*) FROM agent_minute_ledger WHERE run_id = $1", run_id) == 1
    )


async def test_ac_m4_an_open_run_posts_nothing(seed: Seeder, world: World) -> None:
    run_id = await _v2_run(seed, world, agent_ms=600_000)
    assert await _deliver(seed, world, run_id) == 0
    assert (
        await seed.value("SELECT count(*) FROM agent_minute_ledger WHERE run_id = $1", run_id) == 0
    )


async def test_usage_is_refused_to_a_person_without_usage_read(
    net: Net, seed: Seeder, world: World
) -> None:
    await _on(seed, world)
    response = await net.call("GET", "/v1/firm/usage", world.requester)
    assert response.status_code == 403, response.text


async def test_usage_answers_404_when_the_runtime_is_off(
    net: Net, seed: Seeder, world: World
) -> None:
    grace = await _admin(seed, world)
    response = await net.call("GET", "/v1/firm/usage", grace)
    assert response.status_code == 404, response.text
