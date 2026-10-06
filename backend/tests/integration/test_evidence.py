"""AC-12 / AC-13: evidence items and versions in the database and through `evidence.api`
(TASK-009 interface contract, "Database (migration 0007)" and "Service"; ADR-004, ADR-016).

Rows are seeded as the superuser (`migrated_db.superuser_dsn`) with fresh firms per test, so tests
never need cleanup. Statements that must fail for `abacus_app` run through `tenant_session`.
Objects go to a bucket of this module on the Versity gateway. Expectations come from the contract,
not from the implementation.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Literal, Protocol, cast

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from types_boto3_s3 import S3Client

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import (
    TenantContext,
    configure_engine,
    dispose_engine,
    tenant_session,
    transaction_context,
)
from abacus.kernel.errors import NotFound
from abacus.kernel.storage import s3_client
from abacus.kernel.uow import Target, uow
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import (
    XLSX_MEDIA_TYPE,
    EngagementArchived,
    EvidenceVersionRef,
    IntegrityError,
    NewItem,
    Provenance,
    StoredObject,
    TrialBalance,
    TrialBalanceLine,
    add_version,
    read_content,
    read_version,
    render_trial_balance,
    stage_content,
)
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus_tools.quality import schema_check as sc

MASTER = b"evidence-test-master-key-0123456789abcdef"
BUCKET = f"evidence-service-{uuid.uuid4().hex[:12]}"
PULLED_AT = datetime(2026, 3, 14, 9, 26, 53, tzinfo=UTC)
SYSTEM = "system"
ACTOR = "retrieval"
DEFAULT_ITEM = NewItem("Trial balance")
INSERT_VERSION = (
    "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, version_no, "
    "fingerprint, storage_key, storage_version_id, size_bytes, media_type, source, method) "
    "VALUES (:tenant, :engagement, :item, 1, :fingerprint, :key, 'v1', 1, 'text/plain', 's', "
    "'uploaded')"
)
INSERT_VERSION_WITH_CREATED_AT = (
    "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, version_no, "
    "fingerprint, storage_key, storage_version_id, size_bytes, media_type, source, method, "
    "created_at) VALUES (:tenant, :engagement, :item, 1, :fingerprint, :key, 'v1', 1, "
    "'text/plain', 's', 'uploaded', now())"
)
FirmRole = Literal["firm_admin", "practice_leader", "quality_partner"]
ENGAGEMENT_ROLES = ["engagement_partner", "manager", "senior", "staff", "reviewer"]


class Migrated(Protocol):
    owner_url: str
    app_url: str
    identity_url: str
    superuser_dsn: str


# --- seeding (superuser) -------------------------------------------------------------------------


class Seeder:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def run(self, sql: str, *args: object) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(sql, *args)
        finally:
            await conn.close()

    async def value(self, sql: str, *args: object) -> object:
        conn = await asyncpg.connect(self._dsn)
        try:
            return await conn.fetchval(sql, *args)
        finally:
            await conn.close()

    async def rows(self, sql: str, *args: object) -> list[asyncpg.Record]:
        conn = await asyncpg.connect(self._dsn)
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

    async def engagement(self, tenant_id: uuid.UUID) -> uuid.UUID:
        created_by = (await self.person(tenant_id, None)).user_id
        client_id = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Seeded client') RETURNING id",
                tenant_id,
            ),
        )
        entity_id = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO client_entities (tenant_id, client_id, name) "
                "VALUES ($1, $2, 'Seeded entity') RETURNING id",
                tenant_id,
                client_id,
            ),
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
                created_by,
            ),
        )

    async def entity_of(self, engagement_id: uuid.UUID) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.value(
                "SELECT client_entity_id FROM engagements WHERE id = $1", engagement_id
            ),
        )

    async def person(self, tenant_id: uuid.UUID, firm_role: FirmRole | None) -> Person:
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
            "VALUES ($1, $2, $3, 'active')",
            tenant_id,
            user_id,
            firm_role,
        )
        return Person(user_id, tenant_id, firm_role)

    async def member(self, engagement_id: uuid.UUID, who: Person, role: str) -> None:
        await self.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            who.tenant_id,
            engagement_id,
            who.user_id,
            role,
        )

    async def item(self, tenant_id: uuid.UUID, engagement_id: uuid.UUID) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
                "created_by_id) VALUES ($1, $2, 'Seeded item', 'system', 'seed') RETURNING id",
                tenant_id,
                engagement_id,
            ),
        )

    async def version(
        self,
        tenant_id: uuid.UUID,
        engagement_id: uuid.UUID,
        item_id: uuid.UUID,
        **overrides: object,
    ) -> uuid.UUID:
        fingerprint = str(
            overrides.pop("fingerprint", hashlib.sha256(uuid.uuid4().bytes).hexdigest())
        )
        values: dict[str, object] = {
            "tenant_id": tenant_id,
            "engagement_id": engagement_id,
            "evidence_item_id": item_id,
            "version_no": 1,
            "fingerprint": fingerprint,
            "storage_key": f"tenants/{tenant_id}/sha256/{fingerprint}",
            "storage_version_id": "v1",
            "size_bytes": 10,
            "media_type": "application/pdf",
            "source": "upload",
            "method": "uploaded",
            "pulled_at": None,
            "period_start": None,
            "period_end": None,
            "client_entity_id": None,
            "snapshot_id": None,
            "idempotency_key": None,
        }
        values.update(overrides)
        return cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
                "version_no, fingerprint, storage_key, storage_version_id, size_bytes, "
                "media_type, source, method, pulled_at, period_start, period_end, "
                "client_entity_id, snapshot_id, idempotency_key) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, "
                "$17) RETURNING id",
                *values.values(),
            ),
        )

    async def count(self, table: str, tenant_id: uuid.UUID) -> int:
        queries = {
            "evidence_items": "SELECT count(*) FROM evidence_items WHERE tenant_id = $1",
            "evidence_versions": "SELECT count(*) FROM evidence_versions WHERE tenant_id = $1",
            "audit_events": "SELECT count(*) FROM audit_events WHERE tenant_id = $1",
            "outbox": "SELECT count(*) FROM outbox WHERE tenant_id = $1",
        }
        return cast(int, await self.value(queries[table], tenant_id))


@dataclass(frozen=True)
class Person:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    firm_role: FirmRole | None

    def context(self) -> AuthContext:
        return AuthContext(
            tenant=TenantContext(self.tenant_id, "human", str(self.user_id)),
            user_id=self.user_id,
            membership_id=uuid.uuid4(),
            firm_role=self.firm_role,
            mfa_at=datetime.now(UTC) - timedelta(minutes=1),
        )


@dataclass(frozen=True)
class World:
    tenant_id: uuid.UUID
    engagement_id: uuid.UUID
    entity_id: uuid.UUID

    @property
    def system(self) -> TenantContext:
        return TenantContext(self.tenant_id, SYSTEM, ACTOR)


@pytest.fixture
def seed(migrated_db: Migrated) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture
async def world(seed: Seeder) -> World:
    tenant_id = await seed.firm()
    engagement_id = await seed.engagement(tenant_id)
    return World(tenant_id, engagement_id, await seed.entity_of(engagement_id))


@pytest.fixture(autouse=True)
async def engines(migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Each test has its own event loop: rebuild the engines for it, from the test database."""
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture(scope="module")
def bucket_client(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True)
    yield client
    listing = client.list_object_versions(Bucket=BUCKET)
    for entry in [*listing.get("Versions", []), *listing.get("DeleteMarkers", [])]:
        client.delete_object(
            Bucket=BUCKET,
            Key=entry.get("Key", ""),
            VersionId=entry.get("VersionId", ""),
            BypassGovernanceRetention=True,
        )
    client.delete_bucket(Bucket=BUCKET)


