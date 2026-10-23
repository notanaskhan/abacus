"""Q-02-T27: independent acceptance tests for the audit hash chain (ADR-078; Q-02-T21, AC-26).

Written apart from Q-02-T21's own suite, against the public verifier only: a tampered row, a late
commit inside a closed range and a published anchor that no longer matches each make the verifier
fail with the checkpoint number, and a logical restore of the firm's rows into a fresh database
verifies clean."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg
import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import Target, uow
from abacus.kernel.uow.chain import seal_checkpoint, verify_anchor, verify_chain
from abacus_tools.quality import schema_check

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

ACTOR = ("system", "chain-probe")
# Every leaf column (chain.LEAF_V1_COLUMNS), in the order the statements below name them.
_COLUMNS = (
    "id",
    "tenant_id",
    "seq",
    "occurred_at",
    "effective_at",
    "actor_kind",
    "actor_id",
    "action",
    "target_type",
    "target_id",
    "before_ref",
    "after_ref",
    "trace_id",
    "engagement_id",
    "work_item_id",
    "on_behalf_of_user_id",
    "policy_ref",
)
_SELECT_EVENTS = (
    "SELECT id, tenant_id, seq, occurred_at, effective_at, actor_kind, actor_id, action, "
    "target_type, target_id, before_ref, after_ref, trace_id, engagement_id, work_item_id, "
    "on_behalf_of_user_id, policy_ref FROM audit_events WHERE tenant_id = $1 ORDER BY seq"
)
_RESTORE_EVENT = (
    "INSERT INTO audit_events (id, tenant_id, seq, occurred_at, effective_at, actor_kind, "
    "actor_id, action, target_type, target_id, before_ref, after_ref, trace_id, engagement_id, "
    "work_item_id, on_behalf_of_user_id, policy_ref) OVERRIDING SYSTEM VALUE VALUES ($1, $2, $3, "
    "$4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)"
)


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _record(tenant: uuid.UUID, n: int) -> None:
    for _ in range(n):
        async with uow(TenantContext(tenant, *ACTOR)) as tx:
            tx.record("chain_probe.recorded", target=Target("chain_probe", uuid.uuid4()))


async def _sealed(tenant: uuid.UUID, rounds: int, per_round: int = 3) -> list[int]:
    numbers: list[int] = []
    for _ in range(rounds):
        await _record(tenant, per_round)
        sealed = await seal_checkpoint(tenant, settle_seconds=0)
        assert sealed is not None
        numbers.append(sealed.checkpoint_no)
    return numbers


async def _as_actor(seed: Seeder, sql: str, tenant: uuid.UUID, *args: object) -> None:
    """The change a forger with database access would make: triggers off, the row's own actor.
    The statement's `$1` is the tenant."""
    await seed.run("ALTER TABLE audit_events DISABLE TRIGGER USER")
    try:
        await seed.as_actor(tenant, ACTOR, sql, tenant, *args)
    finally:
        await seed.run("ALTER TABLE audit_events ENABLE TRIGGER USER")


async def _range(seed: Seeder, tenant: uuid.UUID, no: int) -> tuple[int, int]:
    row = (
        await seed.rows(
            "SELECT seq_from, seq_to FROM audit_checkpoints "
            "WHERE tenant_id = $1 AND checkpoint_no = $2",
            tenant,
            no,
        )
    )[0]
    return int(row["seq_from"]), int(row["seq_to"])


async def test_q02t27_a_tampered_target_names_its_checkpoint(seed: Seeder) -> None:
    tenant = await seed.firm()
    first, second, third = await _sealed(tenant, 3)
    lo, _ = await _range(seed, tenant, second)
    await _as_actor(
        seed,
        "UPDATE audit_events SET target_id = $2 WHERE tenant_id = $1 AND seq = $3",
        tenant,
        str(uuid.uuid4()),
        lo,
    )
    assert await verify_chain(tenant) == [second]
    assert first not in await verify_chain(tenant) and third not in await verify_chain(tenant)


async def test_q02t27_a_back_dated_business_time_is_caught(seed: Seeder) -> None:
    tenant = await seed.firm()
    [only] = await _sealed(tenant, 1)
    _, hi = await _range(seed, tenant, only)
    await _as_actor(
        seed,
        "UPDATE audit_events SET effective_at = effective_at - interval '1 day' "
        "WHERE tenant_id = $1 AND seq = $2",
        tenant,
        hi,
    )
    assert await verify_chain(tenant) == [only]


