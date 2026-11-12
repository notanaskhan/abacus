"""P-10-T54 (TASK-7429): the M17 shadow evidence is read from the database: the synthetic
firm's engagement runs in the window and INV-1 and INV-5 over its audit events."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from abacus.kernel.clock import system_now
from abacus_tools import runtime_v2_flip as flip
from abacus_tools.db_connect import connect as connect_db

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio

_AUDIT = (
    "WITH s AS (SELECT set_config('app.on_behalf_of', $4::uuid::text, true) AS v) "
    "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, target_type, target_id, "
    "on_behalf_of_user_id) SELECT $1::uuid, 'agent', $2::text, 'probe.recorded', 'probe', "
    "$3::text, $4::uuid FROM s"
)


async def _firm(seed: Seeder, *, synthetic: bool) -> uuid.UUID:
    tenant = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = $2 WHERE tenant_id = $1", tenant, synthetic)
    return tenant


async def _runs(seed: Seeder, tenant: uuid.UUID, n: int) -> None:
    owner = await seed.person(tenant)
    engagement = await seed.engagement(tenant, await seed.entity(tenant), owner.user_id)
    for k in range(n):
        await seed.run(
            "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
            "initiator_user_id, task_scope, state, mode, trigger_kind, run_number) VALUES "
            "($1, $2, 'engagements.run', 1, $3, $4, ARRAY['engagement.read'], 'queued', 'run', "
            "'engagement_plan', $5)",
            uuid.uuid4(),
            tenant,
            engagement,
            owner.user_id,
            9000 + k,
        )


async def test_the_shadow_counts_runs_and_invariant_failures(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await _firm(seed, synthetic=True)
    await _runs(seed, tenant, 3)
    # INV-5: an agent row on behalf of someone who is no user at all.
    agent = ("agent", "agent:probe:run")
    await seed.as_actor(tenant, agent, _AUDIT, tenant, agent[1], str(uuid.uuid4()), uuid.uuid4())
    today = system_now().date()
    conn = await connect_db(migrated_db.superuser_dsn)
    try:
        found = await flip.shadow_evidence(
            conn, tenant, today - timedelta(days=1), today, date(2028, 3, 20)
        )
        quiet = await flip.shadow_evidence(
            conn, tenant, today - timedelta(days=30), today - timedelta(days=10), None
        )
    finally:
        await conn.close()
    assert (found.runs, found.invariant_failures) == (3, 1)
    assert (quiet.runs, quiet.invariant_failures) == (0, 0)
    assert "shadow_invariant_failures" in flip.shadow_findings(found)


async def test_a_firm_that_is_not_synthetic_is_refused(migrated_db: MigratedDatabase) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await _firm(seed, synthetic=False)
    conn = await connect_db(migrated_db.superuser_dsn)
    try:
        with pytest.raises(ValueError, match="synthetic firm"):
            await flip.shadow_evidence(conn, tenant, date(2028, 3, 1), date(2028, 4, 20), None)
    finally:
        await conn.close()