@pytest.fixture(autouse=True)
def evidence_storage(bucket_client: S3Client) -> Iterator[S3Client]:
    """Storage and the key service for each test; both are reset in teardown."""
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(bucket_client, BUCKET)
    yield bucket_client
    storage.reset_storage()
    reset_key_service()


def _content(label: str = "evidence") -> bytes:
    return f"{label} {uuid.uuid4()} confidential figures".encode()


def _uploaded() -> Provenance:
    return Provenance(source="upload", method="uploaded")


async def _add(
    world: World,
    *,
    item: uuid.UUID | NewItem = DEFAULT_ITEM,
    content: bytes | None = None,
    media_type: str = "application/pdf",
    provenance: Provenance | None = None,
    ctx: TenantContext | None = None,
    idempotency_key: str | None = None,
    engagement_id: uuid.UUID | None = None,
) -> EvidenceVersionRef:
    tenant = ctx or world.system
    stored = await stage_content(tenant.tenant_id, content if content is not None else _content())
    async with uow(tenant) as tx:
        ref = await add_version(
            tx,
            engagement_id=engagement_id or world.engagement_id,
            item=item,
            stored=stored,
            media_type=media_type,
            provenance=provenance or _uploaded(),
            idempotency_key=idempotency_key,
        )
        if not ref.created:  # a repeat records nothing itself: the caller records its own event
            tx.record("evidence_version.noted", target=_target(ref.id))
        return ref


def _target(identifier: uuid.UUID) -> Target:
    return Target("evidence_version", identifier)


def _object_versions(client: S3Client, key: str) -> list[str]:
    listing = client.list_object_versions(Bucket=BUCKET, Prefix=key)
    return [v.get("VersionId", "") for v in listing.get("Versions", []) if v.get("Key") == key]


# --- database: tables, RLS, ownership ------------------------------------------------------------


@pytest.mark.parametrize("table", ["evidence_items", "evidence_versions"])
async def test_ac13_evidence_tables_are_tenant_tables_with_forced_rls(
    seed: Seeder, table: str
) -> None:
    rows = await seed.rows(
        "SELECT c.relrowsecurity, c.relforcerowsecurity FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relname = $1",
        table,
    )
    assert [(r["relrowsecurity"], r["relforcerowsecurity"]) for r in rows] == [(True, True)]
    column = await seed.value(
        "SELECT attnotnull FROM pg_attribute "
        "WHERE attrelid = $1::regclass AND attname = 'tenant_id'",
        table,
    )
    assert column is True


@pytest.mark.parametrize("table", ["evidence_items", "evidence_versions"])
def test_ac20_the_evidence_module_owns_the_evidence_tables(table: str) -> None:
    assert sc.TABLE_OWNERS[table] == "evidence"


def test_ac20_evidence_versions_is_declared_insert_only() -> None:
    assert "evidence_versions" in sc.INSERT_ONLY_TABLES
    assert "created_at" not in sc.APP_INSERT_COLUMNS["evidence_versions"]
    assert "created_at" not in sc.APP_INSERT_COLUMNS["evidence_items"]


async def test_ac13_rls_hides_another_firms_evidence_from_the_app(
    seed: Seeder, world: World
) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    version_id = await seed.version(world.tenant_id, world.engagement_id, item_id)
    other = await seed.firm()
    async with tenant_session(TenantContext(other, SYSTEM, ACTOR)) as session:
        items = (await session.execute(text("SELECT id FROM evidence_items"))).all()
        versions = (await session.execute(text("SELECT id FROM evidence_versions"))).all()
    assert [r.id for r in items if r.id == item_id] == []
    assert [r.id for r in versions if r.id == version_id] == []
    async with tenant_session(world.system) as session:
        mine = (await session.execute(text("SELECT id FROM evidence_versions"))).all()
    assert version_id in [r.id for r in mine]


# --- database: composite foreign keys ------------------------------------------------------------


async def test_ac13_a_version_must_match_its_items_engagement(seed: Seeder, world: World) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    other_engagement = await seed.engagement(world.tenant_id)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.version(world.tenant_id, other_engagement, item_id)


async def test_ac13_a_version_must_match_its_items_tenant(seed: Seeder, world: World) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    other = await seed.firm()
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.version(other, world.engagement_id, item_id)


async def test_ac13_an_items_engagement_must_be_in_its_tenant(seed: Seeder, world: World) -> None:
    other = await seed.firm()
    foreign_engagement = await seed.engagement(other)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.item(world.tenant_id, foreign_engagement)


async def test_ac13_a_version_for_a_missing_item_is_refused(seed: Seeder, world: World) -> None:
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.version(world.tenant_id, world.engagement_id, uuid.uuid4())


