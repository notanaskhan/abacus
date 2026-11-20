"""TASK-8744 (DEC-5734; migration 0987): firms whose names share initials get distinct tenant
codes, one after another and at the same time. Before 0987 `provision_firm`'s insert ran with
`app.tenant_id` set to the new tenant, the code probe saw no other firm under FORCE RLS, and the
second firm died on the `firms_tenant_code` unique index."""

from __future__ import annotations

import asyncio
import uuid

import asyncpg

from .conftest import MigratedDatabase

PROVISION = "SELECT provision_firm($1, true, 'us', 'America/Chicago', $2, 'race-op')"


def _ops_dsn(db: MigratedDatabase) -> str:
    return db.superuser_dsn.replace("postgres:postgres@", "abacus_ops:abacusops@", 1)


def _name() -> str:
    # A digit-led middle word keeps the initials unique to this test run ('q' + digit + 'r').
    return f"Qz {uuid.uuid4().int % 10}{uuid.uuid4().hex[:4]} Race"


async def _codes(db: MigratedDatabase, tenants: list[uuid.UUID]) -> list[str]:
    su = await asyncpg.connect(db.superuser_dsn)
    try:
        rows = await su.fetch(
            "SELECT tenant_code FROM firms WHERE tenant_id = ANY($1::uuid[]) ORDER BY tenant_code",
            tenants,
        )
    finally:
        await su.close()
    return [r["tenant_code"] for r in rows]


async def test_a_second_firm_with_the_same_initials_takes_the_next_number(
    migrated_db: MigratedDatabase,
) -> None:
    name = _name()
    ops = await asyncpg.connect(_ops_dsn(migrated_db))
    try:
        first = await ops.fetchval(PROVISION, name, f"seq-{uuid.uuid4().hex}")
        second = await ops.fetchval(PROVISION, name, f"seq-{uuid.uuid4().hex}")
    finally:
        await ops.close()
    codes = await _codes(migrated_db, [first, second])
    assert len(set(codes)) == 2
    assert [c[-2:] for c in codes] == ["01", "02"]


async def test_concurrent_firms_with_the_same_initials_get_distinct_codes(
    migrated_db: MigratedDatabase,
) -> None:
    name = _name()
    first = await asyncpg.connect(_ops_dsn(migrated_db))
    second = await asyncpg.connect(_ops_dsn(migrated_db))
    try:
        held = first.transaction()
        await held.start()
        tenant_a = await first.fetchval(PROVISION, name, f"race-{uuid.uuid4().hex}")
        # The second provision waits on the unique index while the first is uncommitted.
        pending = asyncio.ensure_future(
            second.fetchval(PROVISION, name, f"race-{uuid.uuid4().hex}")
        )
        await asyncio.sleep(0.3)
        assert not pending.done()
        await held.commit()
        tenant_b = await asyncio.wait_for(pending, timeout=10)
    finally:
        await first.close()
        await second.close()
    assert len(set(await _codes(migrated_db, [tenant_a, tenant_b]))) == 2
