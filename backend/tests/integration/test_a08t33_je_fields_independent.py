"""A-08-T33 (ADR-078 independent; TASK-8087; ADR-004, ADR-031, ADR-400) against Postgres: the T09
JE columns on an existing ledger row can never be updated, by the app or by the table owner, and
an earlier snapshot reads every JE field unavailable. Fails on a build that rewrites a committed
`gl_entries` row to fill a JE field after the fact.
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio

_SNAPSHOT = """
    WITH s AS (
        INSERT INTO gl_snapshots (tenant_id, client_entity_id, period_start, period_end, source,
            raw_fingerprint, tb_snapshot_id, line_count, total_debit, total_credit)
        VALUES ($1, $2, '2025-07-01', '2026-06-30', 'netsuite_gl_csv',
            md5(random()::text) || md5(random()::text), gen_random_uuid(), 2, 250, 250)
        RETURNING id
    ), e AS (
        INSERT INTO gl_entries (tenant_id, snapshot_id, line_no, account_code, posted_on, debit,
            credit, source_ref)
        SELECT $1, s.id, n, CASE n WHEN 1 THEN '7100' ELSE '2100' END, '2026-06-27',
            CASE n WHEN 1 THEN 250 ELSE 0 END, CASE n WHEN 2 THEN 250 ELSE 0 END, 'row ' || n
        FROM s, generate_series(1, 2) n
        RETURNING 1
    )
    SELECT s.id FROM s, (SELECT count(*) FROM e) ee
"""
_FILLS = (
    "UPDATE gl_entries SET posted_by = 'zq-poster' WHERE snapshot_id = $1",
    "UPDATE gl_entries SET source = 'manual' WHERE snapshot_id = $1",
    "UPDATE gl_entries SET approver = 'zq-approver' WHERE snapshot_id = $1",
    "UPDATE gl_entries SET entered_at = now() WHERE snapshot_id = $1",
    "UPDATE gl_snapshots SET je_fields_available = ARRAY['posted_by'] WHERE id = $1",
)


async def _seed(migrated_db: MigratedDatabase) -> tuple[Seeder, uuid.UUID, uuid.UUID]:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = uuid.uuid4()
    await seed.run("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", tenant)
    client = await seed.value(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Probe') RETURNING id", tenant
    )
    entity = await seed.value(
        "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, 'Probe') RETURNING id",
        tenant,
        client,
    )
    snapshot = uuid.UUID(str(await seed.value(_SNAPSHOT, tenant, entity)))
    return seed, tenant, snapshot


async def test_an_earlier_snapshot_reads_every_je_field_unavailable(
    migrated_db: MigratedDatabase,
) -> None:
    seed, _, snapshot = await _seed(migrated_db)
    rows = await seed.rows("SELECT je_fields_available FROM gl_snapshots WHERE id = $1", snapshot)
    assert list(rows[0]["je_fields_available"]) == []
    lines = await seed.rows(
        "SELECT posted_by, entered_at, source, approver FROM gl_entries WHERE snapshot_id = $1",
        snapshot,
    )
    assert all(all(v is None for v in dict(r).values()) for r in lines)


@pytest.mark.parametrize("sql", _FILLS)
async def test_the_owner_cannot_fill_a_je_field_on_a_committed_row(
    migrated_db: MigratedDatabase, sql: str
) -> None:
    seed, _, snapshot = await _seed(migrated_db)
    with pytest.raises(asyncpg.PostgresError):
        await seed.run(sql, snapshot)


@pytest.mark.parametrize("sql", _FILLS)
async def test_the_app_cannot_fill_a_je_field_on_a_committed_row(
    migrated_db: MigratedDatabase, sql: str
) -> None:
    _, tenant, snapshot = await _seed(migrated_db)
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    try:
        with pytest.raises(DBAPIError):
            async with tenant_session(TenantContext(tenant, "system", "a08-t33")) as session:
                await session.execute(text(sql.replace("$1", ":s")), {"s": snapshot})
    finally:
        await dispose_engine()