async def test_ac13_client_entity_id_must_be_in_the_tenant(seed: Seeder, world: World) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    other = await seed.firm()
    foreign_entity = await seed.entity_of(await seed.engagement(other))
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.version(
            world.tenant_id, world.engagement_id, item_id, client_entity_id=foreign_entity
        )
    await seed.version(
        world.tenant_id, world.engagement_id, item_id, client_entity_id=world.entity_id
    )


# --- database: CHECK constraints -----------------------------------------------------------------


async def test_ac13_storage_key_must_be_the_tenants_content_address(
    seed: Seeder, world: World
) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    fingerprint = "a" * 64
    for key in (
        f"tenants/{uuid.uuid4()}/sha256/{fingerprint}",
        f"tenants/{world.tenant_id}/sha256/{'b' * 64}",
        f"{world.tenant_id}/{fingerprint}",
        "anything-else",
    ):
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.version(
                world.tenant_id,
                world.engagement_id,
                item_id,
                fingerprint=fingerprint,
                storage_key=key,
            )
    await seed.version(world.tenant_id, world.engagement_id, item_id, fingerprint=fingerprint)


@pytest.mark.parametrize("fingerprint", ["a" * 63, "a" * 65, "A" * 64, "g" * 64, ""])
async def test_ac13_fingerprint_must_be_64_lower_case_hex_characters(
    seed: Seeder, world: World, fingerprint: str
) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.version(world.tenant_id, world.engagement_id, item_id, fingerprint=fingerprint)


@pytest.mark.parametrize("version_no", [0, -1])
async def test_ac13_version_no_must_be_at_least_one(
    seed: Seeder, world: World, version_no: int
) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.version(world.tenant_id, world.engagement_id, item_id, version_no=version_no)


async def test_ac13_version_no_is_unique_per_item_and_independent_across_items(
    seed: Seeder, world: World
) -> None:
    first = await seed.item(world.tenant_id, world.engagement_id)
    second = await seed.item(world.tenant_id, world.engagement_id)
    await seed.version(world.tenant_id, world.engagement_id, first, version_no=1)
    with pytest.raises(asyncpg.UniqueViolationError):
        await seed.version(world.tenant_id, world.engagement_id, first, version_no=1)
    await seed.version(world.tenant_id, world.engagement_id, first, version_no=2)
    await seed.version(world.tenant_id, world.engagement_id, second, version_no=1)


async def test_ac13_retrieved_evidence_needs_a_pull_time(seed: Seeder, world: World) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.version(
            world.tenant_id, world.engagement_id, item_id, method="retrieved", pulled_at=None
        )
    await seed.version(
        world.tenant_id, world.engagement_id, item_id, method="retrieved", pulled_at=PULLED_AT
    )
    await seed.version(
        world.tenant_id,
        world.engagement_id,
        item_id,
        version_no=2,
        method="uploaded",
        pulled_at=None,
    )


async def test_ac13_the_period_must_not_end_before_it_starts(seed: Seeder, world: World) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.version(
            world.tenant_id,
            world.engagement_id,
            item_id,
            period_start=date(2025, 12, 31),
            period_end=date(2025, 1, 1),
        )
    await seed.version(
        world.tenant_id,
        world.engagement_id,
        item_id,
        version_no=1,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 1),
    )


@pytest.mark.parametrize("method", ["pulled", "RETRIEVED", "", "manual"])
async def test_ac13_method_is_retrieved_or_uploaded(
    seed: Seeder, world: World, method: str
) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.version(
            world.tenant_id, world.engagement_id, item_id, method=method, pulled_at=PULLED_AT
        )


@pytest.mark.parametrize("title", ["", "t" * 201])
async def test_ac13_item_title_is_between_1_and_200_characters(
    seed: Seeder, world: World, title: str
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
            "created_by_id) VALUES ($1, $2, $3, 'system', 'seed')",
            world.tenant_id,
            world.engagement_id,
            title,
        )


# --- AC-13: immutability as abacus_app -----------------------------------------------------------


async def _app_error(ctx: TenantContext, statement: str, **params: object) -> str:
    with pytest.raises(DBAPIError) as raised:
        async with tenant_session(ctx) as session:
            await session.execute(text(statement), params)
    return str(raised.value)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE evidence_versions SET size_bytes = 1 WHERE id = :id",
        "UPDATE evidence_versions SET storage_version_id = 'other' WHERE id = :id",
        "UPDATE evidence_versions SET fingerprint = repeat('0', 64) WHERE id = :id",
        "UPDATE evidence_versions SET created_at = now() WHERE id = :id",
        "DELETE FROM evidence_versions WHERE id = :id",
        "TRUNCATE evidence_versions",
    ],
)
async def test_ac13_the_app_cannot_update_delete_or_truncate_a_version(
    seed: Seeder, world: World, statement: str
) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    version_id = await seed.version(world.tenant_id, world.engagement_id, item_id)
    message = await _app_error(
        world.system, statement, **({} if "TRUNCATE" in statement else {"id": version_id})
    )
    assert "permission denied" in message
    assert await seed.count("evidence_versions", world.tenant_id) == 1


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE evidence_items SET title = 'renamed' WHERE id = :id",
        "DELETE FROM evidence_items WHERE id = :id",
        "TRUNCATE evidence_items",
    ],
)
async def test_ac13_the_app_cannot_update_delete_or_truncate_an_item(
    seed: Seeder, world: World, statement: str
) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    message = await _app_error(
        world.system, statement, **({} if "TRUNCATE" in statement else {"id": item_id})
    )
    assert "permission denied" in message
    assert await seed.count("evidence_items", world.tenant_id) == 1


async def test_ac13_the_app_may_insert_only_the_listed_version_columns(
    seed: Seeder, world: World
) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    fingerprint = "d" * 64
    params: dict[str, object] = {
        "tenant": world.tenant_id,
        "engagement": world.engagement_id,
        "item": item_id,
        "fingerprint": fingerprint,
        "key": f"tenants/{world.tenant_id}/sha256/{fingerprint}",
    }
    async with tenant_session(world.system) as session:  # control: the listed columns insert
        await session.execute(text(INSERT_VERSION), params)
    message = await _app_error(world.system, INSERT_VERSION_WITH_CREATED_AT, **params)
    assert "permission denied" in message
    assert await seed.count("evidence_versions", world.tenant_id) == 0


