"""Q-02-T21 against Postgres (migration 0106; AC-26): a firm's audit events seal into chained
checkpoints, the verifier holds on an unaltered log, and altering one audit row makes it report
that checkpoint. The chain is sealed and verified as the app role; the tampering is the
superuser's, with the immutability trigger disabled for the moment it takes."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus.kernel.uow import Target, uow
from abacus.kernel.uow.chain import (
    LEAF_V1_COLUMNS,
    chain_hash,
    latest_checkpoint,
    leaf,
    merkle_root,
    seal_checkpoint,
    verify_chain,
)

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _events(tenant: uuid.UUID, n: int) -> None:
    for _ in range(n):
        async with uow(TenantContext(tenant, "system", "probe")) as tx:
            tx.record("probe.recorded", target=Target("probe", uuid.uuid4()))


async def _tamper(seed: Seeder, sql: str, tenant: uuid.UUID, *args: object) -> None:
    """As the events' own actor, so the row's actor CHECK still holds; only the content lies."""
    await seed.run("ALTER TABLE audit_events DISABLE TRIGGER USER")
    try:
        await seed.as_actor(tenant, ("system", "probe"), sql, tenant, *args)
    finally:
        await seed.run("ALTER TABLE audit_events ENABLE TRIGGER USER")


def test_ac26_the_merkle_root_and_chain_are_deterministic() -> None:
    a, b, c = (bytes([n]) * 32 for n in (1, 2, 3))
    assert merkle_root([a]) == a
    assert merkle_root([a, b, c]) == merkle_root([a, b, c])
    assert merkle_root([a, b, c]) != merkle_root([a, c, b])
    first = chain_hash(None, a, 1, 3, 3)
    assert chain_hash(first, b, 4, 4, 1) != chain_hash(None, b, 4, 4, 1)
    with pytest.raises(ValueError):
        merkle_root([])


def test_ac26_the_leaf_covers_both_clocks() -> None:
    assert {"occurred_at", "effective_at"} <= set(LEAF_V1_COLUMNS)
    row: dict[str, object] = {column: None for column in LEAF_V1_COLUMNS}
    other = {**row, "effective_at": "2026-09-14T09:41:00+00:00"}
    assert leaf(row) != leaf(other)


async def test_q02t21_a_new_audit_column_must_join_the_leaf(seed: Seeder) -> None:
    rows = await seed.rows(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'audit_events'"
    )
    # R7: a column the canonical form doesn't list means leaf version 2, in the same change.
    assert {str(r["column_name"]) for r in rows} == set(LEAF_V1_COLUMNS)


async def test_ac26_checkpoints_chain_and_an_unaltered_log_verifies(seed: Seeder) -> None:
    tenant = await seed.firm()
    await _events(tenant, 5)
    first = await seal_checkpoint(tenant, settle_seconds=0)
    assert first is not None and first.checkpoint_no == 1 and first.event_count == 5
    assert first.prev_chain_hash is None
    assert await seal_checkpoint(tenant, settle_seconds=0) is None  # nothing new
    await _events(tenant, 3)
    second = await seal_checkpoint(tenant, settle_seconds=0)
    assert second is not None and second.prev_chain_hash == first.chain_hash
    assert second.seq_from > first.seq_to
    assert await latest_checkpoint(tenant) == second
    assert await verify_chain(tenant) == []


async def test_ac26_events_inside_the_settle_window_wait_for_the_next_run(seed: Seeder) -> None:
    tenant = await seed.firm()
    await _events(tenant, 2)
    assert await seal_checkpoint(tenant, settle_seconds=3600) is None


async def test_ac26_altering_one_audit_row_names_its_checkpoint(seed: Seeder) -> None:
    tenant = await seed.firm()
    await _events(tenant, 4)
    first = await seal_checkpoint(tenant, settle_seconds=0)
    await _events(tenant, 4)
    second = await seal_checkpoint(tenant, settle_seconds=0)
    assert first is not None and second is not None
    await _tamper(
        seed,
        "UPDATE audit_events SET action = 'probe.forged' WHERE tenant_id = $1 AND seq = $2",
        tenant,
        second.seq_from,
    )
    assert await verify_chain(tenant) == [2]


async def test_ac26_a_removed_row_is_reported_too(seed: Seeder) -> None:
    tenant = await seed.firm()
    await _events(tenant, 3)
    sealed = await seal_checkpoint(tenant, settle_seconds=0)
    assert sealed is not None
    await _tamper(
        seed, "DELETE FROM audit_events WHERE tenant_id = $1 AND seq = $2", tenant, sealed.seq_to
    )
    assert await verify_chain(tenant) == [1]


async def test_ac26_checkpoints_are_insert_only_and_per_firm(seed: Seeder) -> None:
    tenant, other = await seed.firm(), await seed.firm()
    await _events(tenant, 1)
    assert await seal_checkpoint(tenant, settle_seconds=0) is not None
    assert await latest_checkpoint(other) is None
    with pytest.raises(Exception, match=r"permission denied|insert-only"):
        async with tenant_session(TenantContext(tenant, "system", "probe")) as session:
            await session.execute(text("UPDATE audit_checkpoints SET event_count = 9"))
    with pytest.raises(Exception, match="insert-only"):
        await seed.run("DELETE FROM audit_checkpoints WHERE tenant_id = $1", tenant)