async def test_q02t27_a_late_commit_inside_a_closed_range_is_flagged(seed: Seeder) -> None:
    tenant = await seed.firm()
    await _record(tenant, 2)
    # A sequence value no committed row holds: a transaction that took it and committed late.
    gap = int(
        str(await seed.value("SELECT nextval(pg_get_serial_sequence('audit_events', 'seq'))"))
    )
    await _record(tenant, 2)
    sealed = await seal_checkpoint(tenant, settle_seconds=0)
    assert sealed is not None and sealed.seq_from < gap < sealed.seq_to
    assert await verify_chain(tenant) == []
    await _as_actor(
        seed,
        "INSERT INTO audit_events (tenant_id, seq, actor_kind, actor_id, action, target_type, "
        "target_id) OVERRIDING SYSTEM VALUE "
        "VALUES ($1, $2, 'system', 'chain-probe', 'chain_probe.recorded', 'chain_probe', $3)",
        tenant,
        gap,
        str(uuid.uuid4()),
    )
    assert await verify_chain(tenant) == [sealed.checkpoint_no]


async def test_q02t27_a_published_anchor_fails_once_its_history_changes(seed: Seeder) -> None:
    tenant = await seed.firm()
    first, second = await _sealed(tenant, 2)
    published = await seed.value(
        "SELECT chain_hash FROM audit_checkpoints WHERE tenant_id = $1 AND checkpoint_no = $2",
        tenant,
        second,
    )
    anchor = bytes(published)  # type: ignore[arg-type]  # asyncpg returns bytea as bytes
    assert await verify_anchor(tenant, second, anchor)
    assert not await verify_anchor(tenant, second, bytes(32))  # a forged anchor
    assert not await verify_anchor(tenant, second + 1, anchor)  # a checkpoint that isn't there
    lo, _ = await _range(seed, tenant, first)
    await _as_actor(
        seed,
        "UPDATE audit_events SET action = 'chain_probe.forged' WHERE tenant_id = $1 AND seq = $2",
        tenant,
        lo,
    )
    # The anchor names checkpoint 2, but checkpoint 1 below it changed: it no longer holds.
    assert await verify_chain(tenant) == [first]
    assert not await verify_anchor(tenant, second, anchor)


def _database(url: str, name: str) -> str:
    return url.rsplit("/", 1)[0] + "/" + name


async def test_q02t27_a_restored_snapshot_verifies_clean(
    migrated_db: MigratedDatabase, seed: Seeder
) -> None:
    tenant = await seed.firm()
    await _sealed(tenant, 3)
    assert await verify_chain(tenant) == []
    events = await seed.rows(_SELECT_EVENTS, tenant)
    checkpoints = await seed.rows(
        "SELECT * FROM audit_checkpoints WHERE tenant_id = $1 ORDER BY checkpoint_no", tenant
    )
    firm = (await seed.rows("SELECT * FROM firms WHERE tenant_id = $1", tenant))[0]

    name = f"restored_{uuid.uuid4().hex[:12]}"
    await seed.run('CREATE DATABASE "' + name + '"')
    superuser = _database(migrated_db.superuser_dsn, name)
    try:
        migrations = Path(schema_check.__file__).parents[3] / "migrations"
        await schema_check._run_sql(  # pyright: ignore[reportPrivateUsage] -- the bootstrap path schema_check uses
            superuser, migrations / "bootstrap.sql", migrations / "bootstrap-local.sql"
        )
        await asyncio.to_thread(
            schema_check.migrate, _database(migrated_db.owner_url, name), "head"
        )
        conn = await asyncpg.connect(superuser)
        try:
            await conn.execute("ALTER TABLE audit_events DISABLE TRIGGER USER")
            await conn.execute(
                "INSERT INTO firms (tenant_id, name) VALUES ($1, $2)", tenant, firm["name"]
            )
            for row in events:
                async with conn.transaction():
                    for setting, value in (
                        ("app.tenant_id", str(tenant)),
                        ("app.actor_kind", row["actor_kind"]),
                        ("app.actor_id", row["actor_id"]),
                        ("app.on_behalf_of", str(row["on_behalf_of_user_id"] or "")),
                    ):
                        await conn.execute("SELECT set_config($1, $2, true)", setting, value)
                    await conn.execute(_RESTORE_EVENT, *(row[c] for c in _COLUMNS))
            await conn.execute("ALTER TABLE audit_events ENABLE TRIGGER USER")
            for c in checkpoints:
                await conn.execute(
                    "INSERT INTO audit_checkpoints (tenant_id, checkpoint_no, seq_from, seq_to, "
                    "event_count, leaf_version, merkle_root, prev_chain_hash, chain_hash) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
                    tenant,
                    c["checkpoint_no"],
                    c["seq_from"],
                    c["seq_to"],
                    c["event_count"],
                    c["leaf_version"],
                    c["merkle_root"],
                    c["prev_chain_hash"],
                    c["chain_hash"],
                )
        finally:
            await conn.close()
        await dispose_engine()
        configure_engine(_database(migrated_db.app_url, name))
        assert await verify_chain(tenant) == []
    finally:
        await dispose_engine()
        configure_engine(migrated_db.app_url)
        await seed.run('DROP DATABASE IF EXISTS "' + name + '" WITH (FORCE)')