async def test_ac13_the_app_may_insert_only_the_listed_item_columns(
    seed: Seeder, world: World
) -> None:
    message = await _app_error(
        world.system,
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id, created_at) VALUES (:tenant, :engagement, 't', 'system', 'x', now())",
        tenant=world.tenant_id,
        engagement=world.engagement_id,
    )
    assert "permission denied" in message


# --- AC-13: immutability as superuser (trigger) --------------------------------------------------


async def test_ac13_the_trigger_rejects_update_even_for_the_superuser(
    seed: Seeder, world: World
) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    version_id = await seed.version(world.tenant_id, world.engagement_id, item_id)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run("UPDATE evidence_versions SET size_bytes = 99 WHERE id = $1", version_id)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run("UPDATE evidence_versions SET media_type = 'x/y' WHERE id = $1", version_id)
    assert (
        await seed.value("SELECT size_bytes FROM evidence_versions WHERE id = $1", version_id)
        == 10
    )


async def test_ac13_the_trigger_rejects_delete_even_for_the_superuser(
    seed: Seeder, world: World
) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    version_id = await seed.version(world.tenant_id, world.engagement_id, item_id)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run("DELETE FROM evidence_versions WHERE id = $1", version_id)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run("DELETE FROM evidence_versions WHERE tenant_id = $1", world.tenant_id)
    assert await seed.count("evidence_versions", world.tenant_id) == 1


async def test_ac13_the_trigger_rejects_truncate_even_for_the_superuser(
    seed: Seeder, world: World
) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    await seed.version(world.tenant_id, world.engagement_id, item_id)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run("TRUNCATE evidence_versions")
    assert await seed.count("evidence_versions", world.tenant_id) == 1


async def test_ac13_the_trigger_rejects_truncate_by_the_table_owner(
    migrated_db: Migrated, seed: Seeder, world: World
) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    await seed.version(world.tenant_id, world.engagement_id, item_id)
    owner = Seeder(migrated_db.owner_url.replace("postgresql+asyncpg://", "postgresql://"))
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await owner.run("TRUNCATE evidence_versions")
    assert await seed.count("evidence_versions", world.tenant_id) == 1


async def test_ac13_inserting_new_versions_is_still_allowed_for_the_superuser(
    seed: Seeder, world: World
) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    await seed.version(world.tenant_id, world.engagement_id, item_id, version_no=1)
    await seed.version(world.tenant_id, world.engagement_id, item_id, version_no=2)
    assert await seed.count("evidence_versions", world.tenant_id) == 2


# --- service: versions ---------------------------------------------------------------------------


async def test_ac13_a_new_item_gets_version_one_and_the_ref_describes_it(
    seed: Seeder, world: World
) -> None:
    content = _content()
    ref = await _add(
        world, item=NewItem("Trial balance"), content=content, media_type="text/plain"
    )
    assert ref.version_no == 1
    assert ref.engagement_id == world.engagement_id
    assert ref.fingerprint == hashlib.sha256(content).hexdigest()
    assert ref.size_bytes == len(content)
    assert ref.media_type == "text/plain"
    item = await seed.rows("SELECT * FROM evidence_items WHERE id = $1", ref.evidence_item_id)
    assert [(r["title"], r["engagement_id"], r["tenant_id"]) for r in item] == [
        ("Trial balance", world.engagement_id, world.tenant_id)
    ]


async def test_ac13_each_later_call_on_the_item_is_the_next_version(
    seed: Seeder, world: World
) -> None:
    first = await _add(world)
    second = await _add(world, item=first.evidence_item_id)
    third = await _add(world, item=first.evidence_item_id)
    assert [first.version_no, second.version_no, third.version_no] == [1, 2, 3]
    assert {second.evidence_item_id, third.evidence_item_id} == {first.evidence_item_id}
    assert len({first.id, second.id, third.id}) == 3
    assert await seed.count("evidence_items", world.tenant_id) == 1
    assert await seed.count("evidence_versions", world.tenant_id) == 3


async def test_ac13_numbering_is_per_item(world: World) -> None:
    one = await _add(world, item=NewItem("One"))
    two = await _add(world, item=NewItem("Two"))
    again = await _add(world, item=one.evidence_item_id)
    assert (one.version_no, two.version_no, again.version_no) == (1, 1, 2)


async def test_ac13_rows_carry_the_provenance_fields_and_the_actor(
    seed: Seeder, world: World
) -> None:
    snapshot_id = uuid.uuid4()
    provenance = Provenance(
        source="quickbooks",
        method="retrieved",
        pulled_at=PULLED_AT,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        client_entity_id=world.entity_id,
        snapshot_id=snapshot_id,
    )
    content = _content()
    ref = await _add(world, content=content, provenance=provenance, media_type="text/csv")
    [row] = await seed.rows("SELECT * FROM evidence_versions WHERE id = $1", ref.id)
    assert row["tenant_id"] == world.tenant_id
    assert row["engagement_id"] == world.engagement_id
    assert row["evidence_item_id"] == ref.evidence_item_id
    assert row["version_no"] == 1
    assert row["fingerprint"] == hashlib.sha256(content).hexdigest()
    assert row["storage_key"] == f"tenants/{world.tenant_id}/sha256/{row['fingerprint']}"
    assert row["size_bytes"] == len(content)
    assert row["media_type"] == "text/csv"
    assert row["source"] == "quickbooks"
    assert row["method"] == "retrieved"
    assert row["pulled_at"] == PULLED_AT
    assert row["period_start"] == date(2025, 1, 1)
    assert row["period_end"] == date(2025, 12, 31)
    assert row["client_entity_id"] == world.entity_id
    assert row["snapshot_id"] == snapshot_id
    [item] = await seed.rows("SELECT * FROM evidence_items WHERE id = $1", ref.evidence_item_id)
    assert (item["created_by_kind"], item["created_by_id"]) == (SYSTEM, ACTOR)


async def test_ac13_created_by_comes_from_the_tenant_context(seed: Seeder, world: World) -> None:
    human = TenantContext(world.tenant_id, "human", str(uuid.uuid4()))
    ref = await _add(world, ctx=human)
    [item] = await seed.rows("SELECT * FROM evidence_items WHERE id = $1", ref.evidence_item_id)
    assert (item["created_by_kind"], item["created_by_id"]) == ("human", human.actor_id)


