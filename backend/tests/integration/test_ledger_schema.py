"""AC-9, AC-10, AC-11, AC-20: migration 0009 and the ledger service (TASK-010a interface contract,
"Database (migration 0009)", and revision 1).

Rows are seeded as the superuser (`migrated_db.superuser_dsn`) with fresh firms per test, so tests
never need cleanup. Statements that must fail for `abacus_app` run through `tenant_session`;
triggers are proven as the superuser, who bypasses grants and row-level security. Expectations
come from the contract, not from the implementation.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Protocol, cast

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Target, uow
from abacus.modules.ledger.api import (
    LedgerLine,
    NormalisedTrialBalance,
    SnapshotRef,
    Unvalidated,
    record_snapshot,
    snapshot_view,
)
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

START = date(2025, 1, 1)
END = date(2025, 12, 31)
PULLED_AT = datetime(2026, 3, 14, 9, 26, 53, tzinfo=UTC)
APP = "test-app"
NEW_TABLES = ["connections", "sync_runs", "ledger_snapshots", "trial_balance_lines", "fulfilments"]


class Migrated(Protocol):
    owner_url: str
    app_url: str
    identity_url: str
    superuser_dsn: str


def _fingerprint() -> str:
    return hashlib.sha256(uuid.uuid4().bytes).hexdigest()


# --- seeding (superuser) -------------------------------------------------------------------------

INSERT_CONNECTION = (
    "INSERT INTO connections (tenant_id, client_entity_id, provider, status, scopes, expires_at, "
    "created_by) VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id"
)
INSERT_SNAPSHOT = (
    "INSERT INTO ledger_snapshots (tenant_id, client_entity_id, period_start, period_end, "
    "pulled_at, source, raw_fingerprint, line_count, total_debit, total_credit) "
    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING id"
)
INSERT_LINE = (
    "INSERT INTO trial_balance_lines (tenant_id, snapshot_id, account_code, account_name, "
    "debit, credit, source_ref) VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id"
)
INSERT_RUN = (
    "INSERT INTO sync_runs (tenant_id, client_entity_id, connection_id, engagement_id, "
    "request_item_id, dataset, period_start, period_end, status, raw_storage_key, "
    "raw_version_id, raw_fingerprint, raw_size_bytes, raw_pulled_at, source, snapshot_id, "
    "evidence_version_id, failure_code, started_by, finished_at) VALUES ($1, $2, $3, $4, $5, "
    "$6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20) RETURNING id"
)
INSERT_FULFILMENT = (
    "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, evidence_version_id, "
    "created_by_kind, created_by_id) VALUES ($1, $2, $3, $4, $5, $6) RETURNING id"
)
INSERT_VERSION = (
    "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, version_no, "
    "fingerprint, storage_key, storage_version_id, size_bytes, media_type, source, method, "
    "snapshot_id) VALUES ($1, $2, $3, 1, $4, $5, 'v1', 10, 'application/pdf', 'upload', "
    "'uploaded', $6) RETURNING id"
)


@dataclass(frozen=True)
class Person:
    user_id: uuid.UUID
    tenant_id: uuid.UUID


@dataclass(frozen=True)
class World:
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    entity_id: uuid.UUID
    engagement_id: uuid.UUID
    item_id: uuid.UUID
    connection_id: uuid.UUID

    @property
    def system(self) -> TenantContext:
        return TenantContext(self.tenant_id, "system", APP)


class Seeder:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    async def run(self, sql: str, *args: object) -> None:
        conn = await asyncpg.connect(self.dsn)
        try:
            await conn.execute(sql, *args)
        finally:
            await conn.close()

    async def value(self, sql: str, *args: object) -> object:
        conn = await asyncpg.connect(self.dsn)
        try:
            return await conn.fetchval(sql, *args)
        finally:
            await conn.close()

    async def rows(self, sql: str, *args: object) -> list[asyncpg.Record]:
        conn = await asyncpg.connect(self.dsn)
        try:
            return list(await conn.fetch(sql, *args))
        finally:
            await conn.close()

    async def firm(self) -> uuid.UUID:
        tenant_id = uuid.uuid4()
        await self.run(
            "INSERT INTO firms (tenant_id, name) VALUES ($1, $2)",
            tenant_id,
            f"Firm {tenant_id.hex[:8]}",
        )
        return tenant_id

    async def user(self, tenant_id: uuid.UUID) -> uuid.UUID:
        subject = f"sub-{uuid.uuid4().hex}"
        user_id = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ('https://identity.abacus.local', $1, $2, 'Test person') RETURNING id",
                subject,
                f"{subject}@example.test",
            ),
        )
        await self.run(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
            "VALUES ($1, $2, NULL, 'active')",
            tenant_id,
            user_id,
        )
        return user_id

    async def entity(self, tenant_id: uuid.UUID) -> uuid.UUID:
        client_id = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Seeded client') RETURNING id",
                tenant_id,
            ),
        )
        return cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO client_entities (tenant_id, client_id, name) "
                "VALUES ($1, $2, 'Seeded entity') RETURNING id",
                tenant_id,
                client_id,
            ),
        )

    async def engagement(
        self, tenant_id: uuid.UUID, entity_id: uuid.UUID, user_id: uuid.UUID
    ) -> uuid.UUID:
        client_id = await self.value(
            "SELECT client_id FROM client_entities WHERE id = $1", entity_id
        )
        return cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                "fiscal_period_start, fiscal_period_end, created_by) "
                "VALUES ($1, $2, $3, $4, '2025-01-01', '2025-12-31', $5) RETURNING id",
                tenant_id,
                client_id,
                entity_id,
                f"Seeded {uuid.uuid4().hex[:6]}",
                user_id,
            ),
        )

    async def item(
        self, tenant_id: uuid.UUID, engagement_id: uuid.UUID, user_id: uuid.UUID
    ) -> uuid.UUID:
        list_id = await self.value(
            "INSERT INTO request_lists (tenant_id, engagement_id) VALUES ($1, $2) "
            "ON CONFLICT (tenant_id, engagement_id) DO UPDATE SET tenant_id = $1 RETURNING id",
            tenant_id,
            engagement_id,
        )
        return cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, "
                "description, audit_area, created_by) VALUES ($1, $2, $3, 'Trial balance', "
                "'Financial reporting', $4) RETURNING id",
                tenant_id,
                engagement_id,
                list_id,
                user_id,
            ),
        )

    async def connection(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        **overrides: object,
    ) -> uuid.UUID:
        values: dict[str, object] = {
            "tenant_id": tenant_id,
            "client_entity_id": entity_id,
            "provider": "fake",
            "status": "active",
            "scopes": [],
            "expires_at": None,
            "created_by": "test-seed",
        }
        values.update(overrides)
        return cast(uuid.UUID, await self.value(INSERT_CONNECTION, *values.values()))

    async def snapshot(self, world: World, *, lines: int = 2, **overrides: object) -> uuid.UUID:
        """A snapshot and its lines, in one transaction (lines may only join their own)."""
        values: dict[str, object] = {
            "tenant_id": world.tenant_id,
            "client_entity_id": world.entity_id,
            "period_start": START,
            "period_end": END,
            "pulled_at": PULLED_AT,
            "source": "fake",
            "raw_fingerprint": _fingerprint(),
            "line_count": lines,
            "total_debit": Decimal("100.00"),
            "total_credit": Decimal("100.00"),
        }
        values.update(overrides)
        tenant_id = cast(uuid.UUID, values["tenant_id"])
        conn = await asyncpg.connect(self.dsn)
        try:
            async with conn.transaction():
                snapshot_id = cast(
                    uuid.UUID, await conn.fetchval(INSERT_SNAPSHOT, *values.values())
                )
                for n in range(lines):
                    await conn.fetchval(
                        INSERT_LINE,
                        tenant_id,
                        snapshot_id,
                        f"{1000 + n}",
                        f"Account {n}",
                        Decimal("100.00") if n == 0 else Decimal("0.00"),
                        Decimal("100.00") if n == 1 else Decimal("0.00"),
                        f"acct-{1000 + n}",
                    )
        finally:
            await conn.close()
        return snapshot_id

    async def version(
        self,
        tenant_id: uuid.UUID,
        engagement_id: uuid.UUID,
        snapshot_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        item_id = await self.value(
            "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
            "created_by_id) VALUES ($1, $2, 'Seeded evidence', 'system', 'seed') RETURNING id",
            tenant_id,
            engagement_id,
        )
        fingerprint = _fingerprint()
        return cast(
            uuid.UUID,
            await self.value(
                INSERT_VERSION,
                tenant_id,
                engagement_id,
                item_id,
                fingerprint,
                f"tenants/{tenant_id}/sha256/{fingerprint}",
                snapshot_id,
            ),
        )

    async def run_row(self, world: World, **overrides: object) -> uuid.UUID:
        values: dict[str, object] = {
            "tenant_id": world.tenant_id,
            "client_entity_id": world.entity_id,
            "connection_id": world.connection_id,
            "engagement_id": world.engagement_id,
            "request_item_id": world.item_id,
            "dataset": "trial_balance",
            "period_start": START,
            "period_end": END,
            "status": "running",
            "raw_storage_key": None,
            "raw_version_id": None,
            "raw_fingerprint": None,
            "raw_size_bytes": None,
            "raw_pulled_at": None,
            "source": None,
            "snapshot_id": None,
            "evidence_version_id": None,
            "failure_code": None,
            "started_by": "test-user",
            "finished_at": None,
        }
        values.update(overrides)
        return cast(uuid.UUID, await self.value(INSERT_RUN, *values.values()))

    async def fulfilment(self, world: World, version_id: uuid.UUID, **overrides: object) -> None:
        values: dict[str, object] = {
            "tenant_id": world.tenant_id,
            "engagement_id": world.engagement_id,
            "request_item_id": world.item_id,
            "evidence_version_id": version_id,
            "created_by_kind": "rule",
            "created_by_id": "run:test",
        }
        values.update(overrides)
        await self.value(INSERT_FULFILMENT, *values.values())

    async def count(self, sql: str, *args: object) -> int:
        return cast(int, await self.value(sql, *args))


@pytest.fixture
def seed(migrated_db: Migrated) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture
async def world(seed: Seeder) -> World:
    tenant_id = await seed.firm()
    user_id = await seed.user(tenant_id)
    entity_id = await seed.entity(tenant_id)
    engagement_id = await seed.engagement(tenant_id, entity_id, user_id)
    item_id = await seed.item(tenant_id, engagement_id, user_id)
    connection_id = await seed.connection(tenant_id, entity_id)
    return World(tenant_id, user_id, entity_id, engagement_id, item_id, connection_id)


@pytest.fixture
async def other(seed: Seeder, world: World) -> World:
    """A second entity, engagement, item and connection in the same firm."""
    entity_id = await seed.entity(world.tenant_id)
    engagement_id = await seed.engagement(world.tenant_id, entity_id, world.user_id)
    item_id = await seed.item(world.tenant_id, engagement_id, world.user_id)
    connection_id = await seed.connection(world.tenant_id, entity_id)
    return World(world.tenant_id, world.user_id, entity_id, engagement_id, item_id, connection_id)


@pytest.fixture
async def foreign(seed: Seeder) -> World:
    """Everything again, in another firm."""
    tenant_id = await seed.firm()
    user_id = await seed.user(tenant_id)
    entity_id = await seed.entity(tenant_id)
    engagement_id = await seed.engagement(tenant_id, entity_id, user_id)
    item_id = await seed.item(tenant_id, engagement_id, user_id)
    connection_id = await seed.connection(tenant_id, entity_id)
    return World(tenant_id, user_id, entity_id, engagement_id, item_id, connection_id)


@pytest.fixture(autouse=True)
async def engines(migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


# --- tables, RLS, ownership ----------------------------------------------------------------------


@pytest.mark.parametrize("table", NEW_TABLES)
async def test_ac20_the_new_tables_are_tenant_tables_with_forced_rls(
    seed: Seeder, table: str
) -> None:
    rows = await seed.rows(
        "SELECT c.relrowsecurity, c.relforcerowsecurity FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relname = $1",
        table,
    )
    assert [(r["relrowsecurity"], r["relforcerowsecurity"]) for r in rows] == [(True, True)]
    assert (
        await seed.value(
            "SELECT attnotnull FROM pg_attribute "
            "WHERE attrelid = $1::regclass AND attname = 'tenant_id'",
            table,
        )
        is True
    )


@pytest.mark.parametrize(
    ("table", "owner"),
    [
        ("connections", "connections"),
        ("sync_runs", "connections"),
        ("ledger_snapshots", "ledger"),
        ("trial_balance_lines", "ledger"),
        ("fulfilments", "requests"),
    ],
)
def test_ac20_each_new_table_is_owned_by_its_module(table: str, owner: str) -> None:
    assert sc.TABLE_OWNERS[table] == owner


@pytest.mark.parametrize("table", ["ledger_snapshots", "trial_balance_lines", "fulfilments"])
def test_ac20_ledger_and_fulfilment_tables_are_declared_insert_only(table: str) -> None:
    assert table in sc.INSERT_ONLY_TABLES


@pytest.mark.parametrize("table", ["ledger_snapshots", "trial_balance_lines"])
def test_ac20_ledger_tables_are_declared_immutable(table: str) -> None:
    assert table in sc.IMMUTABLE_TABLES


def test_ac20_the_app_may_update_only_the_declared_connection_and_run_columns() -> None:
    assert sc.APP_UPDATE_COLUMNS["connections"] == frozenset({"status"})
    assert sc.APP_UPDATE_COLUMNS["sync_runs"] == frozenset(
        {
            "status",
            "raw_storage_key",
            "raw_version_id",
            "raw_fingerprint",
            "raw_size_bytes",
            "raw_pulled_at",
            "source",
            "snapshot_id",
            "evidence_version_id",
            "failure_code",
            "finished_at",
        }
    )


def test_ac20_the_app_inserts_no_connection_columns() -> None:
    assert sc.APP_INSERT_COLUMNS["connections"] == frozenset()


@pytest.mark.parametrize("table", ["ledger_snapshots", "sync_runs", "connections"])
async def test_ac20_rls_hides_another_firms_rows_from_the_app(
    seed: Seeder, world: World, foreign: World, table: str
) -> None:
    if table == "ledger_snapshots":
        await seed.snapshot(world)
    elif table == "sync_runs":
        await seed.run_row(world)
    queries = {
        "ledger_snapshots": "SELECT id FROM ledger_snapshots",
        "sync_runs": "SELECT id FROM sync_runs",
        "connections": "SELECT id FROM connections",
    }
    async with tenant_session(foreign.system) as session:
        seen = (await session.execute(text(queries[table]))).all()
    async with tenant_session(world.system) as session:
        mine = (await session.execute(text(queries[table]))).all()
    assert mine
    assert {r.id for r in seen}.isdisjoint({r.id for r in mine})


# --- grants for abacus_app ---------------------------------------------------------------------


async def _app_error(ctx: TenantContext, statement: str, **params: object) -> str:
    with pytest.raises(DBAPIError) as raised:
        async with tenant_session(ctx) as session:
            await session.execute(text(statement), params)
    return str(raised.value)


async def _app_write(world: World, statement: str, **params: object) -> None:
    async with uow(world.system) as tx:
        await tx.session.execute(text(statement), params)
        tx.record("probe.written", target=Target("probe", world.tenant_id))


async def test_ac20_the_app_cannot_insert_a_connection(world: World) -> None:
    message = await _app_error(
        world.system,
        "INSERT INTO connections (tenant_id, client_entity_id, provider, created_by) "
        "VALUES (:t, :e, 'fake', 'test-app')",
        t=world.tenant_id,
        e=world.entity_id,
    )
    assert "permission denied" in message


async def test_ac20_the_app_cannot_delete_a_connection(world: World) -> None:
    message = await _app_error(
        world.system, "DELETE FROM connections WHERE id = :id", id=world.connection_id
    )
    assert "permission denied" in message


async def test_ac20_the_app_may_revoke_a_connection_but_change_nothing_else_of_it(
    seed: Seeder, world: World
) -> None:
    for statement in (
        "UPDATE connections SET scopes = ARRAY['x'] WHERE id = :id",
        "UPDATE connections SET provider = 'fake' WHERE id = :id",
        "UPDATE connections SET expires_at = now() WHERE id = :id",
        "UPDATE connections SET client_entity_id = client_entity_id WHERE id = :id",
        "UPDATE connections SET created_by = 'x' WHERE id = :id",
    ):
        assert "permission denied" in await _app_error(
            world.system, statement, id=world.connection_id
        )
    await _app_write(
        world, "UPDATE connections SET status = 'revoked' WHERE id = :id", id=world.connection_id
    )
    assert (
        await seed.value("SELECT status FROM connections WHERE id = $1", world.connection_id)
        == "revoked"
    )


async def test_ac20_the_app_inserts_a_run_with_only_the_listed_columns(
    seed: Seeder, world: World
) -> None:
    insert = (
        "INSERT INTO sync_runs (tenant_id, client_entity_id, connection_id, engagement_id, "
        "request_item_id, dataset, period_start, period_end, started_by{extra}) "
        "VALUES (:t, :e, :c, :g, :i, 'trial_balance', :s, :f, 'test-user'{value})"
    )
    params: dict[str, object] = {
        "t": world.tenant_id,
        "e": world.entity_id,
        "c": world.connection_id,
        "g": world.engagement_id,
        "i": world.item_id,
        "s": START,
        "f": END,
    }
    for extra, value in (
        (", status", ", 'running'"),
        (", started_at", ", now()"),
        (", raw_fingerprint", f", '{'a' * 64}'"),
        (", finished_at", ", now()"),
        (", failure_code", ", 'x'"),
    ):
        message = await _app_error(
            world.system, insert.replace("{extra}", extra).replace("{value}", value), **params
        )
        assert "permission denied" in message
    assert (
        await seed.count("SELECT count(*) FROM sync_runs WHERE tenant_id = $1", world.tenant_id)
        == 0
    )
    await _app_write(world, insert.replace("{extra}", "").replace("{value}", ""), **params)
    assert (
        await seed.count("SELECT count(*) FROM sync_runs WHERE tenant_id = $1", world.tenant_id)
        == 1
    )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE sync_runs SET tenant_id = tenant_id WHERE id = :id",
        "UPDATE sync_runs SET client_entity_id = client_entity_id WHERE id = :id",
        "UPDATE sync_runs SET connection_id = connection_id WHERE id = :id",
        "UPDATE sync_runs SET engagement_id = engagement_id WHERE id = :id",
        "UPDATE sync_runs SET request_item_id = request_item_id WHERE id = :id",
        "UPDATE sync_runs SET dataset = dataset WHERE id = :id",
        "UPDATE sync_runs SET period_start = period_start WHERE id = :id",
        "UPDATE sync_runs SET period_end = period_end WHERE id = :id",
        "UPDATE sync_runs SET started_by = started_by WHERE id = :id",
        "UPDATE sync_runs SET started_at = started_at WHERE id = :id",
        "DELETE FROM sync_runs WHERE id = :id",
    ],
)
async def test_ac20_the_app_cannot_change_what_a_run_was_asked_to_do(
    seed: Seeder, world: World, statement: str
) -> None:
    run_id = await seed.run_row(world)
    assert "permission denied" in await _app_error(world.system, statement, id=run_id)


async def test_ac20_the_app_may_update_the_result_columns_of_a_running_run(
    seed: Seeder, world: World
) -> None:
    run_id = await seed.run_row(world)
    await _app_write(
        world,
        "UPDATE sync_runs SET status = 'failed', failure_code = 'no_data', "
        "finished_at = now() WHERE id = :id",
        id=run_id,
    )
    row = (await seed.rows("SELECT * FROM sync_runs WHERE id = $1", run_id))[0]
    assert (row["status"], row["failure_code"]) == ("failed", "no_data")


@pytest.mark.parametrize("table", ["ledger_snapshots", "trial_balance_lines", "fulfilments"])
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE", "TRUNCATE"])
async def test_ac20_the_app_cannot_update_delete_or_truncate_insert_only_tables(
    seed: Seeder, world: World, table: str, operation: str
) -> None:
    snapshot_id = await seed.snapshot(world)
    version_id = await seed.version(world.tenant_id, world.engagement_id)
    await seed.fulfilment(world, version_id)
    statements = {
        ("ledger_snapshots", "UPDATE"): "UPDATE ledger_snapshots SET source = 'x'",
        ("ledger_snapshots", "DELETE"): "DELETE FROM ledger_snapshots",
        ("ledger_snapshots", "TRUNCATE"): "TRUNCATE ledger_snapshots",
        ("trial_balance_lines", "UPDATE"): "UPDATE trial_balance_lines SET account_name = 'x'",
        ("trial_balance_lines", "DELETE"): "DELETE FROM trial_balance_lines",
        ("trial_balance_lines", "TRUNCATE"): "TRUNCATE trial_balance_lines",
        ("fulfilments", "UPDATE"): "UPDATE fulfilments SET created_by_id = 'x'",
        ("fulfilments", "DELETE"): "DELETE FROM fulfilments",
        ("fulfilments", "TRUNCATE"): "TRUNCATE fulfilments",
    }
    assert "permission denied" in await _app_error(world.system, statements[(table, operation)])
    assert (
        await seed.count("SELECT count(*) FROM ledger_snapshots WHERE id = $1", snapshot_id) == 1
    )


async def test_ac20_the_app_may_insert_only_the_listed_snapshot_columns(world: World) -> None:
    message = await _app_error(
        world.system,
        "INSERT INTO ledger_snapshots (tenant_id, client_entity_id, period_start, period_end, "
        "pulled_at, source, raw_fingerprint, line_count, total_debit, total_credit, created_at) "
        "VALUES (:t, :e, :s, :f, now(), 'fake', :h, 0, 0, 0, now())",
        t=world.tenant_id,
        e=world.entity_id,
        s=START,
        f=END,
        h="a" * 64,
    )
    assert "permission denied" in message


async def test_ac20_the_app_may_insert_only_the_listed_fulfilment_columns(
    seed: Seeder, world: World
) -> None:
    version_id = await seed.version(world.tenant_id, world.engagement_id)
    message = await _app_error(
        world.system,
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, evidence_version_id, "
        "created_by_kind, created_by_id, created_at) VALUES (:t, :g, :i, :v, 'rule', 'x', now())",
        t=world.tenant_id,
        g=world.engagement_id,
        i=world.item_id,
        v=version_id,
    )
    assert "permission denied" in message


# --- immutability as superuser (trigger) -----------------------------------------------------


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE ledger_snapshots SET source = 'other' WHERE id = $1",
        "UPDATE ledger_snapshots SET line_count = 99 WHERE id = $1",
        "UPDATE ledger_snapshots SET total_debit = total_debit WHERE id = $1",
        "DELETE FROM ledger_snapshots WHERE id = $1",
    ],
)
async def test_ac20_the_trigger_rejects_changes_to_a_snapshot_even_for_the_superuser(
    seed: Seeder, world: World, statement: str
) -> None:
    snapshot_id = await seed.snapshot(world)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run(statement, snapshot_id)
    assert (
        await seed.count("SELECT count(*) FROM ledger_snapshots WHERE id = $1", snapshot_id) == 1
    )
    assert (
        await seed.value("SELECT source FROM ledger_snapshots WHERE id = $1", snapshot_id)
        == "fake"
    )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE trial_balance_lines SET account_name = 'other' WHERE snapshot_id = $1",
        "UPDATE trial_balance_lines SET debit = 1 WHERE snapshot_id = $1",
        "DELETE FROM trial_balance_lines WHERE snapshot_id = $1",
    ],
)
async def test_ac20_the_trigger_rejects_changes_to_lines_even_for_the_superuser(
    seed: Seeder, world: World, statement: str
) -> None:
    snapshot_id = await seed.snapshot(world)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run(statement, snapshot_id)
    assert (
        await seed.count(
            "SELECT count(*) FROM trial_balance_lines WHERE snapshot_id = $1", snapshot_id
        )
        == 2
    )


@pytest.mark.parametrize("table", ["ledger_snapshots", "trial_balance_lines"])
async def test_ac20_the_trigger_rejects_truncate_even_for_the_superuser(
    seed: Seeder, world: World, table: str
) -> None:
    await seed.snapshot(world)
    statements = {
        "ledger_snapshots": "TRUNCATE ledger_snapshots CASCADE",
        "trial_balance_lines": "TRUNCATE trial_balance_lines",
    }
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run(statements[table])
    assert (
        await seed.count(
            "SELECT count(*) FROM ledger_snapshots WHERE tenant_id = $1", world.tenant_id
        )
        == 1
    )


async def test_ac20_lines_cannot_be_added_to_a_finished_snapshot_even_by_the_superuser(
    seed: Seeder, world: World
) -> None:
    snapshot_id = await seed.snapshot(world, lines=2)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.value(
            INSERT_LINE,
            world.tenant_id,
            snapshot_id,
            "9999",
            "Late line",
            Decimal("0.00"),
            Decimal("0.00"),
            "acct-9999",
        )
    assert (
        await seed.count(
            "SELECT count(*) FROM trial_balance_lines WHERE snapshot_id = $1", snapshot_id
        )
        == 2
    )


async def test_ac20_lines_join_a_snapshot_made_in_the_same_transaction(
    seed: Seeder, world: World
) -> None:
    snapshot_id = await seed.snapshot(world, lines=3)
    assert (
        await seed.count(
            "SELECT count(*) FROM trial_balance_lines WHERE snapshot_id = $1", snapshot_id
        )
        == 3
    )


# --- CHECK constraints -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"total_debit": Decimal("100.00"), "total_credit": Decimal("99.99")},
        {"total_debit": Decimal("-1.00"), "total_credit": Decimal("-1.00")},
        {"period_start": END, "period_end": START},
        {"line_count": -1},
        {"raw_fingerprint": "A" * 64},
        {"raw_fingerprint": "a" * 63},
        {"raw_fingerprint": ""},
        {"source": ""},
        {"source": "s" * 101},
    ],
    ids=[
        "unbalanced",
        "negative",
        "period-reversed",
        "negative-count",
        "upper-case-fingerprint",
        "short-fingerprint",
        "empty-fingerprint",
        "empty-source",
        "long-source",
    ],
)
async def test_ac11_a_snapshot_must_be_balanced_in_period_with_a_valid_fingerprint(
    seed: Seeder, world: World, overrides: dict[str, object]
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.snapshot(world, lines=0, **overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"debit": Decimal("-0.01")},
        {"credit": Decimal("-0.01")},
        {"account_code": ""},
        {"account_code": "c" * 51},
        {"account_name": ""},
        {"account_name": "n" * 201},
        {"source_ref": ""},
        {"source_ref": "r" * 201},
    ],
)
async def test_ac20_a_line_must_have_non_negative_amounts_and_bounded_text(
    seed: Seeder, world: World, overrides: dict[str, object]
) -> None:
    values: dict[str, object] = {
        "tenant_id": world.tenant_id,
        "snapshot_id": None,
        "account_code": "1000",
        "account_name": "Cash",
        "debit": Decimal("1.00"),
        "credit": Decimal("0.00"),
        "source_ref": "acct-1000",
    }
    values.update(overrides)
    conn = await asyncpg.connect(seed.dsn)
    try:
        with pytest.raises(asyncpg.CheckViolationError):
            async with conn.transaction():
                values["snapshot_id"] = await conn.fetchval(
                    INSERT_SNAPSHOT,
                    world.tenant_id,
                    world.entity_id,
                    START,
                    END,
                    PULLED_AT,
                    "fake",
                    _fingerprint(),
                    1,
                    Decimal("0.00"),
                    Decimal("0.00"),
                )
                await conn.fetchval(INSERT_LINE, *values.values())
    finally:
        await conn.close()


@pytest.mark.parametrize(
    "overrides",
    [
        {"provider": "quickbooks"},
        {"provider": ""},
        {"status": "pending"},
        {"created_by": ""},
        {"created_by": "c" * 201},
    ],
)
async def test_ac20_a_connection_has_a_known_provider_status_and_creator(
    seed: Seeder, world: World, overrides: dict[str, object]
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.connection(world.tenant_id, world.entity_id, **overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "unknown"},
        {"dataset": "general_ledger"},
        {"period_start": END, "period_end": START},
        {"started_by": ""},
        {"raw_fingerprint": "xyz"},
        {"raw_size_bytes": -1},
        {"failure_code": "Bad Code"},
        {"failure_code": "x" * 51},
        {"source": "Bad Source"},
        # finished <=> not running
        {"status": "running", "finished_at": PULLED_AT},
        {"status": "failed", "failure_code": "no_data", "finished_at": None},
        # failure_code <=> failed
        {"status": "running", "failure_code": "no_data"},
        {"status": "failed", "failure_code": None, "finished_at": PULLED_AT},
        {"status": "failed_validation", "failure_code": None, "finished_at": PULLED_AT},
        # succeeded needs the raw payload, the snapshot and the evidence
        {"status": "succeeded", "finished_at": PULLED_AT},
    ],
    ids=[
        "status",
        "dataset",
        "period",
        "started-by",
        "fingerprint",
        "size",
        "code-format",
        "code-length",
        "source-format",
        "running-finished",
        "failed-unfinished",
        "running-with-code",
        "failed-no-code",
        "failed-validation-no-code",
        "succeeded-incomplete",
    ],
)
async def test_ac20_a_sync_run_state_must_be_consistent(
    seed: Seeder, world: World, overrides: dict[str, object]
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run_row(world, **overrides)


async def test_ac11_a_run_that_failed_validation_cannot_hold_a_snapshot(
    seed: Seeder, world: World
) -> None:
    snapshot_id = await seed.snapshot(world)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run_row(
            world,
            status="failed_validation",
            failure_code="unbalanced",
            finished_at=PULLED_AT,
            snapshot_id=snapshot_id,
        )


async def test_ac10_a_complete_succeeded_run_is_accepted(seed: Seeder, world: World) -> None:
    snapshot_id = await seed.snapshot(world)
    version_id = await seed.version(world.tenant_id, world.engagement_id, snapshot_id)
    fingerprint = _fingerprint()
    await seed.run_row(
        world,
        status="succeeded",
        finished_at=PULLED_AT,
        raw_fingerprint=fingerprint,
        snapshot_id=snapshot_id,
        evidence_version_id=version_id,
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"created_by_kind": "robot"},
        {"created_by_kind": ""},
        {"created_by_id": ""},
        {"created_by_id": "i" * 201},
    ],
)
async def test_ac20_a_fulfilment_has_a_known_kind_and_creator(
    seed: Seeder, world: World, overrides: dict[str, object]
) -> None:
    version_id = await seed.version(world.tenant_id, world.engagement_id)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.fulfilment(world, version_id, **overrides)


@pytest.mark.parametrize("kind", ["rule", "human", "agent"])
async def test_ac20_a_fulfilment_may_be_by_rule_human_or_agent(
    seed: Seeder, world: World, kind: str
) -> None:
    version_id = await seed.version(world.tenant_id, world.engagement_id)
    await seed.fulfilment(world, version_id, created_by_kind=kind)


# --- unique keys -------------------------------------------------------------------------------


async def test_ac20_the_same_pull_of_the_same_period_gives_one_snapshot(
    seed: Seeder, world: World
) -> None:
    fingerprint = _fingerprint()
    await seed.snapshot(world, raw_fingerprint=fingerprint)
    with pytest.raises(asyncpg.UniqueViolationError):
        await seed.snapshot(world, raw_fingerprint=fingerprint)
    await seed.snapshot(world, raw_fingerprint=_fingerprint())
    await seed.snapshot(world, raw_fingerprint=fingerprint, period_end=date(2025, 6, 30))


async def test_ac20_the_same_pull_may_be_snapshotted_for_another_entity(
    seed: Seeder, world: World, other: World
) -> None:
    fingerprint = _fingerprint()
    await seed.snapshot(world, raw_fingerprint=fingerprint)
    await seed.snapshot(other, raw_fingerprint=fingerprint)


async def test_ac20_an_account_code_appears_once_per_snapshot(seed: Seeder, world: World) -> None:
    conn = await asyncpg.connect(seed.dsn)
    try:
        with pytest.raises(asyncpg.UniqueViolationError):
            async with conn.transaction():
                snapshot_id = await conn.fetchval(
                    INSERT_SNAPSHOT,
                    world.tenant_id,
                    world.entity_id,
                    START,
                    END,
                    PULLED_AT,
                    "fake",
                    _fingerprint(),
                    2,
                    Decimal("0.00"),
                    Decimal("0.00"),
                )
                for _ in range(2):
                    await conn.fetchval(
                        INSERT_LINE,
                        world.tenant_id,
                        snapshot_id,
                        "1000",
                        "Cash",
                        Decimal("0.00"),
                        Decimal("0.00"),
                        f"acct-{uuid.uuid4().hex[:6]}",
                    )
    finally:
        await conn.close()


async def test_ac20_a_version_fulfils_an_item_once(seed: Seeder, world: World) -> None:
    version_id = await seed.version(world.tenant_id, world.engagement_id)
    await seed.fulfilment(world, version_id)
    with pytest.raises(asyncpg.UniqueViolationError):
        await seed.fulfilment(world, version_id)
    await seed.fulfilment(world, await seed.version(world.tenant_id, world.engagement_id))


async def test_ac20_only_one_run_per_item_and_period_may_be_running_or_succeeded(
    seed: Seeder, world: World
) -> None:
    await seed.run_row(world)
    with pytest.raises(asyncpg.UniqueViolationError):
        await seed.run_row(world)


async def test_ac20_a_succeeded_run_also_holds_the_item_and_period(
    seed: Seeder, world: World
) -> None:
    snapshot_id = await seed.snapshot(world)
    version_id = await seed.version(world.tenant_id, world.engagement_id, snapshot_id)
    await seed.run_row(
        world,
        status="succeeded",
        finished_at=PULLED_AT,
        raw_fingerprint=_fingerprint(),
        snapshot_id=snapshot_id,
        evidence_version_id=version_id,
    )
    with pytest.raises(asyncpg.UniqueViolationError):
        await seed.run_row(world)


async def test_ac20_failed_runs_do_not_block_a_new_one_and_do_not_block_each_other(
    seed: Seeder, world: World
) -> None:
    for code in ("no_data", "provider_unavailable"):
        await seed.run_row(world, status="failed", failure_code=code, finished_at=PULLED_AT)
    await seed.run_row(
        world, status="failed_validation", failure_code="unbalanced", finished_at=PULLED_AT
    )
    await seed.run_row(world)


async def test_ac20_another_period_or_item_may_run_at_the_same_time(
    seed: Seeder, world: World
) -> None:
    await seed.run_row(world)
    await seed.run_row(world, period_end=date(2025, 6, 30))
    await seed.run_row(
        world, request_item_id=await seed.item(world.tenant_id, world.engagement_id, world.user_id)
    )


# --- composite foreign keys ------------------------------------------------------------------


async def test_ac20_a_runs_connection_must_belong_to_the_runs_entity(
    seed: Seeder, world: World, other: World
) -> None:
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.run_row(world, connection_id=other.connection_id)


async def test_ac20_a_runs_engagement_must_belong_to_the_runs_entity(
    seed: Seeder, world: World, other: World
) -> None:
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.run_row(world, engagement_id=other.engagement_id)


async def test_ac20_a_runs_item_must_be_in_the_runs_engagement(
    seed: Seeder, world: World, other: World
) -> None:
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.run_row(world, request_item_id=other.item_id)


async def test_ac20_a_runs_snapshot_must_be_of_the_runs_entity(
    seed: Seeder, world: World, other: World
) -> None:
    foreign_entity_snapshot = await seed.snapshot(other)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.run_row(world, snapshot_id=foreign_entity_snapshot)


async def test_ac20_a_runs_evidence_must_be_in_the_runs_engagement(
    seed: Seeder, world: World, other: World
) -> None:
    snapshot_id = await seed.snapshot(world)
    elsewhere = await seed.version(other.tenant_id, other.engagement_id)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.run_row(
            world,
            status="succeeded",
            finished_at=PULLED_AT,
            raw_fingerprint=_fingerprint(),
            snapshot_id=snapshot_id,
            evidence_version_id=elsewhere,
        )


@pytest.mark.parametrize("what", ["connection", "engagement", "item", "entity"])
async def test_ac20_a_run_cannot_reach_into_another_firm(
    seed: Seeder, world: World, foreign: World, what: str
) -> None:
    overrides: dict[str, object] = {
        "connection": {"connection_id": foreign.connection_id},
        "engagement": {"engagement_id": foreign.engagement_id},
        "item": {"request_item_id": foreign.item_id},
        "entity": {"client_entity_id": foreign.entity_id},
    }[what]  # pyright: ignore[reportAssignmentType] -- literal dict of dicts
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.run_row(world, **overrides)


async def test_ac20_a_snapshot_must_be_for_an_entity_of_its_own_firm(
    seed: Seeder, world: World, foreign: World
) -> None:
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.snapshot(world, client_entity_id=foreign.entity_id)


async def test_ac20_a_fulfilment_ties_item_and_evidence_to_one_engagement(
    seed: Seeder, world: World, other: World
) -> None:
    elsewhere = await seed.version(other.tenant_id, other.engagement_id)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.fulfilment(world, elsewhere)
    mine = await seed.version(world.tenant_id, world.engagement_id)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.fulfilment(world, mine, engagement_id=other.engagement_id)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.fulfilment(world, mine, request_item_id=other.item_id)


async def test_ac20_a_fulfilment_cannot_reach_into_another_firm(
    seed: Seeder, world: World, foreign: World
) -> None:
    elsewhere = await seed.version(foreign.tenant_id, foreign.engagement_id)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.fulfilment(world, elsewhere)


async def test_ac10_an_evidence_versions_snapshot_must_exist_in_its_firm(
    seed: Seeder, world: World, foreign: World
) -> None:
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.version(world.tenant_id, world.engagement_id, uuid.uuid4())
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.version(world.tenant_id, world.engagement_id, await seed.snapshot(foreign))
    await seed.version(world.tenant_id, world.engagement_id, await seed.snapshot(world))


# --- forward-only runs, write-once results, connections ------------------------------------------


async def _run_error(seed: Seeder, statement: str, *args: object) -> None:
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run(statement, *args)


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "failed", "failure_code": "no_data", "finished_at": PULLED_AT},
        {"status": "failed_validation", "failure_code": "unbalanced", "finished_at": PULLED_AT},
    ],
    ids=["failed", "failed-validation"],
)
@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE sync_runs SET failure_code = 'other_code' WHERE id = $1",
        "UPDATE sync_runs SET status = 'running', failure_code = NULL, finished_at = NULL "
        "WHERE id = $1",
        "UPDATE sync_runs SET finished_at = now() WHERE id = $1",
        "UPDATE sync_runs SET started_by = 'someone-else' WHERE id = $1",
    ],
    ids=["code", "reopen", "finished-at", "started-by"],
)
async def test_ac20_a_finished_run_cannot_be_updated_at_all_even_by_the_superuser(
    seed: Seeder, world: World, overrides: dict[str, object], statement: str
) -> None:
    run_id = await seed.run_row(world, **overrides)
    await _run_error(seed, statement, run_id)
    row = (await seed.rows("SELECT status FROM sync_runs WHERE id = $1", run_id))[0]
    assert row["status"] == overrides["status"]


async def test_ac10_a_succeeded_run_is_frozen(seed: Seeder, world: World) -> None:
    snapshot_id = await seed.snapshot(world)
    version_id = await seed.version(world.tenant_id, world.engagement_id, snapshot_id)
    run_id = await seed.run_row(
        world,
        status="succeeded",
        finished_at=PULLED_AT,
        raw_fingerprint=_fingerprint(),
        snapshot_id=snapshot_id,
        evidence_version_id=version_id,
    )
    await _run_error(seed, "UPDATE sync_runs SET source = 'fake' WHERE id = $1", run_id)
    await _run_error(seed, "UPDATE sync_runs SET status = 'running' WHERE id = $1", run_id)


async def test_ac20_a_running_run_records_results_once_and_they_stay(
    seed: Seeder, world: World
) -> None:
    run_id = await seed.run_row(world)
    fingerprint = _fingerprint()
    await seed.run(
        "UPDATE sync_runs SET raw_storage_key = $2, raw_version_id = 'v1', raw_fingerprint = $3, "
        "raw_size_bytes = 5, raw_pulled_at = now(), source = 'fake' WHERE id = $1",
        run_id,
        f"tenants/{world.tenant_id}/sha256/{fingerprint}",
        fingerprint,
    )
    # unchanged values may be written again
    await seed.run("UPDATE sync_runs SET raw_version_id = 'v1' WHERE id = $1", run_id)
    for statement in (
        "UPDATE sync_runs SET raw_storage_key = 'other' WHERE id = $1",
        "UPDATE sync_runs SET raw_version_id = 'v2' WHERE id = $1",
        "UPDATE sync_runs SET raw_fingerprint = repeat('0', 64) WHERE id = $1",
        "UPDATE sync_runs SET raw_size_bytes = 6 WHERE id = $1",
        "UPDATE sync_runs SET raw_pulled_at = now() + interval '1 day' WHERE id = $1",
        "UPDATE sync_runs SET source = 'other' WHERE id = $1",
        "UPDATE sync_runs SET raw_fingerprint = NULL WHERE id = $1",
        "UPDATE sync_runs SET source = NULL WHERE id = $1",
    ):
        await _run_error(seed, statement, run_id)
    row = (await seed.rows("SELECT * FROM sync_runs WHERE id = $1", run_id))[0]
    assert (row["raw_fingerprint"], row["raw_version_id"], row["source"]) == (
        fingerprint,
        "v1",
        "fake",
    )


async def test_ac20_a_runs_snapshot_and_evidence_links_are_write_once(
    seed: Seeder, world: World
) -> None:
    run_id = await seed.run_row(world)
    first = await seed.snapshot(world)
    second = await seed.snapshot(world)
    await seed.run("UPDATE sync_runs SET snapshot_id = $2 WHERE id = $1", run_id, first)
    await _run_error(seed, "UPDATE sync_runs SET snapshot_id = $2 WHERE id = $1", run_id, second)
    await _run_error(seed, "UPDATE sync_runs SET snapshot_id = NULL WHERE id = $1", run_id)
    version_id = await seed.version(world.tenant_id, world.engagement_id, first)
    other_version = await seed.version(world.tenant_id, world.engagement_id, first)
    await seed.run(
        "UPDATE sync_runs SET evidence_version_id = $2 WHERE id = $1", run_id, version_id
    )
    await _run_error(
        seed, "UPDATE sync_runs SET evidence_version_id = $2 WHERE id = $1", run_id, other_version
    )
    await _run_error(seed, "UPDATE sync_runs SET evidence_version_id = NULL WHERE id = $1", run_id)


async def test_ac20_a_revoked_connection_stays_revoked_even_for_the_superuser(
    seed: Seeder, world: World
) -> None:
    await seed.run("UPDATE connections SET status = 'revoked' WHERE id = $1", world.connection_id)
    await _run_error(
        seed, "UPDATE connections SET status = 'active' WHERE id = $1", world.connection_id
    )
    await seed.run("UPDATE connections SET status = 'revoked' WHERE id = $1", world.connection_id)
    assert (
        await seed.value("SELECT status FROM connections WHERE id = $1", world.connection_id)
        == "revoked"
    )


async def test_ac20_an_active_connection_may_be_revoked_by_the_app(
    seed: Seeder, world: World
) -> None:
    await _app_write(
        world, "UPDATE connections SET status = 'revoked' WHERE id = :id", id=world.connection_id
    )
    assert (
        await seed.value("SELECT status FROM connections WHERE id = $1", world.connection_id)
        == "revoked"
    )


# --- the ledger service ------------------------------------------------------------------------


def _line(code: str, debit: str, credit: str) -> LedgerLine:
    return LedgerLine(code, f"Account {code}", Decimal(debit), Decimal(credit), f"acct-{code}")


def _balanced(
    *, start: date = START, end: date = END, currency: str = "USD"
) -> NormalisedTrialBalance:
    lines = (
        _line("4000", "0.00", "150.00"),
        _line("1000", "100.00", "0.00"),
        _line("1100", "50.00", "0.00"),
    )
    return NormalisedTrialBalance(
        start, end, currency, lines, Decimal("150.00"), Decimal("150.00")
    )


async def _record(
    world: World,
    tb: NormalisedTrialBalance,
    *,
    fingerprint: str,
    period: tuple[date, date] = (START, END),
    note: bool = True,
) -> SnapshotRef:
    async with uow(world.system) as tx:
        ref = await record_snapshot(
            tx,
            client_entity_id=world.entity_id,
            period_start=period[0],
            period_end=period[1],
            tb=tb,
            raw_fingerprint=fingerprint,
            pulled_at=PULLED_AT,
            source="fake",
        )
        if note:  # a repeat records nothing itself: the caller records its own event
            tx.record("ledger_snapshot.noted", target=Target("ledger_snapshot", ref.id))
        return ref


async def _actions(seed: Seeder, tenant_id: uuid.UUID) -> list[str]:
    rows = await seed.rows(
        "SELECT action FROM audit_events WHERE tenant_id = $1 ORDER BY seq", tenant_id
    )
    return [str(r["action"]) for r in rows]


async def test_ac10_record_snapshot_inserts_the_snapshot_its_lines_and_one_audit_event(
    seed: Seeder, world: World
) -> None:
    fingerprint = _fingerprint()
    ref = await _record(world, _balanced(), fingerprint=fingerprint)
    assert ref.created is True
    [row] = await seed.rows("SELECT * FROM ledger_snapshots WHERE id = $1", ref.id)
    assert row["client_entity_id"] == world.entity_id
    assert (row["period_start"], row["period_end"]) == (START, END)
    assert row["pulled_at"] == PULLED_AT
    assert (row["source"], row["raw_fingerprint"]) == ("fake", fingerprint)
    assert row["line_count"] == 3
    assert (row["total_debit"], row["total_credit"]) == (Decimal("150.00"), Decimal("150.00"))
    assert (
        await seed.count("SELECT count(*) FROM trial_balance_lines WHERE snapshot_id = $1", ref.id)
        == 3
    )
    assert await _actions(seed, world.tenant_id) == [
        "ledger_snapshot.created",
        "ledger_snapshot.noted",
    ]
    [event] = await seed.rows(
        "SELECT actor_kind, actor_id, after_ref::text AS after FROM audit_events "
        "WHERE tenant_id = $1 AND action = 'ledger_snapshot.created'",
        world.tenant_id,
    )
    assert (event["actor_kind"], event["actor_id"]) == ("system", APP)
    after = cast(dict[str, object], json.loads(event["after"]))
    assert after["client_entity_id"] == str(world.entity_id)
    assert after["raw_fingerprint"] == fingerprint


async def test_ac20_recording_the_same_pull_again_returns_the_existing_snapshot_quietly(
    seed: Seeder, world: World
) -> None:
    fingerprint = _fingerprint()
    first = await _record(world, _balanced(), fingerprint=fingerprint)
    again = await _record(world, _balanced(), fingerprint=fingerprint)
    assert again == SnapshotRef(first.id, created=False)
    assert (
        await seed.count(
            "SELECT count(*) FROM ledger_snapshots WHERE tenant_id = $1", world.tenant_id
        )
        == 1
    )
    assert (
        await seed.count(
            "SELECT count(*) FROM trial_balance_lines WHERE tenant_id = $1", world.tenant_id
        )
        == 3
    )
    assert (await _actions(seed, world.tenant_id)).count("ledger_snapshot.created") == 1


async def test_ac20_another_fingerprint_or_period_is_another_snapshot(
    seed: Seeder, world: World
) -> None:
    first = await _record(world, _balanced(), fingerprint=_fingerprint())
    second = await _record(world, _balanced(), fingerprint=_fingerprint())
    half = (START, date(2025, 6, 30))
    third = await _record(world, _balanced(end=half[1]), fingerprint=_fingerprint(), period=half)
    assert len({first.id, second.id, third.id}) == 3


@pytest.mark.parametrize(
    "tb",
    [
        NormalisedTrialBalance(
            START,
            END,
            "USD",
            (_line("1000", "100.00", "0.00"), _line("4000", "0.00", "90.00")),
            Decimal("100.00"),
            Decimal("90.00"),
        ),
        NormalisedTrialBalance(
            START,
            END,
            "USD",
            (_line("1000", "100.00", "0.00"), _line("4000", "0.00", "100.00")),
            Decimal("1.00"),
            Decimal("1.00"),
        ),
        NormalisedTrialBalance(START, END, "USD", (), Decimal("0.00"), Decimal("0.00")),
        _balanced(currency="EUR"),
        _balanced(start=date(2024, 1, 1), end=date(2024, 12, 31)),
    ],
    ids=["unbalanced", "control-totals", "empty", "currency", "period"],
)
async def test_ac11_record_snapshot_revalidates_and_stores_nothing_unvalidated(
    seed: Seeder, world: World, tb: NormalisedTrialBalance
) -> None:
    with pytest.raises(Unvalidated):
        await _record(world, tb, fingerprint=_fingerprint(), note=False)
    assert (
        await seed.count(
            "SELECT count(*) FROM ledger_snapshots WHERE tenant_id = $1", world.tenant_id
        )
        == 0
    )
    assert (
        await seed.count("SELECT count(*) FROM audit_events WHERE tenant_id = $1", world.tenant_id)
        == 0
    )


async def test_ac11_record_snapshot_validates_against_the_period_it_is_given(
    seed: Seeder, world: World
) -> None:
    # the document says 2025, the run asked for 2024: the document is for the wrong period
    with pytest.raises(Unvalidated):
        await _record(
            world,
            _balanced(),
            fingerprint=_fingerprint(),
            period=(date(2024, 1, 1), date(2024, 12, 31)),
            note=False,
        )
    assert (
        await seed.count(
            "SELECT count(*) FROM ledger_snapshots WHERE tenant_id = $1", world.tenant_id
        )
        == 0
    )


async def test_ac10_snapshot_view_returns_the_snapshot_with_its_lines_sorted_by_code(
    seed: Seeder, world: World
) -> None:
    fingerprint = _fingerprint()
    ref = await _record(world, _balanced(), fingerprint=fingerprint)
    view = await snapshot_view(world.system, ref.id)
    assert view.id == ref.id
    assert view.client_entity_id == world.entity_id
    assert (view.period_start, view.period_end) == (START, END)
    assert view.pulled_at == PULLED_AT
    assert (view.source, view.raw_fingerprint) == ("fake", fingerprint)
    assert [line.account_code for line in view.lines] == ["1000", "1100", "4000"]
    assert [(line.account_name, line.debit, line.credit) for line in view.lines] == [
        ("Account 1000", Decimal("100.00"), Decimal("0.00")),
        ("Account 1100", Decimal("50.00"), Decimal("0.00")),
        ("Account 4000", Decimal("0.00"), Decimal("150.00")),
    ]


async def test_ac20_snapshot_view_of_an_unknown_snapshot_is_not_found(world: World) -> None:
    with pytest.raises(NotFound):
        await snapshot_view(world.system, uuid.uuid4())


async def test_ac20_snapshot_view_cannot_cross_firms(
    seed: Seeder, world: World, foreign: World
) -> None:
    ref = await _record(world, _balanced(), fingerprint=_fingerprint())
    with pytest.raises(NotFound):
        await snapshot_view(foreign.system, ref.id)


# --- downgrade ---------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def test_ac20_downgrading_0009_is_refused_while_connections_or_ledger_data_exist(
    private_db: sc.Database,
) -> None:
    async def seed_connection() -> tuple[uuid.UUID, uuid.UUID]:
        conn = await asyncpg.connect(private_db.superuser_dsn)
        try:
            tenant_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Downgrade')", tenant_id
            )
            client_id = await conn.fetchval(
                "INSERT INTO clients (tenant_id, name) VALUES ($1, 'c') RETURNING id", tenant_id
            )
            entity_id = cast(
                uuid.UUID,
                await conn.fetchval(
                    "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, "
                    "'e') RETURNING id",
                    tenant_id,
                    client_id,
                ),
            )
            await conn.execute(
                "INSERT INTO connections (tenant_id, client_entity_id, provider, created_by) "
                "VALUES ($1, $2, 'fake', 'test-seed')",
                tenant_id,
                entity_id,
            )
            return tenant_id, entity_id
        finally:
            await conn.close()

    async def swap_connection_for_snapshot(tenant_id: uuid.UUID, entity_id: uuid.UUID) -> None:
        conn = await asyncpg.connect(private_db.superuser_dsn)
        try:
            await conn.execute("DELETE FROM connections WHERE tenant_id = $1", tenant_id)
            await conn.execute(
                INSERT_SNAPSHOT.replace(" RETURNING id", ""),
                tenant_id,
                entity_id,
                START,
                END,
                PULLED_AT,
                "fake",
                _fingerprint(),
                0,
                Decimal("0.00"),
                Decimal("0.00"),
            )
        finally:
            await conn.close()

    tenant_id, entity_id = asyncio.run(seed_connection())
    with pytest.raises(DBAPIError, match="refusing to downgrade"):
        migrate(private_db.owner_url, "0008", down=True)
    assert asyncio.run(_current_revision(private_db)) == "0009"
    asyncio.run(swap_connection_for_snapshot(tenant_id, entity_id))
    with pytest.raises(DBAPIError, match="refusing to downgrade"):
        migrate(private_db.owner_url, "0008", down=True)
    assert asyncio.run(_current_revision(private_db)) == "0009"


async def _current_revision(database: sc.Database) -> str:
    conn = await asyncpg.connect(database.superuser_dsn)
    try:
        return str(await conn.fetchval("SELECT version_num FROM alembic_version"))
    finally:
        await conn.close()
