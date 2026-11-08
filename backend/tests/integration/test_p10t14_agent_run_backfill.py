"""P-10-T14 (TASK-6105; SPEC-647 §4.4): the legacy agent run backfill against Postgres.

Row acceptance: "On production-sized synthetic data every run gets a state and run number,
specialist workflows replay unchanged, and an interrupted backfill resumes." Replay is
`tests/workflows/` (the specialists' histories are untouched; the backfill's own are new). Here:
every pre-v2 run gets its legacy state and a gap-free run number in start order, status and
finished_at never move, a second firm is untouched, a stopped backfill resumes where it stopped,
and the trigger refuses anything but the legacy mapping.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import cast

import asyncpg
import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.modules.agents.run_backfill import LEGACY_STATE, backfill_batch

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
# Production-sized for one firm's pre-v2 history (P-10 §4.7): a few thousand runs per firm.
ROWS = 2_400
_STATUSES = ("completed", "escalated", "failed", "running")


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _legacy_firm(seed: Seeder, rows: int) -> uuid.UUID:
    """A firm with `rows` runs written as a pre-0680 writer left them: `state` NULL."""
    tenant = await seed.firm()
    person = await seed.person(tenant)
    engagement = await seed.engagement(tenant, await seed.entity(tenant), person.user_id)
    conn = await asyncpg.connect(seed._dsn)  # pyright: ignore[reportPrivateUsage]
    try:
        await conn.execute("ALTER TABLE agent_runs DISABLE TRIGGER agent_runs_state_sync")
        await conn.execute(
            """
            INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id,
                initiator_user_id, task_scope, status, failure_code, started_at, finished_at)
            SELECT $1, 'evidence.screener', 1, $2, $3, ARRAY['evidence.read'], s.status,
                   CASE WHEN s.status = 'failed' THEN 'provider_error' END,
                   timestamp '2027-01-01' + (g * interval '1 minute'),
                   CASE WHEN s.status <> 'running'
                        THEN timestamp '2027-01-01' + g * interval '1 minute' + interval '9 s'
                   END
              FROM generate_series(1, $4) AS g
              CROSS JOIN LATERAL (SELECT ($5::text[])[1 + g % 4] AS status) AS s
            """,
            tenant,
            engagement,
            person.user_id,
            rows,
            list(_STATUSES),
        )
    finally:
        await conn.execute("ALTER TABLE agent_runs ENABLE TRIGGER agent_runs_state_sync")
        await conn.close()
    return tenant


async def _drain(tenant: uuid.UUID, limit: int, stop_after: int | None = None) -> int:
    batches = 0
    while True:
        result = await backfill_batch(tenant, limit)
        batches += 1
        if not result.remaining or (stop_after is not None and batches >= stop_after):
            return batches


async def test_every_run_gets_its_state_and_a_run_number(seed: Seeder) -> None:
    tenant = await _legacy_firm(seed, ROWS)
    other = await _legacy_firm(seed, 30)
    before = {
        r["id"]: (r["status"], r["finished_at"], r["failure_code"])
        for r in await seed.rows(
            "SELECT id, status, finished_at, failure_code FROM agent_runs WHERE tenant_id = $1",
            tenant,
        )
    }
    await _drain(tenant, 500)
    rows = await seed.rows(
        "SELECT id, status, state, state_reason, run_number, finished_at, failure_code "
        "FROM agent_runs WHERE tenant_id = $1 ORDER BY started_at, id",
        tenant,
    )
    assert len(rows) == ROWS
    assert [r["run_number"] for r in rows] == list(range(1, ROWS + 1))  # start order, no gaps
    for r in rows:
        assert r["state"] == LEGACY_STATE[r["status"]]
        assert (r["state_reason"] == "escalated") == (r["status"] == "escalated")
        assert (r["status"], r["finished_at"], r["failure_code"]) == before[r["id"]]
    untouched = await seed.value(
        "SELECT count(*) FROM agent_runs WHERE tenant_id = $1 AND state IS NULL", other
    )
    assert untouched == 30


async def test_an_interrupted_backfill_resumes_where_it_stopped(seed: Seeder) -> None:
    tenant = await _legacy_firm(seed, 1_000)
    await _drain(tenant, 300, stop_after=2)  # stopped after 600 rows
    left = await seed.value(
        "SELECT count(*) FROM agent_runs WHERE tenant_id = $1 AND state IS NULL", tenant
    )
    assert left == 400
    await _drain(tenant, 300)
    numbers = [
        r["run_number"]
        for r in await seed.rows(
            "SELECT run_number FROM agent_runs WHERE tenant_id = $1 ORDER BY started_at, id",
            tenant,
        )
    ]
    assert numbers == list(range(1, 1_001))
    again = await backfill_batch(tenant, 300)
    assert (again.updated, again.remaining) == (0, False)  # idempotent


async def test_each_batch_is_audited_by_the_system_with_counts_only(seed: Seeder) -> None:
    tenant = await _legacy_firm(seed, 120)
    await _drain(tenant, 50)
    events = await seed.rows(
        "SELECT actor_kind, (after_ref ->> 'count')::int AS count FROM audit_events "
        "WHERE tenant_id = $1 AND action = 'agent_runs.backfilled' ORDER BY id",
        tenant,
    )
    assert [e["actor_kind"] for e in events] == ["system"] * 3
    assert sum(cast(int, e["count"]) for e in events) == 120


async def test_the_trigger_accepts_only_the_legacy_mapping(seed: Seeder) -> None:
    tenant = await _legacy_firm(seed, 4)
    run = await seed.value(
        "SELECT id FROM agent_runs WHERE tenant_id = $1 AND status = 'completed' LIMIT 1", tenant
    )
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run("UPDATE agent_runs SET state = 'approved' WHERE id = $1", run)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):  # a finished row: nothing else moves
        await seed.run(
            "UPDATE agent_runs SET state = 'succeeded', output = '{}'::jsonb WHERE id = $1", run
        )
    await seed.run("UPDATE agent_runs SET state = 'succeeded', run_number = 99 WHERE id = $1", run)
    with pytest.raises(asyncpg.CheckViolationError):  # a run number never changes
        await seed.run("UPDATE agent_runs SET run_number = 100 WHERE id = $1", run)


async def test_new_runs_keep_their_numbers_after_the_backfill(seed: Seeder) -> None:
    tenant = await _legacy_firm(seed, 10)
    await _drain(tenant, 500)
    counter = await seed.value(
        "SELECT value FROM tenant_counters WHERE tenant_id = $1 AND name = 'agent_run'", tenant
    )
    assert counter == 10  # the next v2 run takes 11