async def test_ac13_the_stored_object_is_the_content_and_is_read_back_verified(
    world: World, evidence_storage: S3Client
) -> None:
    content = _content()
    ref = await _add(world, content=content)
    key = f"tenants/{world.tenant_id}/sha256/{ref.fingerprint}"
    assert len(_object_versions(evidence_storage, key)) == 1
    stored = await storage.get(
        world.tenant_id,
        storage.StoredObject(
            key, _object_versions(evidence_storage, key)[0], ref.fingerprint, ref.size_bytes
        ),
    )
    assert stored == content


async def test_ac13_two_versions_with_the_same_content_share_one_object(
    seed: Seeder, world: World, evidence_storage: S3Client
) -> None:
    content = _content()
    first = await _add(world, content=content)
    second = await _add(world, item=first.evidence_item_id, content=content)
    assert first.fingerprint == second.fingerprint
    assert second.version_no == 2
    rows = await seed.rows(
        "SELECT storage_key, storage_version_id FROM evidence_versions WHERE tenant_id = $1",
        world.tenant_id,
    )
    assert len({(r["storage_key"], r["storage_version_id"]) for r in rows}) == 1
    assert len(_object_versions(evidence_storage, rows[0]["storage_key"])) == 1


async def test_ac13_missing_or_foreign_items_are_not_found_and_leave_nothing_behind(
    seed: Seeder, world: World
) -> None:
    other = await seed.firm()
    foreign_item = await seed.item(other, await seed.engagement(other))
    with pytest.raises(NotFound):
        await _add(world, item=foreign_item)
    with pytest.raises(NotFound):
        await _add(world, item=uuid.uuid4())
    for table in ("evidence_items", "evidence_versions", "audit_events", "outbox"):
        assert await seed.count(table, world.tenant_id) == 0, table


async def test_ac13_retrieved_evidence_without_a_pull_time_is_refused_and_leaves_nothing(
    seed: Seeder, world: World
) -> None:
    with pytest.raises(DBAPIError):
        await _add(world, provenance=Provenance(source="quickbooks", method="retrieved"))
    for table in ("evidence_items", "evidence_versions", "audit_events", "outbox"):
        assert await seed.count(table, world.tenant_id) == 0, table


async def test_ac13_an_item_of_another_engagement_is_not_found(seed: Seeder, world: World) -> None:
    other_engagement = await seed.engagement(world.tenant_id)
    item_id = await seed.item(world.tenant_id, other_engagement)
    with pytest.raises(NotFound):
        await _add(world, item=item_id)
    assert await seed.count("evidence_versions", world.tenant_id) == 0


async def test_ac13_a_missing_or_foreign_engagement_is_not_found(
    seed: Seeder, world: World
) -> None:
    other = await seed.firm()
    foreign_engagement = await seed.engagement(other)
    with pytest.raises(NotFound):
        await _add(world, engagement_id=foreign_engagement)
    with pytest.raises(NotFound):
        await _add(world, engagement_id=uuid.uuid4())
    for table in ("evidence_items", "evidence_versions", "audit_events", "outbox"):
        assert await seed.count(table, world.tenant_id) == 0, table


async def test_ac13_an_archived_engagement_refuses_new_versions(
    seed: Seeder, world: World
) -> None:
    first = await _add(world)
    await seed.run("UPDATE engagements SET status = 'archived' WHERE id = $1", world.engagement_id)
    with pytest.raises(EngagementArchived):
        await _add(world, item=first.evidence_item_id)
    with pytest.raises(EngagementArchived):
        await _add(world, item=NewItem("Another"))
    assert await seed.count("evidence_versions", world.tenant_id) == 1


async def test_ac13_staged_content_of_another_tenant_is_an_integrity_error(
    seed: Seeder, world: World
) -> None:
    other = await seed.firm()
    foreign = await stage_content(other, _content())
    with pytest.raises(IntegrityError):
        async with uow(world.system) as tx:
            await add_version(
                tx,
                engagement_id=world.engagement_id,
                item=NewItem("Foreign"),
                stored=foreign,
                media_type="text/plain",
                provenance=_uploaded(),
            )
    for table in ("evidence_items", "evidence_versions", "audit_events", "outbox"):
        assert await seed.count(table, world.tenant_id) == 0, table


@pytest.mark.parametrize("media_type", ["", "m" * 101])
async def test_ac13_media_type_must_be_1_to_100_characters(
    seed: Seeder, world: World, media_type: str
) -> None:
    with pytest.raises(ValueError):
        await _add(world, media_type=media_type)
    assert await seed.count("evidence_versions", world.tenant_id) == 0
    await _add(world, media_type="m" * 100)


async def test_ac13_stage_content_stores_without_touching_the_database(
    seed: Seeder, world: World, evidence_storage: S3Client
) -> None:
    content = _content()
    stored = await stage_content(world.tenant_id, content)
    assert stored.key == f"tenants/{world.tenant_id}/sha256/{hashlib.sha256(content).hexdigest()}"
    assert stored.size == len(content)
    assert len(_object_versions(evidence_storage, stored.key)) == 1
    assert await read_content(world.system, stored) == content
    for table in ("evidence_items", "evidence_versions", "audit_events", "outbox"):
        assert await seed.count(table, world.tenant_id) == 0, table


async def test_ac13_read_content_refuses_a_record_that_does_not_match(world: World) -> None:
    stored = await stage_content(world.tenant_id, _content())
    lying = StoredObject(stored.key, stored.version_id, stored.fingerprint, stored.size + 1)
    with pytest.raises(IntegrityError):
        await read_content(world.system, lying)
    with pytest.raises(IntegrityError):
        await read_content(TenantContext(uuid.uuid4(), SYSTEM, ACTOR), stored)


async def test_ac13_a_new_ref_says_it_was_created(world: World) -> None:
    assert (await _add(world)).created is True


# --- service: idempotency ------------------------------------------------------------------------


async def test_ac20_a_repeated_idempotency_key_returns_the_existing_version(
    seed: Seeder, world: World
) -> None:
    content = _content()
    first = await _add(world, content=content, idempotency_key="pull-2026-03-14")
    again = await _add(
        world, item=first.evidence_item_id, content=content, idempotency_key="pull-2026-03-14"
    )
    assert first.created is True
    assert again.created is False
    assert again.id == first.id
    assert again.version_no == 1
    assert await seed.count("evidence_versions", world.tenant_id) == 1


