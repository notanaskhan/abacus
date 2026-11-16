"""C-01-T48 (TASK-8307; ADR-078) against Postgres: the CAS ledger's monthly snapshots are
immutable to the app and invisible across tenants (SPEC-655 AC-32, ADR-004, ADR-014).

ac-test-author: ayushkbhatia
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest
from sqlalchemy import text

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_c01t18_ledger_reads import (
    _record,  # pyright: ignore[reportPrivateUsage] -- C-01-T18's month writer
    _tb,  # pyright: ignore[reportPrivateUsage] -- C-01-T18's trial balance builder
)
from .test_c01t18_ledger_reads import seeded as seeded

pytestmark = pytest.mark.asyncio
SYSTEM = ("system", "connections:ledger_sync")


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.fixture
async def app(migrated_db: MigratedDatabase) -> AsyncIterator[Seeder]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield Seeder(_dsn(migrated_db.app_url))
    await dispose_engine()


async def test_a_monthly_snapshot_never_changes_and_is_never_deleted(
    seeded: tuple[Seeder, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID], app: Seeder
) -> None:
    _, tenant, entity, _, _ = seeded
    snapshot = await _record(
        tenant, entity, "2026-08",
        _tb("2026-08", "50000.00", "4000.00", "40000.00", "9000.00", "3000.00"), 2, "100.00",
    )  # fmt: skip
    for statement in (
        "UPDATE ledger_snapshots SET period = '2026-07' WHERE id = $1",
        "DELETE FROM ledger_snapshots WHERE id = $1",
        "UPDATE gl_entries SET debit = 0 WHERE snapshot_id = $1",
        "DELETE FROM gl_entries WHERE snapshot_id = $1",
    ):
        with pytest.raises((asyncpg.InsufficientPrivilegeError, asyncpg.RaiseError)):
            await app.as_actor(tenant, SYSTEM, statement, snapshot)


async def test_another_tenant_never_sees_the_snapshot(
    seeded: tuple[Seeder, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID], app: Seeder
) -> None:
    seed, tenant, entity, _, _ = seeded
    snapshot = await _record(
        tenant, entity, "2026-08",
        _tb("2026-08", "50000.00", "4000.00", "40000.00", "9000.00", "3000.00"), 1, "100.00",
    )  # fmt: skip
    other = uuid.uuid4()
    await seed.run("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Other')", other)
    async with tenant_session(TenantContext(other, "system", "probe")) as session:
        seen = await session.scalar(
            text("SELECT count(*) FROM ledger_snapshots WHERE id = :s"), {"s": snapshot}
        )
        rows = await session.scalar(
            text("SELECT count(*) FROM gl_entries WHERE snapshot_id = :s"), {"s": snapshot}
        )
    assert (seen, rows) == (0, 0)
