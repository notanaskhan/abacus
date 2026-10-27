"""N-01-T06 (TASK-1605; ADR-158): migration 0270, client-scoped evidence and same-client
fulfilment.

"Upgrade and downgrade pass on the synthetic seed and a fulfilment across two clients is refused
by the trigger" (N-01-T06 acceptance; SPEC-380 AC-20, AC-21): items made before 0270 read their
engagement's client and scope `engagement`; an insert that leaves the new columns out is filled
from the engagement; a client-scoped item needs no engagement; a fulfilment from another client's
evidence is refused, from another engagement of the same client allowed; down and up again
leaves a schema that passes the schema check.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

BEFORE = "0244"  # the revision before 0270 (re-pointed with the chain at the batch merge)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _revision(database: sc.Database) -> str:
    seed = Seeder(database.superuser_dsn)
    return str(asyncio.run(seed.value("SELECT version_num FROM alembic_version")))


_INSERT_VERSION = (
    "INSERT INTO evidence_versions (id, tenant_id, engagement_id, evidence_item_id, version_no, "
    "fingerprint, storage_key, storage_version_id, size_bytes, media_type, source, method, "
    "supersedes_version_id) VALUES ($1, $2, $3, $4, $5, $6, $7, 'v1', 10, 'application/pdf', "
    "'portal_drop', 'uploaded', $8)"
)
# Before migration 0270 the column does not exist yet.
_INSERT_LEGACY_VERSION = (
    "INSERT INTO evidence_versions (id, tenant_id, engagement_id, evidence_item_id, version_no, "
    "fingerprint, storage_key, storage_version_id, size_bytes, media_type, source, method) "
    "VALUES ($1, $2, $3, $4, $5, $6, $7, 'v1', 10, 'application/pdf', 'portal_drop', 'uploaded')"
)


async def _version(
    seed: Seeder,
    tenant: uuid.UUID,
    engagement: uuid.UUID | None,
    item: uuid.UUID,
    number: int = 1,
    supersedes_version_id: uuid.UUID | None = None,
    *,
    legacy: bool = False,
) -> uuid.UUID:
    fingerprint = uuid.uuid4().hex * 2
    version = uuid.uuid4()
    values = (version, tenant, engagement, item, number, fingerprint)
    key = f"tenants/{tenant}/sha256/{fingerprint}"
    if legacy:
        await seed.run(_INSERT_LEGACY_VERSION, *values, key)
    else:
        await seed.run(_INSERT_VERSION, *values, key, supersedes_version_id)
    return version


async def _item(
    seed: Seeder, tenant: uuid.UUID, engagement: uuid.UUID | None, client: uuid.UUID | None = None
) -> uuid.UUID:
    return uuid.UUID(
        str(
            await seed.value(
                "INSERT INTO evidence_items (tenant_id, engagement_id, client_id, title, "
                "created_by_kind, created_by_id) "
                "VALUES ($1, $2, $3, 'Form 1099-DIV', 'human', 'seed') "
                "RETURNING id",
                tenant,
                engagement,
                client,
            )
        )
    )


async def _fulfil(
    seed: Seeder, tenant: uuid.UUID, engagement: uuid.UUID, request: uuid.UUID, version: uuid.UUID
) -> None:
    await seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id) "
        "VALUES ($1, $2, $3, $4, 'human', 'seed')",
        tenant,
        engagement,
        request,
        version,
    )


def test_ac20_ac21_scope_backfill_fill_trigger_and_same_client_fulfilment(
    private_db: sc.Database,
) -> None:
    seed = Seeder(private_db.superuser_dsn)
    head = _revision(private_db)
    migrate(private_db.owner_url, BEFORE, down=True)

    async def before() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
        tenant = await seed.firm()
        person = await seed.person(tenant)
        entity = await seed.entity(tenant)
        engagement = await seed.engagement(tenant, entity, person.user_id)
        item = await seed.value(
            "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
            "created_by_id) VALUES ($1, $2, 'Census', 'human', 'seed') RETURNING id",
            tenant,
            engagement,
        )
        await _version(seed, tenant, engagement, uuid.UUID(str(item)), legacy=True)
        return tenant, person.user_id, entity, engagement

    tenant, user, entity, engagement = asyncio.run(before())
    migrate(private_db.owner_url, "head")

    async def after() -> None:
        legacy = await seed.rows(
            "SELECT i.client_id, i.scope, i.folder_kind, v.channel FROM evidence_items i "
            "JOIN evidence_versions v ON v.evidence_item_id = i.id WHERE i.tenant_id = $1",
            tenant,
        )
        client = await seed.value("SELECT client_id FROM engagements WHERE id = $1", engagement)
        assert [tuple(r) for r in legacy] == [(client, "engagement", "source_documents", "portal")]

        # An insert that leaves the new columns out is filled from the engagement.
        filled = await _item(seed, tenant, engagement)
        row = await seed.rows("SELECT client_id, scope FROM evidence_items WHERE id = $1", filled)
        assert tuple(row[0]) == (client, "engagement")

        # A client-scoped item: no engagement, its client named.
        permanent = await _item(seed, tenant, None, uuid.UUID(str(client)))
        assert await seed.value("SELECT scope FROM evidence_items WHERE id = $1", permanent) == (
            "client"
        )
        permanent_version = await _version(seed, tenant, None, permanent)

        # The same client's other engagement may fulfil from it; another client's may not.
        second = await seed.engagement(tenant, entity, user)
        request = await seed.item(tenant, second, user)
        await _fulfil(seed, tenant, second, request, permanent_version)

        other_entity = await seed.entity(tenant, "Other client")
        other = await seed.engagement(tenant, other_entity, user)
        other_request = await seed.item(tenant, other, user)
        with pytest.raises(asyncpg.CheckViolationError):
            await _fulfil(seed, tenant, other, other_request, permanent_version)

        # An engagement-scoped item can't claim another client.
        other_client = await seed.value(
            "SELECT client_id FROM client_entities WHERE id = $1", other_entity
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await _item(seed, tenant, engagement, uuid.UUID(str(other_client)))

        # A version supersedes only an earlier version of its own item.
        first = await _version(seed, tenant, engagement, filled, 1)
        await _version(seed, tenant, engagement, filled, 2, supersedes_version_id=first)
        with pytest.raises(asyncpg.CheckViolationError):
            await _version(
                seed, tenant, engagement, filled, 3, supersedes_version_id=permanent_version
            )

    asyncio.run(after())

    # Down refuses while client-scoped evidence exists.
    with pytest.raises(Exception, match="cannot be undone"):
        migrate(private_db.owner_url, BEFORE, down=True)
    # Later migrations may go down first; 0270 itself stays applied.
    assert _revision(private_db) >= "0270" and head >= "0270"


def test_0270_goes_down_and_up_on_a_firm_without_client_scoped_evidence() -> None:
    with provisioned_database(roundtrip=False) as database:
        migrate(database.owner_url, BEFORE, down=True)
        migrate(database.owner_url, "head")
        migrate(database.owner_url, BEFORE, down=True)
        migrate(database.owner_url, "head")
        assert sc.check(database.owner_url, database.app_url) == []