async def test_ac20_a_repeated_key_records_no_audit_or_outbox_event(
    seed: Seeder, world: World
) -> None:
    content = _content()
    first = await _add(world, content=content, idempotency_key="k-1")
    audit_before = await seed.count("audit_events", world.tenant_id)
    outbox_before = await seed.count("outbox", world.tenant_id)
    stored = await stage_content(world.tenant_id, content)
    async with uow(world.system) as tx:
        again = await add_version(
            tx,
            engagement_id=world.engagement_id,
            item=first.evidence_item_id,
            stored=stored,
            media_type="text/plain",
            provenance=_uploaded(),
            idempotency_key="k-1",
        )
        tx.record("evidence_version.noted", target=_target(again.id))
    assert again.created is False
    assert await seed.count("outbox", world.tenant_id) == outbox_before
    assert await seed.count("audit_events", world.tenant_id) == audit_before + 1


async def test_ac20_a_repeated_key_does_not_create_a_second_item(
    seed: Seeder, world: World
) -> None:
    content = _content()
    await _add(world, content=content, idempotency_key="k-2")
    await _add(world, content=content, idempotency_key="k-2")
    assert await seed.count("evidence_items", world.tenant_id) == 1


async def test_ac20_a_repeated_key_with_different_content_is_refused(
    seed: Seeder, world: World
) -> None:
    first = await _add(world, content=_content(), idempotency_key="k-3")
    with pytest.raises(ValueError, match="idempotency key reused"):
        await _add(world, item=first.evidence_item_id, content=_content(), idempotency_key="k-3")
    assert await seed.count("evidence_versions", world.tenant_id) == 1


async def test_ac20_a_repeated_key_with_a_different_engagement_is_refused(
    seed: Seeder, world: World
) -> None:
    content = _content()
    await _add(world, content=content, idempotency_key="k-4")
    other_engagement = await seed.engagement(world.tenant_id)
    with pytest.raises(ValueError, match="idempotency key reused"):
        await _add(
            world,
            item=NewItem("Elsewhere"),
            content=content,
            idempotency_key="k-4",
            engagement_id=other_engagement,
        )
    assert await seed.count("evidence_versions", world.tenant_id) == 1
    assert await seed.count("evidence_items", world.tenant_id) == 1


async def test_ac20_a_repeat_with_the_same_content_ignores_item_media_type_and_provenance(
    seed: Seeder, world: World
) -> None:
    content = _content()
    first = await _add(world, content=content, idempotency_key="k-5")
    again = await _add(
        world,
        item=NewItem("Ignored"),
        content=content,
        media_type="text/plain",
        provenance=Provenance(source="other", method="uploaded"),
        idempotency_key="k-5",
    )
    assert (again.created, again.id, again.evidence_item_id) == (
        False,
        first.id,
        first.evidence_item_id,
    )
    assert again.media_type == first.media_type
    assert await seed.count("evidence_items", world.tenant_id) == 1


async def test_ac20_different_keys_and_no_key_each_create_a_version(
    seed: Seeder, world: World
) -> None:
    first = await _add(world, idempotency_key="a")
    second = await _add(world, item=first.evidence_item_id, idempotency_key="b")
    third = await _add(world, item=first.evidence_item_id)
    fourth = await _add(world, item=first.evidence_item_id)
    assert [r.version_no for r in (first, second, third, fourth)] == [1, 2, 3, 4]
    assert all(r.created for r in (first, second, third, fourth))


async def test_ac20_idempotency_keys_are_scoped_to_the_tenant(seed: Seeder, world: World) -> None:
    other_tenant = await seed.firm()
    other = World(other_tenant, await seed.engagement(other_tenant), world.entity_id)
    first = await _add(world, idempotency_key="shared")
    second = await _add(other, idempotency_key="shared")
    assert first.created is True
    assert second.created is True
    assert first.id != second.id


@pytest.mark.parametrize("key", ["", "k" * 201])
async def test_ac20_idempotency_keys_are_1_to_200_characters(
    seed: Seeder, world: World, key: str
) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.version(world.tenant_id, world.engagement_id, item_id, idempotency_key=key)


async def test_ac20_the_idempotency_key_is_unique_per_tenant_where_set(
    seed: Seeder, world: World
) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    await seed.version(world.tenant_id, world.engagement_id, item_id, idempotency_key="once")
    with pytest.raises(asyncpg.UniqueViolationError):
        await seed.version(
            world.tenant_id, world.engagement_id, item_id, version_no=2, idempotency_key="once"
        )
    await seed.version(world.tenant_id, world.engagement_id, item_id, version_no=2)
    await seed.version(world.tenant_id, world.engagement_id, item_id, version_no=3)


async def test_ac20_the_app_may_insert_the_idempotency_key_column(
    seed: Seeder, world: World
) -> None:
    item_id = await seed.item(world.tenant_id, world.engagement_id)
    fingerprint = "9" * 64
    async with tenant_session(world.system) as session:
        await session.execute(
            text(
                INSERT_VERSION.replace("method)", "method, idempotency_key)").replace(
                    "'uploaded')", "'uploaded', 'app-key')"
                )
            ),
            {
                "tenant": world.tenant_id,
                "engagement": world.engagement_id,
                "item": item_id,
                "fingerprint": fingerprint,
                "key": f"tenants/{world.tenant_id}/sha256/{fingerprint}",
            },
        )
    assert "idempotency_key" in sc.APP_INSERT_COLUMNS["evidence_versions"]


async def test_ac13_the_transaction_context_is_read_back_from_the_transaction(
    world: World,
) -> None:
    async with tenant_session(world.system) as session:
        assert await transaction_context(session) == world.system
    async with uow(TenantContext(world.tenant_id, "human", "someone")) as tx:
        assert await transaction_context(tx.session) == TenantContext(
            world.tenant_id, "human", "someone"
        )
        tx.record("evidence_version.noted", target=_target(uuid.uuid4()))


# --- service: audit and outbox -------------------------------------------------------------------


