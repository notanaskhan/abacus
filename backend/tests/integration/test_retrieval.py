"""AC-9, AC-10, AC-11, AC-20: starting a retrieval, resuming its system context, the pipeline
stages and `fulfil_by_rule` (TASK-010a interface contract and revision 1).

Rows are seeded as the superuser (`migrated_db.superuser_dsn`) with fresh firms per test, so tests
never need cleanup. Provider responses come from `abacus_tools.synthetic.connector_fixtures`,
written under a per-test directory that `ABACUS_FAKE_CONNECTOR_DIR` names. Objects go to a bucket
of this module on the Versity gateway. Expectations come from the contract, not the
implementation.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol, cast

import asyncpg
import pytest
from sqlalchemy.exc import DBAPIError
from types_boto3_s3 import S3Client

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import (
    TenantContext,
    configure_engine,
    dispose_engine,
)
from abacus.kernel.errors import NotFound
from abacus.kernel.storage import s3_client
from abacus.kernel.uow import Target, uow
from abacus.modules.connections.api import (
    NoConnection,
    Period,
    RunFailed,
    RunNotRunning,
    RunResult,
    StartedRun,
    Unavailable,
    fail_run,
    load_system_context,
    normalise_raw,
    pull_raw,
    render,
    run_pipeline,
    snapshot,
    start_retrieval,
    validate_run,
)
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import XLSX_MEDIA_TYPE, StoredObject, read_content
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    SystemContext,
    system_context_for_run,
)
from abacus.modules.requests.api import FulfilmentRef, ItemNotFulfillable, fulfil_by_rule
from abacus_tools.synthetic import generate
from abacus_tools.synthetic.connector_fixtures import (
    trial_balance_document,
    write_fault,
    write_raw,
    write_trial_balance,
)

MASTER = b"retrieval-test-master-key-0123456789abcdef"
BUCKET = f"retrieval-{uuid.uuid4().hex[:12]}"
ENTITY = generate(1).client_entities[0]
TB = ENTITY.trial_balances[-1]
PERIOD = Period(ENTITY.period_start, TB.as_of)
ENTITY_NAME = "Seeded entity"
EXPECTED_EVENTS = [
    "sync_run.started",
    "sync_run.raw_stored",
    "ledger_snapshot.created",
    "sync_run.snapshot_linked",
    "evidence_item.created",
    "evidence_version.created",
    "fulfilment.created",
    "request_item.received",
    "sync_run.succeeded",
]
Role = Literal["engagement_partner", "manager", "senior", "staff", "reviewer"]


class Migrated(Protocol):
    owner_url: str
    app_url: str
    identity_url: str
    superuser_dsn: str


# --- seeding (superuser) -------------------------------------------------------------------------

COUNTS = {
    "sync_runs": "SELECT count(*) FROM sync_runs WHERE tenant_id = $1",
    "ledger_snapshots": "SELECT count(*) FROM ledger_snapshots WHERE tenant_id = $1",
    "trial_balance_lines": "SELECT count(*) FROM trial_balance_lines WHERE tenant_id = $1",
    "evidence_items": "SELECT count(*) FROM evidence_items WHERE tenant_id = $1",
    "evidence_versions": "SELECT count(*) FROM evidence_versions WHERE tenant_id = $1",
    "fulfilments": "SELECT count(*) FROM fulfilments WHERE tenant_id = $1",
    "audit_events": "SELECT count(*) FROM audit_events WHERE tenant_id = $1",
    "outbox": "SELECT count(*) FROM outbox WHERE tenant_id = $1",
}


@dataclass(frozen=True)
class Person:
    user_id: uuid.UUID
    tenant_id: uuid.UUID

    def context(self) -> AuthContext:
        return AuthContext(
            tenant=TenantContext(self.tenant_id, "human", str(self.user_id)),
            user_id=self.user_id,
            membership_id=uuid.uuid4(),
            firm_role=None,
            mfa_at=datetime.now(UTC) - timedelta(minutes=1),
        )


@dataclass(frozen=True)
class Event:
    action: str
    actor_kind: str
    actor_id: str
    after: dict[str, object]


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

    async def count(self, table: str, tenant_id: uuid.UUID) -> int:
        return cast(int, await self.value(COUNTS[table], tenant_id))

    async def firm(self) -> uuid.UUID:
        tenant_id = uuid.uuid4()
        await self.run(
            "INSERT INTO firms (tenant_id, name) VALUES ($1, $2)",
            tenant_id,
            f"Firm {tenant_id.hex[:8]}",
        )
        return tenant_id

    async def person(self, tenant_id: uuid.UUID) -> Person:
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
        return Person(user_id, tenant_id)

    async def entity(self, tenant_id: uuid.UUID, name: str = ENTITY_NAME) -> uuid.UUID:
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
                "VALUES ($1, $2, $3) RETURNING id",
                tenant_id,
                client_id,
                name,
            ),
        )

    async def engagement(
        self, tenant_id: uuid.UUID, entity_id: uuid.UUID, created_by: uuid.UUID
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
                created_by,
            ),
        )

    async def member(self, engagement_id: uuid.UUID, who: Person, role: Role) -> None:
        await self.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            who.tenant_id,
            engagement_id,
            who.user_id,
            role,
        )

    async def item(
        self, tenant_id: uuid.UUID, engagement_id: uuid.UUID, created_by: uuid.UUID
    ) -> uuid.UUID:
        list_id = cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO request_lists (tenant_id, engagement_id) VALUES ($1, $2) "
                "ON CONFLICT (tenant_id, engagement_id) DO UPDATE SET tenant_id = $1 "
                "RETURNING id",
                tenant_id,
                engagement_id,
            ),
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
                created_by,
            ),
        )

    async def connection(
        self,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        *,
        status: str = "active",
        expires_at: datetime | None = None,
    ) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO connections (tenant_id, client_entity_id, provider, status, "
                "expires_at, created_by) VALUES ($1, $2, 'fake', $3, $4, 'test-seed') "
                "RETURNING id",
                tenant_id,
                entity_id,
                status,
                expires_at,
            ),
        )

    async def evidence_version(self, tenant_id: uuid.UUID, engagement_id: uuid.UUID) -> uuid.UUID:
        item_id = await self.value(
            "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
            "created_by_id) VALUES ($1, $2, 'Seeded evidence', 'system', 'seed') RETURNING id",
            tenant_id,
            engagement_id,
        )
        fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        return cast(
            uuid.UUID,
            await self.value(
                "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
                "version_no, fingerprint, storage_key, storage_version_id, size_bytes, "
                "media_type, source, method) VALUES ($1, $2, $3, 1, $4, $5, 'v1', 10, "
                "'application/pdf', 'upload', 'uploaded') RETURNING id",
                tenant_id,
                engagement_id,
                item_id,
                fingerprint,
                f"tenants/{tenant_id}/sha256/{fingerprint}",
            ),
        )

    async def events(self, tenant_id: uuid.UUID) -> list[Event]:
        rows = await self.rows(
            "SELECT action, actor_kind, actor_id, after_ref::text AS after FROM audit_events "
            "WHERE tenant_id = $1 ORDER BY seq",
            tenant_id,
        )
        return [
            Event(
                str(r["action"]),
                str(r["actor_kind"]),
                str(r["actor_id"]),
                cast(dict[str, object], json.loads(r["after"])) if r["after"] else {},
            )
            for r in rows
        ]

    async def actions(self, tenant_id: uuid.UUID) -> list[str]:
        return [e.action for e in await self.events(tenant_id)]

    async def run_row(self, run_id: uuid.UUID) -> asyncpg.Record:
        rows = await self.rows("SELECT * FROM sync_runs WHERE id = $1", run_id)
        assert len(rows) == 1
        return rows[0]

    async def item_status(self, item_id: uuid.UUID) -> str:
        return str(await self.value("SELECT status FROM request_items WHERE id = $1", item_id))


@dataclass(frozen=True)
class World:
    tenant_id: uuid.UUID
    engagement_id: uuid.UUID
    entity_id: uuid.UUID
    item_id: uuid.UUID
    connection_id: uuid.UUID
    requester: Person
    directory: Path

    def write_fixture(self) -> Path:
        return write_trial_balance(
            self.directory,
            self.connection_id,
            TB,
            period_start=ENTITY.period_start,
            entity_name=ENTITY_NAME,
        )

    def write_document(self, change: Callable[[dict[str, object]], None]) -> bytes:
        document = trial_balance_document(
            TB, period_start=ENTITY.period_start, entity_name=ENTITY_NAME
        )
        change(document)
        content = json.dumps(document).encode()
        write_raw(self.directory, self.connection_id, PERIOD, content)
        return content


@pytest.fixture
def seed(migrated_db: Migrated) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture
def fake_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    directory = tmp_path / "fake-connector"
    directory.mkdir()
    monkeypatch.setenv("ABACUS_FAKE_CONNECTOR_DIR", str(directory))
    settings.cache_clear()
    yield directory
    monkeypatch.undo()
    settings.cache_clear()


@pytest.fixture
async def world(seed: Seeder, fake_dir: Path) -> World:
    tenant_id = await seed.firm()
    requester = await seed.person(tenant_id)
    entity_id = await seed.entity(tenant_id)
    engagement_id = await seed.engagement(tenant_id, entity_id, requester.user_id)
    await seed.member(engagement_id, requester, "staff")
    item_id = await seed.item(tenant_id, engagement_id, requester.user_id)
    connection_id = await seed.connection(tenant_id, entity_id)
    made = World(tenant_id, engagement_id, entity_id, item_id, connection_id, requester, fake_dir)
    made.write_fixture()
    return made


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch, fake_dir: Path
) -> AsyncIterator[None]:
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
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(bucket_client, BUCKET)
    yield bucket_client
    storage.reset_storage()
    reset_key_service()


# --- helpers -------------------------------------------------------------------------------------


async def _begin(
    world: World,
    *,
    ctx: AuthContext | None = None,
    item_id: uuid.UUID | None = None,
    period: Period = PERIOD,
    engagement_id: uuid.UUID | None = None,
) -> StartedRun:
    return await start_retrieval(
        ctx or world.requester.context(),
        engagement_id=engagement_id or world.engagement_id,
        request_item_id=item_id or world.item_id,
        period=period,
    )


async def _start(
    world: World,
    *,
    ctx: AuthContext | None = None,
    item_id: uuid.UUID | None = None,
    period: Period = PERIOD,
    engagement_id: uuid.UUID | None = None,
) -> uuid.UUID:
    return (
        await _begin(world, ctx=ctx, item_id=item_id, period=period, engagement_id=engagement_id)
    ).run_id


async def _started(world: World) -> tuple[uuid.UUID, SystemContext]:
    run_id = await _start(world)
    return run_id, await load_system_context(world.tenant_id, run_id)


async def _succeeded(world: World) -> tuple[uuid.UUID, SystemContext, RunResult]:
    run_id, system = await _started(world)
    return run_id, system, await run_pipeline(system)


def _fixture_files(world: World) -> list[Path]:
    return sorted((world.directory / str(world.connection_id)).iterdir())


def _raw_bytes(world: World) -> bytes:
    [path] = _fixture_files(world)
    return path.read_bytes()


async def _failure(awaitable: Awaitable[object]) -> RunFailed:
    with pytest.raises(RunFailed) as raised:
        await awaitable
    return raised.value


# --- start_retrieval -----------------------------------------------------------------------------


async def test_ac9_start_retrieval_returns_the_id_of_a_running_run(
    seed: Seeder, world: World
) -> None:
    started = await _begin(world)
    assert isinstance(started, StartedRun)
    assert started.created is True
    run_id = started.run_id
    assert isinstance(run_id, uuid.UUID)
    row = await seed.run_row(run_id)
    assert row["status"] == "running"
    assert row["finished_at"] is None
    assert row["failure_code"] is None
    assert row["tenant_id"] == world.tenant_id
    assert row["engagement_id"] == world.engagement_id
    assert row["request_item_id"] == world.item_id
    assert row["client_entity_id"] == world.entity_id
    assert row["connection_id"] == world.connection_id
    assert row["dataset"] == "trial_balance"
    assert (row["period_start"], row["period_end"]) == (PERIOD.start, PERIOD.end)
    assert row["started_by"] == str(world.requester.user_id)
    for column in ("raw_storage_key", "raw_fingerprint", "snapshot_id", "evidence_version_id"):
        assert row[column] is None


async def test_ac9_start_retrieval_records_sync_run_started_for_the_human(
    seed: Seeder, world: World
) -> None:
    run_id = await _start(world)
    [event] = await seed.events(world.tenant_id)
    assert event.action == "sync_run.started"
    assert (event.actor_kind, event.actor_id) == ("human", str(world.requester.user_id))
    assert event.after["user_id"] == str(world.requester.user_id)
    assert event.after["request_item_id"] == str(world.item_id)
    target = await seed.value(
        "SELECT target_id FROM audit_events WHERE tenant_id = $1", world.tenant_id
    )
    assert target == str(run_id)


@pytest.mark.parametrize("role", ["engagement_partner", "manager", "senior", "staff"])
async def test_ac9_every_role_with_evidence_upload_may_start_a_retrieval(
    seed: Seeder, world: World, role: Role
) -> None:
    person = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, person, role)
    assert await _start(world, ctx=person.context())


async def test_ac20_a_reviewer_may_not_start_a_retrieval_and_nothing_is_written(
    seed: Seeder, world: World
) -> None:
    reviewer = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, reviewer, "reviewer")
    with pytest.raises(Forbidden):
        await _start(world, ctx=reviewer.context())
    assert await seed.count("sync_runs", world.tenant_id) == 0
    assert await seed.count("audit_events", world.tenant_id) == 0


async def test_ac20_someone_with_no_relationship_to_the_engagement_is_forbidden(
    seed: Seeder, world: World
) -> None:
    stranger = await seed.person(world.tenant_id)
    with pytest.raises(Forbidden):
        await _start(world, ctx=stranger.context())
    assert await seed.count("sync_runs", world.tenant_id) == 0


async def test_ac20_an_archived_engagement_takes_no_retrieval(seed: Seeder, world: World) -> None:
    await seed.run("UPDATE engagements SET status = 'archived' WHERE id = $1", world.engagement_id)
    with pytest.raises(Forbidden):
        await _start(world)
    assert await seed.count("sync_runs", world.tenant_id) == 0


async def test_ac20_an_unknown_engagement_is_not_found(seed: Seeder, world: World) -> None:
    with pytest.raises(NotFound):
        await _start(world, engagement_id=uuid.uuid4())
    assert await seed.count("sync_runs", world.tenant_id) == 0


async def test_ac20_another_firms_engagement_is_not_found(seed: Seeder, world: World) -> None:
    other = await seed.firm()
    person = await seed.person(other)
    entity = await seed.entity(other)
    engagement = await seed.engagement(other, entity, person.user_id)
    await seed.member(engagement, person, "staff")
    with pytest.raises(NotFound):
        await _start(world, engagement_id=engagement)
    assert await seed.count("sync_runs", other) == 0


async def test_ac20_an_unknown_request_item_is_not_found_and_nothing_is_written(
    seed: Seeder, world: World
) -> None:
    with pytest.raises(NotFound):
        await _start(world, item_id=uuid.uuid4())
    assert await seed.count("sync_runs", world.tenant_id) == 0
    assert await seed.count("audit_events", world.tenant_id) == 0


async def test_ac20_an_item_of_another_engagement_is_not_found_and_nothing_is_written(
    seed: Seeder, world: World
) -> None:
    other_engagement = await seed.engagement(
        world.tenant_id, world.entity_id, world.requester.user_id
    )
    other_item = await seed.item(world.tenant_id, other_engagement, world.requester.user_id)
    with pytest.raises(NotFound):
        await _start(world, item_id=other_item)
    assert await seed.count("sync_runs", world.tenant_id) == 0
    assert await seed.count("audit_events", world.tenant_id) == 0


async def test_ac20_another_firms_request_item_is_not_found(seed: Seeder, world: World) -> None:
    other = await seed.firm()
    person = await seed.person(other)
    entity = await seed.entity(other)
    engagement = await seed.engagement(other, entity, person.user_id)
    foreign_item = await seed.item(other, engagement, person.user_id)
    with pytest.raises(NotFound):
        await _start(world, item_id=foreign_item)
    assert await seed.count("sync_runs", other) == 0


@pytest.mark.parametrize("status", ["ready_for_review", "needs_revision"])
async def test_ac20_an_item_past_receipt_is_not_fulfillable(
    seed: Seeder, world: World, status: str
) -> None:
    await seed.run("UPDATE request_items SET status = $2 WHERE id = $1", world.item_id, status)
    with pytest.raises(ItemNotFulfillable):
        await _start(world)
    assert await seed.count("sync_runs", world.tenant_id) == 0


async def test_ac20_a_received_item_may_be_retrieved_again(seed: Seeder, world: World) -> None:
    await seed.run("UPDATE request_items SET status = 'received' WHERE id = $1", world.item_id)
    assert await _start(world)


@pytest.mark.parametrize("state", ["revoked", "expired", "other_entity", "none"])
async def test_ac20_without_an_active_unexpired_connection_for_the_entity_there_is_no_run(
    seed: Seeder, world: World, state: str
) -> None:
    if state == "revoked":
        await seed.run(
            "UPDATE connections SET status = 'revoked' WHERE id = $1", world.connection_id
        )
    elif state == "expired":
        await seed.run(
            "UPDATE connections SET expires_at = now() - interval '1 hour' WHERE id = $1",
            world.connection_id,
        )
    elif state == "other_entity":
        await seed.run(
            "UPDATE connections SET status = 'revoked' WHERE id = $1", world.connection_id
        )
        await seed.connection(world.tenant_id, await seed.entity(world.tenant_id))
    else:
        await seed.run(
            "UPDATE connections SET status = 'revoked' WHERE id = $1", world.connection_id
        )
    with pytest.raises(NoConnection):
        await _start(world)
    assert await seed.count("sync_runs", world.tenant_id) == 0
    assert await seed.count("audit_events", world.tenant_id) == 0


async def test_ac9_a_connection_that_expires_later_counts(seed: Seeder, world: World) -> None:
    await seed.run(
        "UPDATE connections SET expires_at = now() + interval '1 day' WHERE id = $1",
        world.connection_id,
    )
    assert await _start(world)


async def test_ac9_triggering_again_while_running_returns_the_same_run(
    seed: Seeder, world: World
) -> None:
    started = await _begin(world)
    repeated = await _begin(world)
    assert started.created is True
    assert repeated.created is False
    first, second = started.run_id, repeated.run_id
    assert second == first
    assert await seed.count("sync_runs", world.tenant_id) == 1
    assert await seed.actions(world.tenant_id) == ["sync_run.started", "sync_run.requested_again"]
    again = (await seed.events(world.tenant_id))[1]
    assert again.after["user_id"] == str(world.requester.user_id)


async def test_ac9_triggering_again_by_someone_else_records_who_asked(
    seed: Seeder, world: World
) -> None:
    other = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, other, "manager")
    first = await _start(world)
    assert await _start(world, ctx=other.context()) == first
    again = (await seed.events(world.tenant_id))[1]
    assert (again.action, again.actor_id) == ("sync_run.requested_again", str(other.user_id))
    assert again.after["user_id"] == str(other.user_id)
    assert (await seed.run_row(first))["started_by"] == str(world.requester.user_id)


async def test_ac9_triggering_again_after_success_returns_the_same_run(
    seed: Seeder, world: World
) -> None:
    run_id, _, _ = await _succeeded(world)
    repeated = await _begin(world)
    assert repeated.run_id == run_id
    assert repeated.created is False
    assert await seed.count("sync_runs", world.tenant_id) == 1
    assert (await seed.actions(world.tenant_id))[-1] == "sync_run.requested_again"


async def test_ac9_a_different_period_or_item_is_a_different_run(
    seed: Seeder, world: World
) -> None:
    first = await _start(world)
    other_period = await _start(world, period=Period(PERIOD.start, PERIOD.end - timedelta(days=1)))
    other_item = await _start(
        world,
        item_id=await seed.item(world.tenant_id, world.engagement_id, world.requester.user_id),
    )
    assert len({first, other_period, other_item}) == 3
    assert await seed.count("sync_runs", world.tenant_id) == 3


async def test_ac9_concurrent_triggers_share_one_run(seed: Seeder, world: World) -> None:
    ids = await asyncio.gather(*[_start(world) for _ in range(4)])
    assert len(set(ids)) == 1
    assert await seed.count("sync_runs", world.tenant_id) == 1
    actions = await seed.actions(world.tenant_id)
    assert actions.count("sync_run.started") == 1
    assert actions.count("sync_run.requested_again") == 3


async def test_ac11_after_a_failed_run_a_new_trigger_starts_a_new_run(
    seed: Seeder, world: World
) -> None:
    world.write_document(lambda d: d.update(control_totals={"debit": "1.00", "credit": "1.00"}))
    first, system = await _started(world)
    await _failure(run_pipeline(system))
    assert (await seed.run_row(first))["status"] == "failed_validation"
    world.write_fixture()
    again = await _begin(world)
    assert again.created is True
    second = again.run_id
    assert second != first
    assert await seed.count("sync_runs", world.tenant_id) == 2


# --- load_system_context -------------------------------------------------------------------------


async def test_ac20_load_system_context_takes_everything_from_the_run_row(
    world: World,
) -> None:
    run_id, system = await _started(world)
    assert isinstance(system, SystemContext)
    assert system.run_id == run_id
    assert system.tenant_id == world.tenant_id
    assert system.engagement_id == world.engagement_id
    assert system.on_behalf_of == world.requester.user_id
    assert system.tenant == TenantContext(world.tenant_id, "system", f"run:{run_id}")


async def test_ac20_load_system_context_for_a_missing_run_is_not_found(world: World) -> None:
    with pytest.raises(NotFound):
        await load_system_context(world.tenant_id, uuid.uuid4())


async def test_ac20_load_system_context_cannot_cross_tenants(seed: Seeder, world: World) -> None:
    run_id = await _start(world)
    with pytest.raises(NotFound):
        await load_system_context(await seed.firm(), run_id)


@pytest.mark.parametrize("how", ["succeeded", "failed", "failed_validation"])
async def test_ac20_load_system_context_refuses_a_finished_run(
    seed: Seeder, world: World, how: str
) -> None:
    if how == "succeeded":
        run_id, _, _ = await _succeeded(world)
    else:
        run_id, system = await _started(world)
        await fail_run(system, how, "test_reason")
    with pytest.raises(RunNotRunning) as raised:
        await load_system_context(world.tenant_id, run_id)
    assert raised.value.args[0] == how


# --- AC-9 and AC-10: the pipeline ----------------------------------------------------------------


async def test_ac9_the_raw_payload_is_stored_unaltered_under_its_fingerprint_encrypted(
    seed: Seeder, world: World, evidence_storage: S3Client
) -> None:
    provider_bytes = _raw_bytes(world)
    run_id, system = await _started(world)
    stored = await pull_raw(system)
    fingerprint = hashlib.sha256(provider_bytes).hexdigest()
    assert isinstance(stored, StoredObject)
    assert stored.fingerprint == fingerprint
    assert stored.size == len(provider_bytes)
    assert stored.key == f"tenants/{world.tenant_id}/sha256/{fingerprint}"
    assert await read_content(system.tenant, stored) == provider_bytes
    sealed = evidence_storage.get_object(
        Bucket=BUCKET, Key=stored.key, VersionId=stored.version_id
    )["Body"].read()
    assert sealed != provider_bytes
    for line in TB.lines[:5]:
        assert line.account_name.encode() not in sealed
    row = await seed.run_row(run_id)
    assert (row["raw_storage_key"], row["raw_version_id"]) == (stored.key, stored.version_id)
    assert (row["raw_fingerprint"], row["raw_size_bytes"]) == (fingerprint, len(provider_bytes))
    assert row["source"] == "fake"
    assert row["raw_pulled_at"] is not None
    assert row["status"] == "running"
    assert row["snapshot_id"] is None
    assert await seed.actions(world.tenant_id) == ["sync_run.started", "sync_run.raw_stored"]


async def test_ac9_the_stages_run_one_by_one_and_record_in_order(
    seed: Seeder, world: World
) -> None:
    run_id, system = await _started(world)
    await pull_raw(system)
    assert await normalise_raw(system) == len(TB.lines)
    assert await validate_run(system) is None
    assert (await seed.run_row(run_id))["snapshot_id"] is None
    snapshot_id = await snapshot(system)
    row = await seed.run_row(run_id)
    assert row["snapshot_id"] == snapshot_id
    assert (row["status"], row["evidence_version_id"]) == ("running", None)
    version_id = await render(system)
    row = await seed.run_row(run_id)
    assert (row["status"], row["evidence_version_id"]) == ("succeeded", version_id)
    assert row["finished_at"] is not None
    assert await seed.actions(world.tenant_id) == EXPECTED_EVENTS


async def test_ac10_the_pipeline_makes_one_snapshot_one_version_one_fulfilment(
    seed: Seeder, world: World
) -> None:
    run_id, _, result = await _succeeded(world)
    assert result == RunResult(run_id, result.snapshot_id, result.evidence_version_id)
    row = await seed.run_row(run_id)
    assert row["status"] == "succeeded"
    assert row["failure_code"] is None
    assert (row["snapshot_id"], row["evidence_version_id"]) == (
        result.snapshot_id,
        result.evidence_version_id,
    )
    assert row["raw_fingerprint"] == hashlib.sha256(_raw_bytes(world)).hexdigest()
    for table in ("ledger_snapshots", "evidence_items", "evidence_versions", "fulfilments"):
        assert await seed.count(table, world.tenant_id) == 1
    assert await seed.count("trial_balance_lines", world.tenant_id) == len(TB.lines)
    assert await seed.item_status(world.item_id) == "received"


async def test_ac10_the_snapshot_holds_the_validated_trial_balance(
    seed: Seeder, world: World
) -> None:
    run_id, _, result = await _succeeded(world)
    [snap] = await seed.rows("SELECT * FROM ledger_snapshots WHERE id = $1", result.snapshot_id)
    assert snap["client_entity_id"] == world.entity_id
    assert (snap["period_start"], snap["period_end"]) == (PERIOD.start, PERIOD.end)
    assert snap["line_count"] == len(TB.lines)
    assert snap["total_debit"] == TB.total_debits
    assert snap["total_credit"] == TB.total_credits
    assert snap["source"] == "fake"
    assert snap["raw_fingerprint"] == (await seed.run_row(run_id))["raw_fingerprint"]
    lines = await seed.rows(
        "SELECT * FROM trial_balance_lines WHERE snapshot_id = $1 ORDER BY account_code",
        result.snapshot_id,
    )
    assert [(r["account_code"], r["account_name"], r["debit"], r["credit"]) for r in lines] == [
        (line.account_code, line.account_name, line.debit, line.credit)
        for line in sorted(TB.lines, key=lambda line: line.account_code)
    ]
    assert all(r["source_ref"] == f"acct-{r['account_code']}" for r in lines)


async def test_ac10_the_evidence_version_carries_its_provenance(
    seed: Seeder, world: World
) -> None:
    run_id, _, result = await _succeeded(world)
    [version] = await seed.rows(
        "SELECT * FROM evidence_versions WHERE id = $1", result.evidence_version_id
    )
    snap = await seed.rows("SELECT * FROM ledger_snapshots WHERE id = $1", result.snapshot_id)
    assert version["method"] == "retrieved"
    assert version["media_type"] == XLSX_MEDIA_TYPE
    assert version["source"] == "fake"
    assert version["snapshot_id"] == result.snapshot_id
    assert version["client_entity_id"] == world.entity_id
    assert version["engagement_id"] == world.engagement_id
    assert (version["period_start"], version["period_end"]) == (PERIOD.start, PERIOD.end)
    assert version["pulled_at"] == snap[0]["pulled_at"]
    assert version["pulled_at"] == (await seed.run_row(run_id))["raw_pulled_at"]
    assert version["version_no"] == 1
    assert version["storage_key"] == (f"tenants/{world.tenant_id}/sha256/{version['fingerprint']}")
    assert version["fingerprint"] != (await seed.run_row(run_id))["raw_fingerprint"]
    stored = StoredObject(
        version["storage_key"],
        version["storage_version_id"],
        version["fingerprint"],
        version["size_bytes"],
    )
    workbook = await read_content(TenantContext(world.tenant_id, "system", "test-reader"), stored)
    assert workbook.startswith(b"PK")
    [item] = await seed.rows(
        "SELECT * FROM evidence_items WHERE id = $1", version["evidence_item_id"]
    )
    assert (item["created_by_kind"], item["created_by_id"]) == ("system", f"run:{run_id}")


async def test_ac10_the_item_is_fulfilled_by_rule(seed: Seeder, world: World) -> None:
    run_id, _, result = await _succeeded(world)
    [fulfilment] = await seed.rows(
        "SELECT * FROM fulfilments WHERE tenant_id = $1", world.tenant_id
    )
    assert fulfilment["created_by_kind"] == "rule"
    assert fulfilment["created_by_id"] == f"run:{run_id}"
    assert fulfilment["request_item_id"] == world.item_id
    assert fulfilment["evidence_version_id"] == result.evidence_version_id
    assert fulfilment["engagement_id"] == world.engagement_id
    assert await seed.item_status(world.item_id) == "received"


async def test_ac10_audit_events_are_in_order_with_the_right_actors(
    seed: Seeder, world: World
) -> None:
    run_id, _, result = await _succeeded(world)
    events = await seed.events(world.tenant_id)
    assert [e.action for e in events] == EXPECTED_EVENTS
    assert (events[0].actor_kind, events[0].actor_id) == ("human", str(world.requester.user_id))
    for event in events[1:]:
        assert (event.actor_kind, event.actor_id) == ("system", f"run:{run_id}")
    by_action = {e.action: e for e in events}
    user = str(world.requester.user_id)
    row = await seed.run_row(run_id)
    assert by_action["sync_run.raw_stored"].after["raw_fingerprint"] == row["raw_fingerprint"]
    assert by_action["sync_run.raw_stored"].after["on_behalf_of"] == user
    assert by_action["sync_run.snapshot_linked"].after["snapshot_id"] == str(result.snapshot_id)
    assert by_action["sync_run.snapshot_linked"].after["on_behalf_of"] == user
    assert by_action["sync_run.succeeded"].after["on_behalf_of"] == user
    assert by_action["sync_run.succeeded"].after["evidence_version_id"] == str(
        result.evidence_version_id
    )


async def test_ac10_the_outbox_announces_the_new_version(seed: Seeder, world: World) -> None:
    await _succeeded(world)
    types = [
        str(r["event_type"])
        for r in await seed.rows(
            "SELECT event_type FROM outbox WHERE tenant_id = $1 ORDER BY seq", world.tenant_id
        )
    ]
    assert types == ["evidence_version.created"]


# --- idempotency and quiet repeats (§12) -----------------------------------------------------


async def test_ac20_every_stage_repeated_after_success_returns_the_recorded_result_quietly(
    seed: Seeder, world: World
) -> None:
    run_id, system, result = await _succeeded(world)
    before = await seed.count("audit_events", world.tenant_id)
    stored = await pull_raw(system)
    assert stored.key == (await seed.run_row(run_id))["raw_storage_key"]
    assert await normalise_raw(system) == len(TB.lines)
    assert await validate_run(system) is None
    assert await snapshot(system) == result.snapshot_id
    assert await render(system) == result.evidence_version_id
    assert await run_pipeline(system) == result
    assert await seed.count("audit_events", world.tenant_id) == before
    assert await seed.actions(world.tenant_id) == EXPECTED_EVENTS
    for table in ("ledger_snapshots", "evidence_versions", "fulfilments", "outbox"):
        assert await seed.count(table, world.tenant_id) == 1


async def test_ac20_pull_raw_pulls_at_most_once_per_run(seed: Seeder, world: World) -> None:
    run_id, system = await _started(world)
    first = await pull_raw(system)
    for path in _fixture_files(world):
        path.unlink()  # the provider no longer has it: a second pull would be no_data
    assert await pull_raw(system) == first
    assert (await seed.actions(world.tenant_id)).count("sync_run.raw_stored") == 1
    assert (await seed.run_row(run_id))["status"] == "running"


async def test_ac20_concurrent_pull_raw_keeps_the_first_recorded_payload(
    seed: Seeder, world: World
) -> None:
    _, system = await _started(world)
    results = await asyncio.gather(*[pull_raw(system) for _ in range(4)])
    assert len({(r.key, r.version_id) for r in results}) == 1
    assert (await seed.actions(world.tenant_id)).count("sync_run.raw_stored") == 1


async def test_ac20_concurrent_render_makes_one_version_and_one_fulfilment(
    seed: Seeder, world: World
) -> None:
    _, system = await _started(world)
    await pull_raw(system)
    await snapshot(system)
    versions = await asyncio.gather(*[render(system) for _ in range(4)])
    assert len(set(versions)) == 1
    assert await seed.count("evidence_versions", world.tenant_id) == 1
    assert await seed.count("fulfilments", world.tenant_id) == 1
    actions = await seed.actions(world.tenant_id)
    assert actions.count("sync_run.succeeded") == 1
    assert actions.count("request_item.received") == 1


async def test_ac20_a_snapshot_repeated_mid_run_is_quiet(seed: Seeder, world: World) -> None:
    _, system = await _started(world)
    await pull_raw(system)
    first = await snapshot(system)
    assert await snapshot(system) == first
    assert await validate_run(system) is None
    actions = await seed.actions(world.tenant_id)
    assert actions.count("sync_run.snapshot_linked") == 1
    assert actions.count("ledger_snapshot.created") == 1


async def test_ac20_retriggering_and_rerunning_gives_the_same_snapshot_and_version(
    seed: Seeder, world: World
) -> None:
    run_id, _, _ = await _succeeded(world)
    again = await _start(world)
    assert again == run_id
    for table in ("sync_runs", "ledger_snapshots", "evidence_versions", "fulfilments"):
        assert await seed.count(table, world.tenant_id) == 1


async def test_ac20_a_second_item_for_the_same_pull_shares_the_snapshot_not_the_fulfilment(
    seed: Seeder, world: World
) -> None:
    _, _, first = await _succeeded(world)
    second_item = await seed.item(world.tenant_id, world.engagement_id, world.requester.user_id)
    run2 = await _start(world, item_id=second_item)
    second = await run_pipeline(await load_system_context(world.tenant_id, run2))
    assert second.snapshot_id == first.snapshot_id
    assert await seed.count("ledger_snapshots", world.tenant_id) == 1
    assert (await seed.actions(world.tenant_id)).count("ledger_snapshot.created") == 1
    assert await seed.count("fulfilments", world.tenant_id) == 2
    assert await seed.item_status(second_item) == "received"
    assert await seed.item_status(world.item_id) == "received"


# --- AC-11: validation failures ------------------------------------------------------------------


def _bad_totals(document: dict[str, object]) -> None:
    document["control_totals"] = {"debit": "1.00", "credit": "1.00"}


def _unbalanced(document: dict[str, object]) -> None:
    lines = cast(list[dict[str, object]], document["lines"])
    lines[0]["debit"] = str(Decimal(str(lines[0]["debit"])) + Decimal("5.00"))
    totals = cast(dict[str, str], document["control_totals"])
    totals["debit"] = str(Decimal(totals["debit"]) + Decimal("5.00"))


def _wrong_period(document: dict[str, object]) -> None:
    cast(dict[str, str], document["period"])["end"] = "2025-06-30"


def _eur(document: dict[str, object]) -> None:
    document["currency"] = "EUR"


def _duplicate_account(document: dict[str, object]) -> None:
    lines = cast(list[dict[str, object]], document["lines"])
    lines[1]["code"] = str(lines[0]["code"]).lower()
    lines[0]["code"] = str(lines[0]["code"]).upper()


def _duplicate_ref(document: dict[str, object]) -> None:
    lines = cast(list[dict[str, object]], document["lines"])
    lines[1]["id"] = lines[0]["id"]


def _empty(document: dict[str, object]) -> None:
    document["lines"] = []
    document["control_totals"] = {"debit": "0.00", "credit": "0.00"}


def _zero(document: dict[str, object]) -> None:
    lines = cast(list[dict[str, object]], document["lines"])
    for line in lines:
        line["debit"] = "0.00"
        line["credit"] = "0.00"
    document["control_totals"] = {"debit": "0.00", "credit": "0.00"}


VALIDATION_CASES: list[tuple[str, Callable[[dict[str, object]], None]]] = [
    ("control_totals_mismatch", _bad_totals),
    ("unbalanced", _unbalanced),
    ("period_mismatch", _wrong_period),
    ("unsupported_currency", _eur),
    ("duplicate_account", _duplicate_account),
    ("duplicate_source_ref", _duplicate_ref),
    ("empty", _empty),
    ("zero_total", _zero),
]


@pytest.mark.parametrize(
    ("code", "change"), VALIDATION_CASES, ids=[c for c, _ in VALIDATION_CASES]
)
async def test_ac11_a_failed_validation_ends_the_run_with_no_snapshot_or_evidence(
    seed: Seeder, world: World, code: str, change: Callable[[dict[str, object]], None]
) -> None:
    world.write_document(change)
    run_id, system = await _started(world)
    failed = await _failure(run_pipeline(system))
    assert (failed.status, failed.code) == ("failed_validation", code)
    row = await seed.run_row(run_id)
    assert (row["status"], row["failure_code"]) == ("failed_validation", code)
    assert row["finished_at"] is not None
    assert row["snapshot_id"] is None
    assert row["evidence_version_id"] is None
    assert row["raw_fingerprint"] is not None  # the raw payload is kept: it is the evidence of why
    for table in ("ledger_snapshots", "trial_balance_lines", "evidence_versions", "fulfilments"):
        assert await seed.count(table, world.tenant_id) == 0
    assert await seed.item_status(world.item_id) == "open"
    assert await seed.actions(world.tenant_id) == [
        "sync_run.started",
        "sync_run.raw_stored",
        "sync_run.failed",
    ]
    failure_event = (await seed.events(world.tenant_id))[-1]
    assert (failure_event.actor_kind, failure_event.actor_id) == ("system", f"run:{run_id}")


async def test_ac11_validate_run_alone_marks_the_run_and_every_later_stage_refuses(
    seed: Seeder, world: World
) -> None:
    world.write_document(_unbalanced)
    run_id, system = await _started(world)
    await pull_raw(system)
    assert await normalise_raw(system) == len(TB.lines)
    failed = await _failure(validate_run(system))
    assert (failed.status, failed.code) == ("failed_validation", "unbalanced")
    for stage in (pull_raw, normalise_raw, validate_run, snapshot, render):
        again = await _failure(stage(system))
        assert (again.status, again.code) == ("failed_validation", "unbalanced")
    assert await seed.count("ledger_snapshots", world.tenant_id) == 0
    assert (await seed.actions(world.tenant_id)).count("sync_run.failed") == 1
    assert (await seed.run_row(run_id))["status"] == "failed_validation"


async def test_ac11_snapshot_never_stores_an_unvalidated_trial_balance(
    seed: Seeder, world: World
) -> None:
    world.write_document(_unbalanced)
    _, system = await _started(world)
    await pull_raw(system)
    failed = await _failure(snapshot(system))  # validate_run skipped on purpose
    assert (failed.status, failed.code) == ("failed_validation", "unbalanced")
    assert await seed.count("ledger_snapshots", world.tenant_id) == 0


# --- failures --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"not json at all", "malformed_payload"),
        (b'{"dataset": "general_ledger"}', "malformed_payload"),
        (b"\xff\xfe\x00", "malformed_payload"),
        (b"[]", "malformed_payload"),
    ],
)
async def test_ac11_a_malformed_payload_fails_the_run_after_the_raw_is_kept(
    seed: Seeder, world: World, content: bytes, code: str
) -> None:
    write_raw(world.directory, world.connection_id, PERIOD, content)
    run_id, system = await _started(world)
    failed = await _failure(run_pipeline(system))
    assert (failed.status, failed.code) == ("failed", code)
    row = await seed.run_row(run_id)
    assert (row["status"], row["failure_code"]) == ("failed", code)
    assert row["raw_fingerprint"] == hashlib.sha256(content).hexdigest()
    assert await seed.count("ledger_snapshots", world.tenant_id) == 0
    assert await seed.item_status(world.item_id) == "open"


async def test_ac11_an_unreadable_amount_fails_the_run_as_invalid_amount(
    seed: Seeder, world: World
) -> None:
    def bad(document: dict[str, object]) -> None:
        cast(list[dict[str, object]], document["lines"])[0]["debit"] = "1e3"

    world.write_document(bad)
    _, system = await _started(world)
    failed = await _failure(run_pipeline(system))
    assert (failed.status, failed.code) == ("failed", "invalid_amount")


async def test_ac11_a_missing_fixture_fails_the_run_as_no_data_and_stores_nothing(
    seed: Seeder, world: World
) -> None:
    for path in _fixture_files(world):
        path.unlink()
    run_id, system = await _started(world)
    failed = await _failure(run_pipeline(system))
    assert (failed.status, failed.code) == ("failed", "no_data")
    row = await seed.run_row(run_id)
    assert (row["status"], row["failure_code"], row["raw_fingerprint"]) == (
        "failed",
        "no_data",
        None,
    )
    assert await seed.actions(world.tenant_id) == ["sync_run.started", "sync_run.failed"]


async def test_ac11_a_provider_fault_is_unavailable_from_pull_raw_and_failed_from_the_pipeline(
    seed: Seeder, world: World
) -> None:
    write_fault(world.directory, world.connection_id, PERIOD)
    run_id, system = await _started(world)
    with pytest.raises(Unavailable):
        await pull_raw(system)
    row = await seed.run_row(run_id)
    assert row["status"] == "running"  # retryable: the run is not failed by a single outage
    failed = await _failure(run_pipeline(system))
    assert (failed.status, failed.code) == ("failed", "provider_unavailable")
    assert (await seed.run_row(run_id))["failure_code"] == "provider_unavailable"


async def test_ac11_a_revoked_connection_fails_the_run_as_connection_inactive(
    seed: Seeder, world: World
) -> None:
    run_id, system = await _started(world)
    await seed.run("UPDATE connections SET status = 'revoked' WHERE id = $1", world.connection_id)
    failed = await _failure(run_pipeline(system))
    assert (failed.status, failed.code) == ("failed", "connection_inactive")
    row = await seed.run_row(run_id)
    assert (row["status"], row["raw_fingerprint"]) == ("failed", None)


async def test_ac11_a_raw_object_that_cannot_be_read_back_fails_the_run_as_unprocessable(
    seed: Seeder, world: World, evidence_storage: S3Client
) -> None:
    run_id, system = await _started(world)
    stored = await pull_raw(system)
    evidence_storage.delete_object(
        Bucket=BUCKET, Key=stored.key, VersionId=stored.version_id, BypassGovernanceRetention=True
    )
    failed = await _failure(normalise_raw(system))
    assert (failed.status, failed.code) == ("failed", "unprocessable")
    assert (await seed.run_row(run_id))["failure_code"] == "unprocessable"


@pytest.mark.parametrize(
    "stage", ["pull_raw", "normalise_raw", "validate_run", "snapshot", "render"]
)
async def test_ac20_every_stage_refuses_a_failed_run(
    seed: Seeder, world: World, stage: str
) -> None:
    stages = {
        "pull_raw": pull_raw,
        "normalise_raw": normalise_raw,
        "validate_run": validate_run,
        "snapshot": snapshot,
        "render": render,
    }
    _, system = await _started(world)
    await fail_run(system, "failed", "test_reason")
    failed = await _failure(stages[stage](system))
    assert (failed.status, failed.code) == ("failed", "test_reason")


# --- fail_run ------------------------------------------------------------------------------------


async def test_ac20_fail_run_ends_a_running_run_and_records_it_once(
    seed: Seeder, world: World
) -> None:
    run_id, system = await _started(world)
    returned = await fail_run(system, "failed", "test_reason")
    assert isinstance(returned, RunFailed)
    assert (returned.status, returned.code) == ("failed", "test_reason")
    row = await seed.run_row(run_id)
    assert (row["status"], row["failure_code"]) == ("failed", "test_reason")
    assert row["finished_at"] is not None
    assert await seed.actions(world.tenant_id) == ["sync_run.started", "sync_run.failed"]
    event = (await seed.events(world.tenant_id))[-1]
    assert (event.actor_kind, event.actor_id) == ("system", f"run:{run_id}")
    assert await seed.item_status(world.item_id) == "open"


async def test_ac20_fail_run_on_a_finished_run_changes_and_records_nothing(
    seed: Seeder, world: World
) -> None:
    run_id, system = await _started(world)
    await fail_run(system, "failed_validation", "unbalanced")
    before = await seed.rows("SELECT * FROM sync_runs WHERE id = $1", run_id)
    events = await seed.count("audit_events", world.tenant_id)
    again = await fail_run(system, "failed", "something_else")
    assert (again.status, again.code) == ("failed_validation", "unbalanced")
    assert await seed.rows("SELECT * FROM sync_runs WHERE id = $1", run_id) == before
    assert await seed.count("audit_events", world.tenant_id) == events


async def test_ac20_fail_run_cannot_undo_a_succeeded_run(seed: Seeder, world: World) -> None:
    run_id, system, _ = await _succeeded(world)
    events = await seed.count("audit_events", world.tenant_id)
    returned = await fail_run(system, "failed", "late_failure")
    assert returned.status == "succeeded"
    row = await seed.run_row(run_id)
    assert (row["status"], row["failure_code"]) == ("succeeded", None)
    assert await seed.count("audit_events", world.tenant_id) == events
    assert await seed.item_status(world.item_id) == "received"


# --- the system context confines a stage to its run ------------------------------------------


async def test_ac20_a_context_for_another_engagement_cannot_touch_the_run(
    seed: Seeder, world: World
) -> None:
    run_id, _ = await _started(world)
    elsewhere = system_context_for_run(
        tenant_id=world.tenant_id,
        run_id=run_id,
        engagement_id=uuid.uuid4(),
        on_behalf_of=world.requester.user_id,
    )
    for stage in (pull_raw, normalise_raw, validate_run, snapshot, render):
        with pytest.raises(NotFound):
            await stage(elsewhere)
    assert (await seed.run_row(run_id))["raw_fingerprint"] is None
    assert await seed.actions(world.tenant_id) == ["sync_run.started"]


async def test_ac20_a_context_for_a_run_that_does_not_exist_is_not_found(world: World) -> None:
    ghost = system_context_for_run(
        tenant_id=world.tenant_id,
        run_id=uuid.uuid4(),
        engagement_id=world.engagement_id,
        on_behalf_of=world.requester.user_id,
    )
    with pytest.raises(NotFound):
        await pull_raw(ghost)


async def test_ac20_a_context_in_another_tenant_cannot_see_the_run(
    seed: Seeder, world: World
) -> None:
    run_id, system = await _started(world)
    foreign = system_context_for_run(
        tenant_id=await seed.firm(),
        run_id=run_id,
        engagement_id=system.engagement_id,
        on_behalf_of=world.requester.user_id,
    )
    with pytest.raises(NotFound):
        await pull_raw(foreign)


async def test_ac20_an_archived_engagement_stops_the_platform_too(
    seed: Seeder, world: World
) -> None:
    run_id, system = await _started(world)
    await seed.run("UPDATE engagements SET status = 'archived' WHERE id = $1", world.engagement_id)
    with pytest.raises(Forbidden):
        await pull_raw(system)
    assert (await seed.run_row(run_id))["raw_fingerprint"] is None


async def test_ac20_render_is_refused_for_an_archived_engagement_before_any_write(
    seed: Seeder, world: World
) -> None:
    _, system = await _started(world)
    await pull_raw(system)
    await snapshot(system)
    await seed.run("UPDATE engagements SET status = 'archived' WHERE id = $1", world.engagement_id)
    with pytest.raises(Forbidden):
        await render(system)
    assert await seed.count("evidence_versions", world.tenant_id) == 0
    assert await seed.count("fulfilments", world.tenant_id) == 0
    assert await seed.item_status(world.item_id) == "open"


async def test_ac20_render_before_a_snapshot_is_not_found(world: World) -> None:
    _, system = await _started(world)
    await pull_raw(system)
    with pytest.raises(NotFound):
        await render(system)


async def test_ac20_snapshot_before_the_raw_payload_is_recorded_is_not_found(world: World) -> None:
    _, system = await _started(world)
    with pytest.raises(NotFound):
        await snapshot(system)


# --- fulfil_by_rule ------------------------------------------------------------------------


@dataclass(frozen=True)
class Fulfilling:
    world: World
    version_id: uuid.UUID


@pytest.fixture
async def fulfilling(seed: Seeder, world: World) -> Fulfilling:
    return Fulfilling(world, await seed.evidence_version(world.tenant_id, world.engagement_id))


def _platform(world: World, engagement_id: uuid.UUID | None = None) -> SystemContext:
    return system_context_for_run(
        tenant_id=world.tenant_id,
        run_id=uuid.uuid4(),
        engagement_id=engagement_id or world.engagement_id,
        on_behalf_of=world.requester.user_id,
    )


async def _fulfil(
    ctx: AuthContext | SystemContext,
    item_id: uuid.UUID,
    version_id: uuid.UUID,
    *,
    note: bool = False,
) -> FulfilmentRef:
    async with uow(ctx.tenant) as tx:
        ref = await fulfil_by_rule(
            tx, ctx, request_item_id=item_id, evidence_version_id=version_id
        )
        if note:  # a repeat records nothing itself: the caller records its own event
            tx.record("fulfilment.noted", target=Target("request_item", item_id))
        return ref


async def test_ac10_the_platform_fulfils_an_open_item_by_rule(
    seed: Seeder, fulfilling: Fulfilling
) -> None:
    world, version = fulfilling.world, fulfilling.version_id
    system = _platform(world)
    ref = await _fulfil(system, world.item_id, version)
    assert ref.id is not None
    assert ref.received is True
    [row] = await seed.rows("SELECT * FROM fulfilments WHERE id = $1", ref.id)
    assert (row["created_by_kind"], row["created_by_id"]) == ("rule", str(system.tenant.actor_id))
    assert row["engagement_id"] == world.engagement_id
    assert await seed.item_status(world.item_id) == "received"
    assert await seed.actions(world.tenant_id) == ["fulfilment.created", "request_item.received"]


async def test_ac10_a_person_who_may_propose_fulfils_as_human_not_rule(
    seed: Seeder, fulfilling: Fulfilling
) -> None:
    world, version = fulfilling.world, fulfilling.version_id
    ref = await _fulfil(world.requester.context(), world.item_id, version)
    [row] = await seed.rows("SELECT * FROM fulfilments WHERE id = $1", ref.id)
    assert (row["created_by_kind"], row["created_by_id"]) == (
        "human",
        str(world.requester.user_id),
    )


async def test_ac20_a_reviewer_may_not_fulfil(seed: Seeder, fulfilling: Fulfilling) -> None:
    world, version = fulfilling.world, fulfilling.version_id
    reviewer = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, reviewer, "reviewer")
    with pytest.raises(Forbidden):
        await _fulfil(reviewer.context(), world.item_id, version)
    assert await seed.count("fulfilments", world.tenant_id) == 0
    assert await seed.item_status(world.item_id) == "open"


async def test_ac20_the_platform_may_not_fulfil_for_another_engagement(
    seed: Seeder, fulfilling: Fulfilling
) -> None:
    world, version = fulfilling.world, fulfilling.version_id
    with pytest.raises(Forbidden):
        await _fulfil(_platform(world, uuid.uuid4()), world.item_id, version)
    assert await seed.count("fulfilments", world.tenant_id) == 0


async def test_ac20_an_unknown_item_is_not_found(fulfilling: Fulfilling) -> None:
    with pytest.raises(NotFound):
        await _fulfil(_platform(fulfilling.world), uuid.uuid4(), fulfilling.version_id)


async def test_ac10_fulfilling_again_with_the_same_version_changes_nothing(
    seed: Seeder, fulfilling: Fulfilling
) -> None:
    world, version = fulfilling.world, fulfilling.version_id
    system = _platform(world)
    await _fulfil(system, world.item_id, version)
    again = await _fulfil(system, world.item_id, version, note=True)
    assert again == FulfilmentRef(id=None, received=False)
    assert await seed.count("fulfilments", world.tenant_id) == 1
    actions = await seed.actions(world.tenant_id)
    assert actions.count("fulfilment.created") == 1
    assert actions.count("request_item.received") == 1


async def test_ac10_a_further_version_for_a_received_item_is_a_new_fulfilment_without_a_move(
    seed: Seeder, fulfilling: Fulfilling
) -> None:
    world, version = fulfilling.world, fulfilling.version_id
    system = _platform(world)
    await _fulfil(system, world.item_id, version)
    second = await seed.evidence_version(world.tenant_id, world.engagement_id)
    ref = await _fulfil(system, world.item_id, second)
    assert ref.id is not None
    assert ref.received is False
    assert await seed.count("fulfilments", world.tenant_id) == 2
    assert (await seed.actions(world.tenant_id)).count("request_item.received") == 1


# TASK-019 (SPEC-004 amendment): a sent-back `needs_revision` item takes new evidence; an
# accepted one never does.
@pytest.mark.parametrize("status", ["ready_for_review", "accepted"])
async def test_ac20_an_item_past_receipt_takes_no_fulfilment(
    seed: Seeder, fulfilling: Fulfilling, status: str
) -> None:
    world, version = fulfilling.world, fulfilling.version_id
    await seed.run("UPDATE request_items SET status = $2 WHERE id = $1", world.item_id, status)
    with pytest.raises(ItemNotFulfillable):
        await _fulfil(_platform(world), world.item_id, version)
    assert await seed.count("fulfilments", world.tenant_id) == 0
    assert await seed.item_status(world.item_id) == status


async def test_ac20_evidence_of_another_engagement_cannot_fulfil_the_item(
    seed: Seeder, fulfilling: Fulfilling
) -> None:
    world = fulfilling.world
    other = await seed.engagement(world.tenant_id, world.entity_id, world.requester.user_id)
    foreign_version = await seed.evidence_version(world.tenant_id, other)
    with pytest.raises(DBAPIError):
        await _fulfil(_platform(world), world.item_id, foreign_version)
    assert await seed.count("fulfilments", world.tenant_id) == 0
    assert await seed.item_status(world.item_id) == "open"


async def test_ac20_fulfilling_is_repeatable_to_the_last_detail(
    seed: Seeder, world: World
) -> None:
    run_id, system, result = await _succeeded(world)
    before = await seed.count("audit_events", world.tenant_id)
    again = await _fulfil(system, world.item_id, result.evidence_version_id, note=True)
    assert again == FulfilmentRef(id=None, received=False)
    assert await seed.count("fulfilments", world.tenant_id) == 1
    assert await seed.count("audit_events", world.tenant_id) == before + 1
    assert run_id == system.run_id
