"""A-02-T12 (TASK-1339; SPEC-333 AC-49, AC-50; AC-13.1, AC-13.3) against Postgres: migration 0194,
the operator's catalogue load and sealed integration secrets.

The row's acceptance: an unregistered adapter is never listed as available (the unit suite
covers the registry; here the rows come from the real definer), secrets are sealed with the
tenant key and the owner id as associated data, and a dry-run load reports adds and changes
without writing. Also: the app holds no privilege on the catalogue and cannot run the load; a
second live install of one app is refused; deleting a secret removes its only sealed copy.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import cast

import asyncpg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from abacus.kernel.crypto import DecryptionError, open_sealed
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import uow
from abacus.modules.integrations.api import (
    CatalogDocument,
    catalog_rows,
    erase_secret,
    listed,
    open_secret,
    store_secret,
)
from abacus.modules.integrations.secrets import binding
from abacus_tools import integration_catalog as ops
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

REVISION = "0194"
_SCRIPTS = ScriptDirectory.from_config(
    Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
)
BEFORE = cast(str, _SCRIPTS.get_revision(REVISION).down_revision)
OPERATOR = "probe-op"


def _row(key: str, provider: str | None, **over: object) -> dict[str, object]:
    row: dict[str, object] = {
        "key": key,
        "name": key.replace("_", " ").title(),
        "category": "ledger",
        "ownership_mode": "client_authorised",
        "surfaces": ["portal"],
        "connector_provider": provider,
        "adapter_key": provider,
        "listing_status": "available",
        "consent_copy": {
            "title": "Connect",
            "will": ["Read your ledger"],
            "wont": ["Post entries"],
            "authorization": "I'm authorized to connect this account.",
            "continue_label": "Continue",
        },
        "consent_version": 1,
        "scopes": {"read": [{"code": "ledger.read", "label": "Read ledger"}]},
        "icon": "book-open",
        "tone": "olive",
        "sort_order": 10,
    }
    row.update(over)
    return row


def _firm_row(key: str) -> dict[str, object]:
    """A firm-installed app (T-01's CCH bridge shape): no provider, no consent sheet."""
    return _row(
        key,
        None,
        ownership_mode="firm",
        consent_copy=None,
        consent_version=None,
        surfaces=["workbench"],
    )


def _document(*rows: dict[str, object]) -> CatalogDocument:
    return CatalogDocument.model_validate({"version": 1, "rows": list(rows)})


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


@pytest.fixture
async def engines(db: sc.Database) -> AsyncIterator[None]:
    await dispose_engine()
    configure_engine(db.app_url)
    yield
    await dispose_engine()


def _ops(db: sc.Database) -> str:
    # bootstrap-local.sql gives abacus_ops the local password; the role has EXECUTE only.
    return db.app_url.replace("abacus_app:abacusapp", "abacus_ops:abacusops", 1)


def _app(db: sc.Database) -> str:
    return db.app_url.replace("postgresql+asyncpg://", "postgresql://")


async def _firm(db: sc.Database) -> TenantContext:
    conn = await asyncpg.connect(db.superuser_dsn)
    try:
        tenant_id = uuid.uuid4()
        await conn.execute("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Ints')", tenant_id)
        subject = f"sub-{uuid.uuid4().hex}"
        user_id = cast(
            uuid.UUID,
            await conn.fetchval(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ('https://identity.abacus.local', $1, $2, 'Test person') RETURNING id",
                subject,
                f"{subject}@example.test",
            ),
        )
        await conn.execute(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
            "VALUES ($1, $2, 'firm_admin', 'active')",
            tenant_id,
            user_id,
        )
        return TenantContext(tenant_id, "human", str(user_id))
    finally:
        await conn.close()


async def _install(db: sc.Database, tenant: TenantContext, key: str) -> uuid.UUID:
    conn = await asyncpg.connect(_app(db))
    try:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.tenant_id', $1, true)", str(tenant.tenant_id)
            )
            return cast(
                uuid.UUID,
                await conn.fetchval(
                    "INSERT INTO firm_integrations (tenant_id, catalog_key, mode, created_by) "
                    "VALUES ($1, $2, 'token', $3) RETURNING id",
                    tenant.tenant_id,
                    key,
                    uuid.UUID(tenant.actor_id),
                ),
            )
    finally:
        await conn.close()


def test_the_migration_passes_up_down_up(db: sc.Database) -> None:
    migrate(db.owner_url, BEFORE, down=True)
    migrate(db.owner_url, "head")
    migrate(db.owner_url, BEFORE, down=True)
    migrate(db.owner_url, "head")
    assert sc.check(db.owner_url, db.app_url) == []