async def _audit(seed: Seeder, tenant_id: uuid.UUID) -> list[dict[str, object]]:
    rows = await seed.rows(
        "SELECT action, actor_kind, actor_id, target_type, target_id, after_ref FROM audit_events "
        "WHERE tenant_id = $1 ORDER BY seq",
        tenant_id,
    )
    return [
        {
            "action": r["action"],
            "actor_kind": r["actor_kind"],
            "actor_id": r["actor_id"],
            "target_type": r["target_type"],
            "target_id": r["target_id"],
            "after": json.loads(cast(str, r["after_ref"])) if r["after_ref"] else None,
        }
        for r in rows
    ]


async def test_ac13_a_new_item_records_item_and_version_audit_events(
    seed: Seeder, world: World
) -> None:
    ref = await _add(world)
    events = await _audit(seed, world.tenant_id)
    by_action = {e["action"]: e for e in events}
    assert set(by_action) == {"evidence_item.created", "evidence_version.created"}
    assert len(events) == 2
    item_event = by_action["evidence_item.created"]
    assert item_event["target_type"] == "evidence_item"
    assert item_event["target_id"] == str(ref.evidence_item_id)
    assert cast(dict[str, object], item_event["after"])["engagement_id"] == str(
        world.engagement_id
    )
    version_event = by_action["evidence_version.created"]
    assert version_event["target_type"] == "evidence_version"
    assert version_event["target_id"] == str(ref.id)
    after = cast(dict[str, object], version_event["after"])
    assert after["evidence_item_id"] == str(ref.evidence_item_id)
    assert after["fingerprint"] == ref.fingerprint
    for event in events:
        assert (event["actor_kind"], event["actor_id"]) == (SYSTEM, ACTOR)


async def test_ac13_a_later_version_records_only_the_version_audit_event(
    seed: Seeder, world: World
) -> None:
    first = await _add(world)
    second = await _add(world, item=first.evidence_item_id)
    events = await _audit(seed, world.tenant_id)
    assert [e["action"] for e in events].count("evidence_item.created") == 1
    assert [e["action"] for e in events].count("evidence_version.created") == 2
    assert events[-1]["target_id"] == str(second.id)


async def test_ac13_the_audit_trail_never_holds_the_content_or_the_title(
    seed: Seeder, world: World
) -> None:
    title = f"Secret title {uuid.uuid4()}"
    content = _content("secret body")
    await _add(world, item=NewItem(title), content=content)
    rows = await seed.rows(
        "SELECT row_to_json(a)::text AS doc FROM audit_events a WHERE tenant_id = $1",
        world.tenant_id,
    )
    blob = " ".join(str(r["doc"]) for r in rows)
    assert title not in blob
    assert "secret body" not in blob


async def test_ac13_the_outbox_event_carries_identifiers_only(seed: Seeder, world: World) -> None:
    ref = await _add(world, item=NewItem("Outbox probe"))
    rows = await seed.rows(
        "SELECT event_type, payload FROM outbox WHERE tenant_id = $1 ORDER BY seq",
        world.tenant_id,
    )
    assert [r["event_type"] for r in rows] == ["evidence_version.created"]
    payload = cast(dict[str, object], json.loads(cast(str, rows[0]["payload"])))
    assert payload["evidence_version_id"] == str(ref.id)
    assert payload["evidence_item_id"] == str(ref.evidence_item_id)
    assert payload["engagement_id"] == str(world.engagement_id)
    assert "Outbox probe" not in json.dumps(payload)
    assert ref.fingerprint not in json.dumps(payload)


# --- service: concurrency ------------------------------------------------------------------------


async def test_ac13_concurrent_calls_on_one_item_get_distinct_consecutive_numbers(
    seed: Seeder, world: World
) -> None:
    first = await _add(world)
    refs = await asyncio.gather(*(_add(world, item=first.evidence_item_id) for _ in range(6)))
    numbers = sorted([first.version_no, *(r.version_no for r in refs)])
    assert numbers == [1, 2, 3, 4, 5, 6, 7]
    assert await seed.count("evidence_versions", world.tenant_id) == 7


async def test_ac13_concurrent_calls_with_the_same_content_get_distinct_numbers(
    seed: Seeder, world: World, evidence_storage: S3Client
) -> None:
    first = await _add(world)
    content = _content()
    refs = await asyncio.gather(
        *(_add(world, item=first.evidence_item_id, content=content) for _ in range(5))
    )
    assert sorted(r.version_no for r in refs) == [2, 3, 4, 5, 6]
    assert len({r.fingerprint for r in refs}) == 1
    key = f"tenants/{world.tenant_id}/sha256/{refs[0].fingerprint}"
    assert len(_object_versions(evidence_storage, key)) == 1


# --- service: failure and retry ------------------------------------------------------------------


async def test_ac13_a_failed_unit_of_work_leaves_no_rows_and_a_retry_reuses_the_object(
    seed: Seeder, world: World, evidence_storage: S3Client
) -> None:
    content = _content()
    key = f"tenants/{world.tenant_id}/sha256/{hashlib.sha256(content).hexdigest()}"
    stored = await stage_content(world.tenant_id, content)
    with pytest.raises(RuntimeError, match="boom"):
        async with uow(world.system) as tx:
            await add_version(
                tx,
                engagement_id=world.engagement_id,
                item=NewItem("Doomed"),
                stored=stored,
                media_type="text/plain",
                provenance=_uploaded(),
            )
            raise RuntimeError("boom")
    for table in ("evidence_items", "evidence_versions", "audit_events", "outbox"):
        assert await seed.count(table, world.tenant_id) == 0, table
    orphan = _object_versions(evidence_storage, key)
    assert len(orphan) == 1
    ref = await _add(world, item=NewItem("Retried"), content=content)
    assert ref.version_no == 1
    assert _object_versions(evidence_storage, key) == orphan
    stored_version = await seed.value(
        "SELECT storage_version_id FROM evidence_versions WHERE id = $1", ref.id
    )
    assert stored_version == orphan[0]
    assert await seed.count("evidence_versions", world.tenant_id) == 1


