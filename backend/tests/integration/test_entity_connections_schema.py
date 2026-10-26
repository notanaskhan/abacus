"""A-02-T13 (TASK-1340; SPEC-333 AC-35 to AC-48; A-02 §4.2) against Postgres: migration 0195.

The row's acceptance: existing connections and sync runs survive up/down/up unchanged, a second
live QuickBooks connection for one entity is refused, and a bank feed beside the ledger is
allowed. Also from §4.2: a run names a request item exactly when a request item asked for it,
consents are never updated or deleted, and a connection has one open reconnect request. Rows are
seeded as the superuser; the app's statements run as `abacus_app` with the tenant set.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import asyncpg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

REVISION = "0195"
_SCRIPTS = ScriptDirectory.from_config(
    Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
)
BEFORE = cast(str, _SCRIPTS.get_revision(REVISION).down_revision)


@dataclass(frozen=True)
class Firm:
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    entity_id: uuid.UUID
    engagement_id: uuid.UUID
    item_id: uuid.UUID


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _app(db: sc.Database) -> str:
    return db.app_url.replace("postgresql+asyncpg://", "postgresql://")


async def _sql(db: sc.Database, statement: str, *args: object) -> object:
    conn = await asyncpg.connect(db.superuser_dsn)
    try:
        return await conn.fetchval(statement, *args)
    finally:
        await conn.close()


async def _as_app(db: sc.Database, firm: Firm, statement: str, *args: object) -> object:
    conn = await asyncpg.connect(_app(db))
    try:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.tenant_id', $1, true)", str(firm.tenant_id))
            return await conn.fetchval(statement, *args)
    finally:
        await conn.close()


async def _firm(db: sc.Database) -> Firm:
    tenant_id = uuid.uuid4()
    await _sql(db, "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Conns')", tenant_id)
    subject = f"sub-{uuid.uuid4().hex}"
    user_id = cast(
        uuid.UUID,
        await _sql(
            db,
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ('https://identity.abacus.local', $1, $2, 'Test person') RETURNING id",
            subject,
            f"{subject}@example.test",
        ),
    )
    await _sql(
        db,
        "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
        "VALUES ($1, $2, NULL, 'active')",
        tenant_id,
        user_id,
    )
    client_id = await _sql(
        db, "INSERT INTO clients (tenant_id, name) VALUES ($1, 'C') RETURNING id", tenant_id
    )
    entity_id = cast(
        uuid.UUID,
        await _sql(
            db,
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, 'E') "
            "RETURNING id",
            tenant_id,
            client_id,
        ),
    )
    engagement_id = cast(
        uuid.UUID,
        await _sql(
            db,
            "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
            "fiscal_period_start, fiscal_period_end, created_by) "
            "VALUES ($1, $2, $3, 'Audit', '2026-01-01', '2026-12-31', $4) RETURNING id",
            tenant_id,
            client_id,
            entity_id,
            user_id,
        ),
    )
    list_id = await _sql(
        db,
        "INSERT INTO request_lists (tenant_id, engagement_id) VALUES ($1, $2) RETURNING id",
        tenant_id,
        engagement_id,
    )
    item_id = cast(
        uuid.UUID,
        await _sql(
            db,
            "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, description, "
            "audit_area, created_by) VALUES ($1, $2, $3, 'Trial balance', 'General', $4) "
            "RETURNING id",
            tenant_id,
            engagement_id,
            list_id,
            user_id,
        ),
    )
    return Firm(tenant_id, user_id, entity_id, engagement_id, item_id)


_CONNECT = (
    "INSERT INTO connections (tenant_id, client_entity_id, provider, created_by) "
    "VALUES ($1, $2, $3, 'seed') RETURNING id"
)
_CONNECT_V2 = (
    "INSERT INTO connections (tenant_id, client_entity_id, provider, created_by, category, "
    "external_account_ref, display_label) VALUES ($1, $2, $3, 'seed', $4, $5, $6) RETURNING id"
)


async def _run(db: sc.Database, firm: Firm, connection: uuid.UUID) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await _sql(
            db,
            "INSERT INTO sync_runs (tenant_id, client_entity_id, connection_id, engagement_id, "
            "request_item_id, dataset, period_start, period_end, started_by) "
            "VALUES ($1, $2, $3, $4, $5, 'trial_balance', '2026-01-01', '2026-12-31', 'seed') "
            "RETURNING id",
            firm.tenant_id,
            firm.entity_id,
            connection,
            firm.engagement_id,
            firm.item_id,
        ),
    )


_ROW_JSON = {
    "connections": "SELECT to_jsonb(t)::text FROM connections t WHERE id = $1",
    "sync_runs": "SELECT to_jsonb(t)::text FROM sync_runs t WHERE id = $1",
}


async def _json(db: sc.Database, table: str, row_id: uuid.UUID) -> dict[str, object]:
    raw = await _sql(db, _ROW_JSON[table], row_id)
    return cast(dict[str, object], json.loads(cast(str, raw)))


def test_existing_connections_and_sync_runs_survive_up_down_up(db: sc.Database) -> None:
    migrate(db.owner_url, BEFORE, down=True)
    firm = asyncio.run(_firm(db))
    connection = cast(
        uuid.UUID, asyncio.run(_sql(db, _CONNECT, firm.tenant_id, firm.entity_id, "fake"))
    )
    run = asyncio.run(_run(db, firm, connection))
    before = (
        asyncio.run(_json(db, "connections", connection)),
        asyncio.run(_json(db, "sync_runs", run)),
    )
    migrate(db.owner_url, "head")
    after_c = asyncio.run(_json(db, "connections", connection))
    after_r = asyncio.run(_json(db, "sync_runs", run))
    assert {k: after_c[k] for k in before[0]} == before[0]
    assert {k: after_r[k] for k in before[1]} == before[1]
    assert (after_c["category"], after_r["trigger"]) == ("ledger", "request_item")
    migrate(db.owner_url, BEFORE, down=True)
    assert asyncio.run(_json(db, "connections", connection)) == before[0]
    assert asyncio.run(_json(db, "sync_runs", run)) == before[1]
    migrate(db.owner_url, "head")
    assert asyncio.run(_json(db, "connections", connection)) == after_c
    assert asyncio.run(_json(db, "sync_runs", run)) == after_r
    assert sc.check(db.owner_url, db.app_url) == []


def test_a_second_live_quickbooks_connection_for_one_entity_is_refused(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    args = (firm.tenant_id, firm.entity_id, "quickbooks_online", "ledger")
    first = asyncio.run(_as_app(db, firm, _CONNECT_V2, *args, "9130-001", "Copperleaf books"))
    assert first is not None
    # The same company again, and another company: one live ledger per entity (ADR-045).
    for account in ("9130-001", "9130-002"):
        with pytest.raises(asyncpg.UniqueViolationError):
            asyncio.run(_as_app(db, firm, _CONNECT_V2, *args, account, "Copperleaf books"))
    # Once the first is revoked, the entity may connect its ledger again.
    asyncio.run(
        _as_app(
            db,
            firm,
            "UPDATE connections SET status = 'revoked', revoked_at = clock_timestamp(), "
            "revoked_by = 'seed' WHERE id = $1 RETURNING id",
            first,
        )
    )
    again = asyncio.run(_as_app(db, firm, _CONNECT_V2, *args, "9130-001", "Copperleaf books"))
    assert again is not None


def test_a_bank_feed_beside_the_ledger_is_allowed(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    asyncio.run(
        _as_app(
            db, firm, _CONNECT_V2, firm.tenant_id, firm.entity_id, "quickbooks_online",
            "ledger", "9130-001", "Copperleaf books",
        )
    )  # fmt: skip
    feed = asyncio.run(
        _as_app(
            db, firm, _CONNECT_V2, firm.tenant_id, firm.entity_id, "front_range_bank",
            "bank_feed", "acct-4410", "Front Range Bank ••4410",
        )
    )  # fmt: skip
    assert feed is not None
    # A second account at the same bank is another feed; the same account twice is not.
    second = asyncio.run(
        _as_app(
            db, firm, _CONNECT_V2, firm.tenant_id, firm.entity_id, "front_range_bank",
            "bank_feed", "acct-5520", "Front Range Bank ••5520",
        )
    )  # fmt: skip
    assert second is not None
    with pytest.raises(asyncpg.UniqueViolationError):
        asyncio.run(
            _as_app(
                db, firm, _CONNECT_V2, firm.tenant_id, firm.entity_id, "front_range_bank",
                "bank_feed", "acct-4410", "Front Range Bank ••4410",
            )
        )  # fmt: skip


def test_a_provider_outside_the_key_grammar_is_refused(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_as_app(db, firm, _CONNECT, firm.tenant_id, firm.entity_id, "QuickBooks"))


_RUN = (
    "INSERT INTO sync_runs (tenant_id, client_entity_id, connection_id, engagement_id, "
    "request_item_id, dataset, period_start, period_end, started_by, trigger, label) "
    "VALUES ($1, $2, $3, $4, $5, $6, '2026-01-01', '2026-12-31', 'seed', $7, $8) RETURNING id"
)


def test_a_run_names_a_request_item_exactly_when_one_asked(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    connection = asyncio.run(
        _as_app(db, firm, _CONNECT, firm.tenant_id, firm.entity_id, "quickbooks_online")
    )
    base = (firm.tenant_id, firm.entity_id, connection, firm.engagement_id)
    on_demand = asyncio.run(
        _as_app(db, firm, _RUN, *base, None, "prior_trial_balance", "on_demand", "prior")
    )
    assert on_demand is not None
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_as_app(db, firm, _RUN, *base, None, "trial_balance", "request_item", None))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _as_app(db, firm, _RUN, *base, firm.item_id, "trial_balance", "on_demand", None)
        )


_CONSENT = (
    "INSERT INTO connection_consents (tenant_id, client_entity_id, catalog_key, consent_version, "
    "will, wont, authorization_text, authorised_by_user_id, ip_sha256) "
    "VALUES ($1, $2, 'american_express', 1, ARRAY['Read your card transactions'], "
    "ARRAY['Move money'], 'I am authorized to connect this account.', $3, $4) RETURNING id"
)


def test_a_consent_is_written_once_and_never_changed(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    ip = hashlib.sha256(b"192.0.2.10").hexdigest()
    consent = asyncio.run(
        _as_app(db, firm, _CONSENT, firm.tenant_id, firm.entity_id, firm.user_id, ip)
    )
    connection = asyncio.run(
        _as_app(db, firm, _CONNECT, firm.tenant_id, firm.entity_id, "american_express")
    )
    link = "INSERT INTO connection_consent_links (consent_id, tenant_id, connection_id) "
    link += "VALUES ($1, $2, $3) RETURNING consent_id"
    assert asyncio.run(_as_app(db, firm, link, consent, firm.tenant_id, connection)) == consent
    with pytest.raises(asyncpg.UniqueViolationError):  # one link per consent
        asyncio.run(_as_app(db, firm, link, consent, firm.tenant_id, connection))
    for statement in (
        "UPDATE connection_consents SET consent_version = 2 WHERE id = $1",
        "DELETE FROM connection_consents WHERE id = $1",
    ):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            asyncio.run(_as_app(db, firm, statement, consent))
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            asyncio.run(_sql(db, statement, consent))  # the trigger refuses every role


def test_a_connection_has_one_open_reconnect_request(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    connection = asyncio.run(
        _as_app(db, firm, _CONNECT, firm.tenant_id, firm.entity_id, "american_express")
    )
    ask = (
        "INSERT INTO reconnect_requests (tenant_id, connection_id, requested_by_user_id, "
        "engagement_id) VALUES ($1, $2, $3, $4) RETURNING id"
    )
    args = (firm.tenant_id, connection, firm.user_id, firm.engagement_id)
    first = asyncio.run(_as_app(db, firm, ask, *args))
    with pytest.raises(asyncpg.UniqueViolationError):
        asyncio.run(_as_app(db, firm, ask, *args))
    asyncio.run(
        _as_app(
            db,
            firm,
            "UPDATE reconnect_requests SET fulfilled_at = abacus_now() WHERE id = $1 RETURNING id",
            first,
        )
    )
    assert asyncio.run(_as_app(db, firm, ask, *args)) is not None
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(
            _as_app(db, firm, "UPDATE reconnect_requests SET connection_id = $1", connection)
        )