async def test_ac50_a_dry_run_reports_adds_and_changes_and_writes_nothing(db: sc.Database) -> None:
    first = _document(_row("quickbooks_online", "quickbooks_online"))
    loaded = await ops.load(_ops(db), first, OPERATOR, dry_run=False)
    assert loaded.written == (("quickbooks_online", "added"),)
    before = await ops.current_rows(_ops(db))

    second = _document(
        _row("quickbooks_online", "quickbooks_online", listing_status="coming_soon"),
        _row("netsuite", None, ownership_mode="firm", adapter_key=None, sort_order=20),
    )
    dry = await ops.load(_ops(db), second, OPERATOR, dry_run=True)
    assert dry.plan.added == ("netsuite",)
    assert dry.plan.changed == (("quickbooks_online", ("listing_status",)),)
    assert dry.written == ()
    assert await ops.current_rows(_ops(db)) == before  # nothing written

    # The real load makes exactly the planned changes, and bumps the changed row's revision.
    real = await ops.load(_ops(db), second, OPERATOR, dry_run=False)
    assert sorted(real.written) == [("netsuite", "added"), ("quickbooks_online", "changed")]
    assert real.matches_plan and dry.matches_plan and loaded.matches_plan
    after = {str(r["key"]): r for r in await ops.current_rows(_ops(db))}
    assert after["quickbooks_online"]["revision"] == 2
    assert after["quickbooks_online"]["listing_status"] == "coming_soon"
    # Loading the same document again plans and writes nothing.
    again = await ops.load(_ops(db), second, OPERATOR, dry_run=False)
    assert (again.plan.writes, again.written) == (False, ())


async def test_the_app_reads_the_catalogue_only_through_the_definer(
    db: sc.Database, engines: None
) -> None:
    tenant = await _firm(db)
    conn = await asyncpg.connect(_app(db))
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetch("SELECT * FROM integration_catalog")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetch("SELECT * FROM integration_catalog_load('[]'::jsonb, 'probe-op')")
    finally:
        await conn.close()
    await ops.load(
        _ops(db), _document(_row("square", "square", category="sales")), OPERATOR, dry_run=False
    )
    rows = await catalog_rows(tenant)
    assert "square" in {r.key for r in rows}
    # AC-49 on the real rows: no adapter is registered in this process, so nothing is available.
    entries = listed(rows, "portal", "client_authorised")
    assert entries and all(e.listing != "available" for e in entries)


async def test_a_second_live_install_of_one_app_is_refused(db: sc.Database) -> None:
    await ops.load(_ops(db), _document(_firm_row("cch_bridge")), OPERATOR, dry_run=False)
    tenant = await _firm(db)
    await _install(db, tenant, "cch_bridge")
    with pytest.raises(asyncpg.UniqueViolationError):
        await _install(db, tenant, "cch_bridge")


async def test_ac13_3_a_secret_is_sealed_to_the_tenant_and_its_owner_and_erase_destroys_it(
    db: sc.Database, engines: None
) -> None:
    await ops.load(_ops(db), _document(_firm_row("cch_file")), OPERATOR, dry_run=False)
    tenant = await _firm(db)
    other = await _firm(db)
    owner = await _install(db, tenant, "cch_file")
    second = await _install(db, other, "cch_file")
    plaintext = b"synthetic-token-not-a-secret"
    async with uow(tenant) as tx:
        await store_secret(tx, tenant.tenant_id, owner, plaintext)
    assert await open_secret(tenant, owner) == plaintext

    conn = await asyncpg.connect(db.superuser_dsn)
    try:
        sealed = cast(
            bytes,
            await conn.fetchval(
                "SELECT sealed FROM integration_secrets WHERE firm_integration_id = $1", owner
            ),
        )
        events = await conn.fetchval(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'integration_secret.stored' AND target_id = $2",
            tenant.tenant_id,
            str(owner),
        )
    finally:
        await conn.close()
    assert plaintext not in sealed
    assert events == 1
    # Bound to the owner row: under another install's id it does not open, nor in another firm.
    with pytest.raises(DecryptionError):
        await open_sealed(tenant.tenant_id, sealed, binding(second))
    with pytest.raises(DecryptionError):
        await open_sealed(other.tenant_id, sealed, binding(owner))
    # The app may not update a secret; erasing deletes the only copy.
    app = await asyncpg.connect(_app(db))
    try:
        async with app.transaction():
            await app.execute(
                "SELECT set_config('app.tenant_id', $1, true)", str(tenant.tenant_id)
            )
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.execute(
                    "UPDATE integration_secrets SET sealed = '\\x00' "
                    "WHERE firm_integration_id = $1",
                    owner,
                )
    finally:
        await app.close()
    async with uow(tenant) as tx:
        assert await erase_secret(tx, owner) is True
    assert await open_secret(tenant, owner) is None
    # Another firm never sees the row at all (forced row-level security).
    assert await open_secret(other, owner) is None


async def test_the_load_command_refuses_an_email_as_operator(db: sc.Database) -> None:
    with pytest.raises(ops.Refused):
        await ops.load(_ops(db), _document(), "builder@example.test", dry_run=True)