async def test_ac13_a_database_failure_after_the_object_is_stored_is_retryable(
    seed: Seeder, world: World, evidence_storage: S3Client
) -> None:
    content = _content()
    key = f"tenants/{world.tenant_id}/sha256/{hashlib.sha256(content).hexdigest()}"
    with pytest.raises(DBAPIError):
        await _add(world, content=content, provenance=Provenance(source="x", method="retrieved"))
    orphan = _object_versions(evidence_storage, key)
    assert len(orphan) == 1
    ref = await _add(world, content=content, provenance=_uploaded())
    assert _object_versions(evidence_storage, key) == orphan
    assert ref.version_no == 1
    assert await seed.count("audit_events", world.tenant_id) == 2


# --- AC-12 end to end ----------------------------------------------------------------------------


async def test_ac12_rendering_the_same_snapshot_twice_stores_one_object_and_two_versions(
    seed: Seeder, world: World, evidence_storage: S3Client
) -> None:
    snapshot = TrialBalance(
        client_entity_id=world.entity_id,
        entity_name="Seeded entity",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        pulled_at=PULLED_AT,
        snapshot_id=uuid.uuid4(),
        source="quickbooks",
        source_fingerprint="e" * 64,
        lines=(
            TrialBalanceLine("1000", "Cash", Decimal("100.00"), Decimal("0.00")),
            TrialBalanceLine("2000", "Payables", Decimal("0.00"), Decimal("100.00")),
        ),
    )
    provenance = Provenance(
        source="quickbooks",
        method="retrieved",
        pulled_at=PULLED_AT,
        period_start=snapshot.period_start,
        period_end=snapshot.period_end,
        client_entity_id=world.entity_id,
        snapshot_id=snapshot.snapshot_id,
    )
    first_bytes = render_trial_balance(snapshot)
    first = await _add(
        world, content=first_bytes, media_type=XLSX_MEDIA_TYPE, provenance=provenance
    )
    await asyncio.sleep(1.1)
    second = await _add(
        world,
        item=first.evidence_item_id,
        content=render_trial_balance(snapshot),
        media_type=XLSX_MEDIA_TYPE,
        provenance=provenance,
    )
    assert first.fingerprint == second.fingerprint
    assert (first.version_no, second.version_no) == (1, 2)
    key = f"tenants/{world.tenant_id}/sha256/{first.fingerprint}"
    assert len(_object_versions(evidence_storage, key)) == 1


# --- service: read_version -----------------------------------------------------------------------


@pytest.mark.parametrize("role", ENGAGEMENT_ROLES)
async def test_ac13_an_engagement_member_allowed_evidence_read_gets_the_bytes(
    seed: Seeder, world: World, role: str
) -> None:
    content = _content()
    ref = await _add(world, content=content)
    who = await seed.person(world.tenant_id, None)
    await seed.member(world.engagement_id, who, role)
    assert await read_version(who.context(), ref.id) == content


async def test_ac13_a_member_who_is_also_a_firm_admin_may_read(seed: Seeder, world: World) -> None:
    content = _content()
    ref = await _add(world, content=content)
    who = await seed.person(world.tenant_id, "firm_admin")
    await seed.member(world.engagement_id, who, "manager")
    assert await read_version(who.context(), ref.id) == content


async def test_ac13_a_firm_admin_who_is_not_a_member_is_forbidden(
    seed: Seeder, world: World
) -> None:
    ref = await _add(world)
    who = await seed.person(world.tenant_id, "firm_admin")
    with pytest.raises(Forbidden):
        await read_version(who.context(), ref.id)


async def test_ac13_a_person_with_no_role_on_the_engagement_is_forbidden(
    seed: Seeder, world: World
) -> None:
    ref = await _add(world)
    who = await seed.person(world.tenant_id, None)
    with pytest.raises(Forbidden):
        await read_version(who.context(), ref.id)


async def test_ac13_a_member_of_another_engagement_is_forbidden(
    seed: Seeder, world: World
) -> None:
    ref = await _add(world)
    other_engagement = await seed.engagement(world.tenant_id)
    who = await seed.person(world.tenant_id, None)
    await seed.member(other_engagement, who, "manager")
    with pytest.raises(Forbidden):
        await read_version(who.context(), ref.id)


async def test_ac13_another_firms_version_is_not_found(seed: Seeder, world: World) -> None:
    ref = await _add(world)
    other_tenant = await seed.firm()
    other_engagement = await seed.engagement(other_tenant)
    who = await seed.person(other_tenant, None)
    await seed.member(other_engagement, who, "engagement_partner")
    with pytest.raises(NotFound):
        await read_version(who.context(), ref.id)


async def test_ac13_a_missing_version_is_not_found(seed: Seeder, world: World) -> None:
    who = await seed.person(world.tenant_id, None)
    await seed.member(world.engagement_id, who, "manager")
    with pytest.raises(NotFound):
        await read_version(who.context(), uuid.uuid4())


async def test_ac13_read_version_refuses_content_that_no_longer_matches_its_record(
    seed: Seeder, world: World, evidence_storage: S3Client
) -> None:
    content = _content()
    ref = await _add(world, content=content)
    who = await seed.person(world.tenant_id, None)
    await seed.member(world.engagement_id, who, "manager")
    key = f"tenants/{world.tenant_id}/sha256/{ref.fingerprint}"
    evidence_storage.put_object(Bucket=BUCKET, Key=key, Body=b"ABE1 not the evidence")
    assert await read_version(who.context(), ref.id) == content  # the recorded version is pinned


async def test_ac13_read_version_records_an_audit_event_for_the_reader(
    seed: Seeder, world: World
) -> None:
    ref = await _add(world)
    who = await seed.person(world.tenant_id, None)
    await seed.member(world.engagement_id, who, "senior")
    await read_version(who.context(), ref.id)
    reads = [
        e for e in await _audit(seed, world.tenant_id) if e["action"] == "evidence_version.read"
    ]
    assert len(reads) == 1
    assert reads[0]["target_type"] == "evidence_version"
    assert reads[0]["target_id"] == str(ref.id)
    assert (reads[0]["actor_kind"], reads[0]["actor_id"]) == ("human", str(who.user_id))


async def test_ac13_a_forbidden_read_records_no_read_event(seed: Seeder, world: World) -> None:
    ref = await _add(world)
    who = await seed.person(world.tenant_id, "firm_admin")
    with pytest.raises(Forbidden):
        await read_version(who.context(), ref.id)
    actions = [e["action"] for e in await _audit(seed, world.tenant_id)]
    assert "evidence_version.read" not in actions
