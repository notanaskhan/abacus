"""W-01-T08 rest (TASK-8112; DEC-5083; SPEC-659 AC-25, OQ-5) against Postgres with the Connect
fakes on a synthetic firm.

Disabling a client-authorised firm app suspends every live client connection of its provider in
the firm (status `needs_attention`, reason `firm_app_disabled`, the secret retired to the
revocation queue, one `connection.suspended` audit row each) and reports the count; another
provider's connection is untouched; the health pass leaves a suspended connection alone; and with
`integrations.connect_v1` on a POR-16 start of that provider is refused while the app is off (a
portal-only feed never is).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast

import pytest

from abacus.kernel import config
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.connections.health import check_connection
from abacus.modules.connections.models import Connection
from abacus.modules.identity.api import AuthContext
from abacus.modules.integrations import connect_service as svc
from abacus.modules.integrations.api import CatalogDocumentV2
from abacus.modules.integrations.catalog import client_catalog
from abacus.modules.integrations.client_connect import firm_app_off
from abacus_tools import integration_catalog as ops

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.usefixtures("fakes_on")

PROVIDER = "probe_ledger"
CONSENT = {
    "title": "Connect Probe Ledger",
    "will": ["Read your books"],
    "wont": ["Change anything"],
    "authorization": "I'm authorized to connect this company.",
    "continue_label": "Continue",
}


def _row(key: str, surfaces: list[str], provider: str, category: str) -> dict[str, object]:
    return {
        "key": key,
        "category": category,
        "name": key.title(),
        "categories": ["erp"],
        "ownership_mode": "client_authorised",
        "surfaces": surfaces,
        "adapter_key": key,
        "connector_provider": provider,
        "listing_status": "available",
        "scopes": {"read": [{"code": "ledger.read", "label": "Ledger"}]},
        "consent_copy": CONSENT,
        "consent_version": 1,
        "icon": "store",
        "tone": "clay",
        "sort_order": 30,
        "description": "A probe ledger.",
        "auth_line": "Firm app · client-authorized",
        "published_at": "2026-01-01T00:00:00-06:00",
    }


DOC = CatalogDocumentV2.model_validate(
    {
        "version": 2,
        "rows": [
            _row("probeapp", ["workbench", "portal"], PROVIDER, "ledger"),
            _row("probefeed", ["portal"], "probe_feed", "bank_feed"),
        ],
    }
)


@pytest.fixture
def fakes_on(monkeypatch: pytest.MonkeyPatch) -> object:
    monkeypatch.setenv("ABACUS_INTEGRATIONS_FAKE_ADAPTERS", "true")
    config.settings.cache_clear()
    yield None
    config.settings.cache_clear()


@pytest.fixture
async def db(migrated_db: MigratedDatabase) -> AsyncIterator[MigratedDatabase]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    await ops.import_v2(
        migrated_db.app_url.replace("abacus_app:abacusapp", "abacus_ops:abacusops", 1),
        DOC,
        "c" * 64,
        "probe-op",
        "W-01-T08 firm-app suspend probe",
        environment="test",
        dry_run=False,
    )
    yield migrated_db
    await dispose_engine()


async def _admin(seed: Seeder, tenant_id: uuid.UUID) -> AuthContext:
    subject = f"sub-{uuid.uuid4().hex}"
    user_id = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ('https://identity.abacus.local', $1, $2, 'Probe person') RETURNING id",
            subject,
            f"{subject}@example.test",
        ),
    )
    membership = await seed.value(
        "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
        "VALUES ($1, $2, 'security_admin', 'active') RETURNING id",
        tenant_id,
        user_id,
    )
    tenant = TenantContext(tenant_id, "human", str(user_id))
    return AuthContext(
        tenant, user_id, cast(uuid.UUID, membership), "security_admin", datetime.now(UTC)
    )


async def _connection(
    seed: Seeder,
    tenant_id: uuid.UUID,
    entity: uuid.UUID,
    provider: str,
    category: str,
    *,
    status: str = "active",
    reason: str | None = None,
) -> uuid.UUID:
    connection = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO connections (tenant_id, client_entity_id, provider, created_by, "
            "category, status, status_reason_code) VALUES ($1, $2, $3, 'seed', $4, $5, $6) "
            "RETURNING id",
            tenant_id,
            entity,
            provider,
            category,
            status,
            reason,
        ),
    )
    await seed.run(
        "INSERT INTO connection_secrets (connection_id, tenant_id, sealed) VALUES ($1, $2, $3)",
        connection,
        tenant_id,
        b"sealed-probe",
    )
    return connection


async def _world(db: MigratedDatabase) -> tuple[Seeder, AuthContext, list[uuid.UUID]]:
    seed = Seeder(db.superuser_dsn)
    tenant_id = uuid.uuid4()
    await seed.run(
        "INSERT INTO firms (tenant_id, name, synthetic) VALUES ($1, 'Probe', true)", tenant_id
    )
    felix = await _admin(seed, tenant_id)
    client = await seed.value(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Probe Client') RETURNING id",
        tenant_id,
    )
    entities = [
        cast(
            uuid.UUID,
            await seed.value(
                "INSERT INTO client_entities (tenant_id, client_id, name) "
                "VALUES ($1, $2, $3) RETURNING id",
                tenant_id,
                client,
                f"Probe Entity {n}",
            ),
        )
        for n in (1, 2)
    ]
    return seed, felix, entities


async def _version(seed: Seeder, tenant_id: uuid.UUID) -> int:
    return cast(
        int,
        await seed.value(
            "SELECT version FROM firm_integrations "
            "WHERE tenant_id = $1 AND catalog_key = 'probeapp'",
            tenant_id,
        ),
    )


async def test_ac25_the_disable_suspends_the_providers_client_connections(
    db: MigratedDatabase,
) -> None:
    seed, felix, (e1, e2) = await _world(db)
    tenant_id = felix.tenant_id
    started = await svc.start_firm(felix, "probeapp")
    assert (started.status, started.authorise_url) == ("connected", None)
    a = await _connection(seed, tenant_id, e1, PROVIDER, "ledger")
    b = await _connection(
        seed, tenant_id, e2, PROVIDER, "ledger", status="needs_attention", reason="sync_failed"
    )
    other = await _connection(seed, tenant_id, e1, "fake", "bank_feed")

    done = await svc.disconnect_firm(
        felix, "probeapp", "Probeapp", await _version(seed, tenant_id)
    )

    assert done.suspended_client_connections == 2
    rows = await seed.rows(
        "SELECT id, status, status_reason_code FROM connections WHERE tenant_id = $1", tenant_id
    )
    by_id = {r["id"]: (r["status"], r["status_reason_code"]) for r in rows}
    assert by_id[a] == by_id[b] == ("needs_attention", "firm_app_disabled")
    assert by_id[other] == ("active", None)
    secrets = await seed.rows(
        "SELECT connection_id FROM connection_secrets WHERE tenant_id = $1", tenant_id
    )
    assert [r["connection_id"] for r in secrets] == [other]
    retired = await seed.rows(
        "SELECT connection_id, reason FROM connection_grant_revocations WHERE tenant_id = $1",
        tenant_id,
    )
    assert sorted((r["connection_id"], r["reason"]) for r in retired) == sorted(
        [(a, "firm_app_disabled"), (b, "firm_app_disabled")]
    )
    assert (
        await seed.value(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'connection.suspended'",
            tenant_id,
        )
        == 2
    )


async def test_ac25_the_health_pass_leaves_a_suspended_connection_alone(
    db: MigratedDatabase,
) -> None:
    seed, felix, (e1, _) = await _world(db)
    suspended = await _connection(
        seed,
        felix.tenant_id,
        e1,
        PROVIDER,
        "ledger",
        status="needs_attention",
        reason="firm_app_disabled",
    )
    row = Connection(
        id=suspended,
        tenant_id=felix.tenant_id,
        client_entity_id=e1,
        provider=PROVIDER,
        status="needs_attention",
        status_reason_code="firm_app_disabled",
    )
    tenant = TenantContext(felix.tenant_id, "system", "probe:health")
    assert await check_connection(tenant, row) == "skipped"
    assert (
        await seed.value("SELECT status_reason_code FROM connections WHERE id = $1", suspended)
        == "firm_app_disabled"
    )


async def test_ac25_a_portal_start_waits_for_the_firm_app_with_connect_v1_on(
    db: MigratedDatabase,
) -> None:
    seed, felix, _ = await _world(db)
    rows = {e.row.key: e.row for e in await client_catalog(felix.tenant)}
    app, feed = rows["probeapp"], rows["probefeed"]
    # Flag off: the firm app is not consulted (POR-16 as before W-01).
    assert not await firm_app_off(felix, app)
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'integrations.connect_v1', 'true', 'test-seed', 'W-01-T08 probe')",
        felix.tenant_id,
    )
    forget_flags()  # the flag read above is cached for 30 seconds
    assert await firm_app_off(felix, app)  # never enabled
    assert not await firm_app_off(felix, feed)  # a portal-only feed has no firm app
    await svc.start_firm(felix, "probeapp")
    assert not await firm_app_off(felix, app)
    await svc.disconnect_firm(felix, "probeapp", "Probeapp", await _version(seed, felix.tenant_id))
    assert await firm_app_off(felix, app)
