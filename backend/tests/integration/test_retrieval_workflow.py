"""AC-9, AC-10, AC-11, AC-20: the retrieval workflow and its activities against Temporal
(TASK-010b interface contract, "Workflow and activities" and "Worker"; ADR-017).

Rows are seeded as the superuser (`migrated_db.superuser_dsn`) with fresh firms per test. The
worker runs in this process on a task queue unique to this module, and the client uses the
platform payload codec. Provider responses come from `abacus_tools.synthetic.connector_fixtures`.
Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Iterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol, cast

import asyncpg
import pytest
from botocore.exceptions import ClientError
from sqlalchemy.exc import DBAPIError
from temporalio import activity
from temporalio.api.enums.v1 import TaskQueueType
from temporalio.api.taskqueue.v1 import TaskQueue
from temporalio.api.workflowservice.v1 import DescribeTaskQueueRequest
from temporalio.client import Client, WorkflowFailureError, WorkflowHandle
from temporalio.common import WorkflowIDConflictPolicy
from temporalio.exceptions import ApplicationError, CancelledError
from temporalio.testing import ActivityEnvironment
from temporalio.worker import Worker
from types_boto3_s3 import S3Client

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.crypto.payload_codec import ENCODING
from abacus.kernel.db import (
    TenantContext,
    configure_engine,
    configure_relay_engine,
    dispose_engine,
)
from abacus.kernel.dispatch import WORK_CLASSES, queue_for
from abacus.kernel.storage import s3_client
from abacus.kernel.temporal import configure_temporal_client, data_converter
from abacus.modules.connections.api import (
    ACTIVITIES,
    FailInput,
    Period,
    RetrievalInput,
    RetrievalOutcome,
    RetrievalWorkflow,
    StartedRun,
    start_retrieval,
    trigger_retrieval,
    workflow_id,
)
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import XLSX_MEDIA_TYPE, check_ready
from abacus.modules.identity.api import AuthContext
from abacus.worker.__main__ import build_workers
from abacus_tools.synthetic import generate
from abacus_tools.synthetic.connector_fixtures import (
    trial_balance_document,
    write_fault,
    write_raw,
    write_trial_balance,
)

MASTER = b"retrieval-test-master-key-0123456789abcdef"
BUCKET = f"retrieval-wf-{uuid.uuid4().hex[:12]}"
QUEUE = f"retrieval-wf-{uuid.uuid4().hex[:12]}"
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
Json = dict[str, object]


class Migrated(Protocol):
    owner_url: str
    app_url: str
    relay_url: str
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
    configure_relay_engine(migrated_db.relay_url)
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


# --- Temporal ------------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def task_queue(monkeypatch: pytest.MonkeyPatch, fake_dir: Path) -> Iterator[None]:
    monkeypatch.setenv("ABACUS_TEMPORAL_TASK_QUEUE", QUEUE)
    settings.cache_clear()
    yield
    settings.cache_clear()


@asynccontextmanager
async def _serving() -> AsyncGenerator[list[Worker]]:
    """Every class's pool (and the legacy queue), as `python -m abacus.worker` runs them."""
    async with AsyncExitStack() as pools:
        built = await build_workers()
        for pool in built:
            await pools.enter_async_context(pool)
        yield built


@pytest.fixture
async def temporal(temporal_target: str) -> AsyncIterator[Client]:
    client = await Client.connect(temporal_target, data_converter=data_converter())
    configure_temporal_client(client)
    yield client
    configure_temporal_client(None)


@pytest.fixture
async def worker(temporal: Client) -> AsyncIterator[list[Worker]]:
    async with _serving() as built:
        yield built


# --- helpers -------------------------------------------------------------------------------------


async def _start(world: World) -> uuid.UUID:
    started = await start_retrieval(
        world.requester.context(),
        engagement_id=world.engagement_id,
        request_item_id=world.item_id,
        period=PERIOD,
    )
    assert isinstance(started, StartedRun)
    assert started.created is True
    return started.run_id


async def _execute(temporal: Client, world: World, run_id: uuid.UUID) -> RetrievalOutcome:
    return await temporal.execute_workflow(
        RetrievalWorkflow.run,
        RetrievalInput(str(world.tenant_id), str(run_id)),
        id=f"test-{uuid.uuid4()}",
        task_queue=queue_for("interactive"),
        execution_timeout=timedelta(seconds=90),
    )


async def _retrieve(temporal: Client, world: World) -> tuple[uuid.UUID, RetrievalOutcome]:
    run_id = await _start(world)
    return run_id, await _execute(temporal, world, run_id)


def _unbalanced(document: dict[str, object]) -> None:
    lines = cast(list[dict[str, object]], document["lines"])
    lines[0]["debit"] = str(Decimal(str(lines[0]["debit"])) + Decimal("5.00"))
    totals = cast(dict[str, str], document["control_totals"])
    totals["debit"] = str(Decimal(totals["debit"]) + Decimal("5.00"))


async def _tables(seed: Seeder, tenant_id: uuid.UUID) -> dict[str, int]:
    return {table: await seed.count(table, tenant_id) for table in COUNTS}


# --- AC-9, AC-10: the happy path through Temporal ------------------------------------------------


@pytest.mark.usefixtures("worker")
async def test_ac9_the_workflow_succeeds_with_the_evidence_version_id(
    seed: Seeder, world: World, temporal: Client
) -> None:
    run_id, outcome = await _retrieve(temporal, world)
    row = await seed.run_row(run_id)
    assert row["status"] == "succeeded"
    assert outcome == RetrievalOutcome("succeeded", None, str(row["evidence_version_id"]))
    assert outcome.code is None
    assert row["evidence_version_id"] is not None


@pytest.mark.usefixtures("worker")
async def test_ac10_the_database_is_as_after_the_pipeline(
    seed: Seeder, world: World, temporal: Client
) -> None:
    run_id, outcome = await _retrieve(temporal, world)
    row = await seed.run_row(run_id)
    assert row["failure_code"] is None
    assert row["finished_at"] is not None
    assert row["raw_fingerprint"] is not None
    assert (
        row["raw_fingerprint"]
        == hashlib.sha256(
            next((world.directory / str(world.connection_id)).iterdir()).read_bytes()
        ).hexdigest()
    )
    for table in ("ledger_snapshots", "evidence_items", "evidence_versions", "fulfilments"):
        assert await seed.count(table, world.tenant_id) == 1
    assert await seed.count("trial_balance_lines", world.tenant_id) == len(TB.lines)
    assert await seed.item_status(world.item_id) == "received"
    [snap] = await seed.rows(
        "SELECT * FROM ledger_snapshots WHERE tenant_id = $1", world.tenant_id
    )
    assert snap["id"] == row["snapshot_id"]
    assert snap["line_count"] == len(TB.lines)
    assert snap["total_debit"] == TB.total_debits
    assert snap["total_credit"] == TB.total_credits
    [version] = await seed.rows(
        "SELECT * FROM evidence_versions WHERE tenant_id = $1", world.tenant_id
    )
    assert str(version["id"]) == outcome.evidence_version_id
    assert version["method"] == "retrieved"
    assert version["media_type"] == XLSX_MEDIA_TYPE
    assert version["snapshot_id"] == snap["id"]
    assert version["client_entity_id"] == world.entity_id
    assert (version["period_start"], version["period_end"]) == (PERIOD.start, PERIOD.end)
    [fulfilment] = await seed.rows(
        "SELECT * FROM fulfilments WHERE tenant_id = $1", world.tenant_id
    )
    assert fulfilment["created_by_kind"] == "rule"
    assert fulfilment["evidence_version_id"] == version["id"]


@pytest.mark.usefixtures("worker")
async def test_ac10_audit_events_and_outbox_are_as_after_the_pipeline(
    seed: Seeder, world: World, temporal: Client
) -> None:
    run_id, _ = await _retrieve(temporal, world)
    events = await seed.events(world.tenant_id)
    assert [e.action for e in events] == EXPECTED_EVENTS
    assert (events[0].actor_kind, events[0].actor_id) == ("human", str(world.requester.user_id))
    for event in events[1:]:
        assert (event.actor_kind, event.actor_id) == ("system", f"run:{run_id}")
    outbox = await seed.rows(
        "SELECT event_type FROM outbox WHERE tenant_id = $1 ORDER BY seq", world.tenant_id
    )
    assert [str(r["event_type"]) for r in outbox] == ["evidence_version.created"]


# --- AC-11: failures decided by the data ---------------------------------------------------------


@pytest.mark.usefixtures("worker")
async def test_ac11_an_unbalanced_trial_balance_fails_validation(
    seed: Seeder, world: World, temporal: Client
) -> None:
    world.write_document(_unbalanced)
    run_id, outcome = await _retrieve(temporal, world)
    assert outcome == RetrievalOutcome("failed_validation", "unbalanced", None)
    row = await seed.run_row(run_id)
    assert row["status"] == "failed_validation"
    assert row["failure_code"] == "unbalanced"
    assert row["snapshot_id"] is None
    assert row["evidence_version_id"] is None
    for table in ("ledger_snapshots", "evidence_versions", "fulfilments"):
        assert await seed.count(table, world.tenant_id) == 0
    assert await seed.item_status(world.item_id) == "open"
    assert (await seed.actions(world.tenant_id)).count("sync_run.failed") == 1


@pytest.mark.usefixtures("worker")
async def test_ac11_a_malformed_payload_fails_the_run(
    seed: Seeder, world: World, temporal: Client
) -> None:
    write_raw(world.directory, world.connection_id, PERIOD, b"not json at all")
    run_id, outcome = await _retrieve(temporal, world)
    assert outcome == RetrievalOutcome("failed", "malformed_payload", None)
    row = await seed.run_row(run_id)
    assert (row["status"], row["failure_code"]) == ("failed", "malformed_payload")
    assert await seed.count("ledger_snapshots", world.tenant_id) == 0
    assert await seed.item_status(world.item_id) == "open"


@pytest.mark.usefixtures("worker")
async def test_ac11_a_missing_fixture_fails_the_run_with_no_data(
    seed: Seeder, world: World, temporal: Client
) -> None:
    for path in (world.directory / str(world.connection_id)).iterdir():
        path.unlink()
    run_id, outcome = await _retrieve(temporal, world)
    assert outcome == RetrievalOutcome("failed", "no_data", None)
    assert (await seed.run_row(run_id))["status"] == "failed"


# --- provider outages ----------------------------------------------------------------------------


@pytest.mark.usefixtures("worker")
async def test_ac9_a_provider_outage_that_clears_is_retried_to_success(
    seed: Seeder, world: World, temporal: Client
) -> None:
    write_fault(world.directory, world.connection_id, PERIOD)
    run_id = await _start(world)
    handle = await temporal.start_workflow(
        RetrievalWorkflow.run,
        RetrievalInput(str(world.tenant_id), str(run_id)),
        id=f"test-{uuid.uuid4()}",
        task_queue=queue_for("interactive"),
        execution_timeout=timedelta(seconds=90),
    )
    async with asyncio.timeout(30):
        while True:
            description = await handle.describe()
            pending = description.raw_description.pending_activities
            if pending and pending[0].attempt >= 1 and pending[0].HasField("last_failure"):
                break
            await asyncio.sleep(0.2)
    assert (await seed.run_row(run_id))["status"] == "running"
    world.write_fixture()  # the provider recovers before the retries run out
    outcome = await handle.result()
    assert outcome.status == "succeeded"
    assert outcome.evidence_version_id is not None
    row = await seed.run_row(run_id)
    assert row["status"] == "succeeded"
    assert await seed.count("evidence_versions", world.tenant_id) == 1
    assert await seed.count("ledger_snapshots", world.tenant_id) == 1
    assert await seed.count("fulfilments", world.tenant_id) == 1


async def test_ac11_an_outage_that_exhausts_the_retries_maps_to_provider_unavailable(
    seed: Seeder, world: World, temporal: Client
) -> None:
    """Exhaustion needs six attempts and over a minute of backoff, and the workflow's retry
    policy is a module constant, so this stands in for the pull activity with one whose final
    failure has the shape an exhausted real outage has (an `Unavailable` application error)."""

    @activity.defn(name="retrieval.pull_raw")
    async def always_down(input: RetrievalInput) -> None:
        raise ApplicationError("provider down", type="Unavailable", non_retryable=True)

    others = [a for a in ACTIVITIES if not a.__name__.startswith("pull_raw")]
    async with Worker(
        temporal,
        task_queue=queue_for("interactive"),
        workflows=[RetrievalWorkflow],
        activities=[always_down, *others],
    ):
        run_id, outcome = await _retrieve(temporal, world)
    assert outcome == RetrievalOutcome("failed", "provider_unavailable", None)
    row = await seed.run_row(run_id)
    assert (row["status"], row["failure_code"]) == ("failed", "provider_unavailable")
    assert await seed.item_status(world.item_id) == "open"


# --- every payload is encrypted at rest (ADR-017) ------------------------------------------------


PATCH_ID = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
CORE_PATCH = "core_patch"
CHANGE_VERSION = "TemporalChangeVersion"


def _decoded(payload: Json) -> object:
    metadata = cast(dict[str, str], payload.get("metadata", {}))
    assert base64.b64decode(metadata.get("encoding", "")).decode() == "json/plain"
    return json.loads(base64.b64decode(cast(str, payload["data"])))


def _encodings(node: object, plain: list[object]) -> list[str]:
    """Every payload's encoding. The only payloads allowed in the clear are Temporal's own
    `core_patch` marker details and `TemporalChangeVersion` search attribute (TASK-018b, SPEC-003:
    `workflow.patched` writes them as plain JSON); they are returned decoded in `plain`."""
    found: list[str] = []
    if isinstance(node, dict):
        mapping = cast(Json, node)
        if mapping.get("markerName") == CORE_PATCH:
            for entry in cast(Json, mapping.get("details", {})).values():
                for payload in cast(list[Json], cast(Json, entry).get("payloads", [])):
                    plain.append(_decoded(payload))
            return found
        indexed = mapping.get("indexedFields")
        if isinstance(indexed, dict):
            versions = cast(Json, indexed).pop(CHANGE_VERSION, None)
            if versions is not None:
                plain.append(_decoded(cast(Json, versions)))
            assert not indexed, f"unexpected search attributes in the history: {sorted(indexed)}"
            return found
        payloads = mapping.get("payloads")
        if isinstance(payloads, list):
            for payload in cast(list[Json], payloads):
                metadata = cast(dict[str, str], payload.get("metadata", {}))
                found.append(base64.b64decode(metadata.get("encoding", "")).decode())
        for value in mapping.values():
            found.extend(_encodings(value, plain))
    elif isinstance(node, list):
        for item in cast(list[object], node):
            found.extend(_encodings(item, plain))
    return found


def _patch_ids(plain: list[object]) -> set[str]:
    """The patch IDs in the plain-JSON payloads, asserting they hold nothing else."""
    ids: set[str] = set()
    for value in plain:
        if isinstance(value, dict):  # the marker: {"id": ..., "deprecated": ...}
            marker = cast(Json, value)
            assert set(marker) <= {"id", "deprecated"}, marker
            assert isinstance(marker["id"], str)
            assert isinstance(marker.get("deprecated", False), bool)
            ids.add(marker["id"])
        else:  # the search attribute: a list of patch IDs
            assert isinstance(value, list), value
            for item in cast(list[object], value):
                assert isinstance(item, str)
                ids.add(item)
    for patch in ids:
        assert PATCH_ID.match(patch), patch
    return ids


@pytest.mark.usefixtures("worker")
async def test_ac20_every_input_and_result_in_the_history_is_encrypted(
    world: World, temporal: Client
) -> None:
    run_id = await _start(world)
    handle = await temporal.start_workflow(
        RetrievalWorkflow.run,
        RetrievalInput(str(world.tenant_id), str(run_id)),
        id=f"test-{uuid.uuid4()}",
        task_queue=queue_for("interactive"),
    )
    await handle.result()
    history = await handle.fetch_history()
    text = history.to_json()
    plain: list[object] = []
    encodings = _encodings(json.loads(text), plain)
    # the workflow's and each of seven activities' input and result (five stages and two slots)
    assert len(encodings) >= 11
    assert set(encodings) == {ENCODING.decode()}
    # Temporal's own patch marker and search attribute are plain JSON and hold only patch IDs
    assert len(plain) == 2  # exactly the marker and the search attribute
    assert "work-slots" in _patch_ids(plain)
    # identifiers never appear in the clear
    assert str(world.tenant_id) not in text
    assert str(run_id) not in text


@pytest.mark.usefixtures("worker")
async def test_ac20_a_client_without_the_codec_cannot_read_the_result(
    world: World, temporal: Client, temporal_target: str
) -> None:
    run_id = await _start(world)
    workflow_id_ = f"test-{uuid.uuid4()}"
    await temporal.execute_workflow(
        RetrievalWorkflow.run,
        RetrievalInput(str(world.tenant_id), str(run_id)),
        id=workflow_id_,
        task_queue=queue_for("interactive"),
    )
    plain = await Client.connect(temporal_target)
    handle = plain.get_workflow_handle(workflow_id_)
    with pytest.raises(KeyError, match="binary/abacus-encrypted"):
        await handle.result()
    # the same workflow, read with the codec, is readable
    assert (await temporal.get_workflow_handle(workflow_id_).result()) is not None


# --- activities ----------------------------------------------------------------------------------

STAGE_NAMES = ["pull_raw", "normalise_raw", "validate_run", "snapshot", "render"]


def _stage(name: str) -> Callable[[RetrievalInput], Awaitable[object]]:
    [found] = [a for a in ACTIVITIES if a.__name__.startswith(name)]
    return cast(Callable[[RetrievalInput], Awaitable[object]], found)


def _fail_activity() -> Callable[[FailInput], Awaitable[object]]:
    [found] = [a for a in ACTIVITIES if a.__name__.startswith("fail_run")]
    return cast(Callable[[FailInput], Awaitable[object]], found)


async def _call[T](function: Callable[[T], Awaitable[object]], argument: T) -> object:
    return await ActivityEnvironment().run(function, argument)


def test_ac20_there_are_eight_activities_one_per_stage_plus_fail_run_and_the_two_slot_ones() -> None:
    assert len(ACTIVITIES) == 8  # TASK-018b: acquire_slot and release_slot join the six
    names = {a.__name__ for a in ACTIVITIES}
    assert {"acquire_slot_activity", "release_slot_activity"} <= names


@pytest.mark.parametrize("name", STAGE_NAMES)
async def test_ac20_an_activity_for_an_unknown_run_is_a_non_retryable_not_found_and_writes_nothing(
    seed: Seeder, world: World, name: str
) -> None:
    before = await _tables(seed, world.tenant_id)
    with pytest.raises(ApplicationError) as raised:
        await _call(_stage(name), RetrievalInput(str(world.tenant_id), str(uuid.uuid4())))
    assert (raised.value.type, raised.value.message) == ("NotFound", "NotFound")
    assert raised.value.non_retryable
    assert await _tables(seed, world.tenant_id) == before


@pytest.mark.parametrize("name", STAGE_NAMES)
async def test_ac20_an_activity_trusts_the_run_row_not_its_input_tenant(
    seed: Seeder, world: World, name: str
) -> None:
    """The input is never proof: another firm's tenant ID with this firm's run finds no run."""
    run_id = await _start(world)
    other = await seed.firm()
    before = await _tables(seed, world.tenant_id)
    with pytest.raises(ApplicationError) as raised:
        await _call(_stage(name), RetrievalInput(str(other), str(run_id)))
    assert raised.value.type == "NotFound"
    assert raised.value.non_retryable
    assert await _tables(seed, world.tenant_id) == before
    assert (await seed.run_row(run_id))["status"] == "running"


async def test_ac20_the_stage_activities_run_the_pipeline_from_the_run_row_alone(
    seed: Seeder, world: World
) -> None:
    run_id = await _start(world)
    given = RetrievalInput(str(world.tenant_id), str(run_id))
    for name in STAGE_NAMES[:-1]:
        await _call(_stage(name), given)
    version = await _call(_stage("render"), given)
    row = await seed.run_row(run_id)
    assert row["status"] == "succeeded"
    assert version == str(row["evidence_version_id"])


@pytest.mark.parametrize("name", STAGE_NAMES)
async def test_ac20_a_retried_activity_after_success_returns_and_changes_nothing(
    seed: Seeder, world: World, name: str
) -> None:
    run_id = await _start(world)
    given = RetrievalInput(str(world.tenant_id), str(run_id))
    for stage in STAGE_NAMES:
        await _call(_stage(stage), given)
    before = await _tables(seed, world.tenant_id)
    events = await seed.actions(world.tenant_id)
    row_before = dict(await seed.run_row(run_id))
    await _call(_stage(name), given)
    assert await _tables(seed, world.tenant_id) == before
    assert await seed.actions(world.tenant_id) == events
    assert dict(await seed.run_row(run_id)) == row_before


async def test_ac20_a_stage_activity_on_a_failed_run_is_a_run_failed_with_the_runs_own_state(
    seed: Seeder, world: World
) -> None:
    world.write_document(_unbalanced)
    run_id = await _start(world)
    given = RetrievalInput(str(world.tenant_id), str(run_id))
    await _call(_stage("pull_raw"), given)
    await _call(_stage("normalise_raw"), given)
    with pytest.raises(ApplicationError) as raised:
        await _call(_stage("validate_run"), given)
    assert (raised.value.type, raised.value.message) == ("RunFailed", "RunFailed")
    assert raised.value.non_retryable
    assert tuple(raised.value.details) == ("failed_validation", "unbalanced")
    assert (await seed.run_row(run_id))["status"] == "failed_validation"
    for name in ("snapshot", "render"):
        with pytest.raises(ApplicationError) as again:
            await _call(_stage(name), given)
        assert again.value.type == "RunFailed"
        assert again.value.non_retryable
        assert tuple(again.value.details) == ("failed_validation", "unbalanced")


async def test_ac20_a_provider_outage_is_a_retryable_unavailable_with_only_the_class_name(
    seed: Seeder, world: World
) -> None:
    write_fault(world.directory, world.connection_id, PERIOD)
    run_id = await _start(world)
    with pytest.raises(ApplicationError) as raised:
        await _call(_stage("pull_raw"), RetrievalInput(str(world.tenant_id), str(run_id)))
    assert (raised.value.type, raised.value.message) == ("Unavailable", "Unavailable")
    assert not raised.value.non_retryable
    assert (await seed.run_row(run_id))["status"] == "running"


async def test_ac20_an_activity_for_a_run_that_failed_for_another_reason_reports_that_reason(
    seed: Seeder, world: World
) -> None:
    run_id = await _start(world)
    given = RetrievalInput(str(world.tenant_id), str(run_id))
    await _call(
        _fail_activity(), FailInput(str(world.tenant_id), str(run_id), "failed", "cancelled")
    )
    with pytest.raises(ApplicationError) as raised:
        await _call(_stage("pull_raw"), given)
    assert raised.value.type == "RunFailed"
    assert tuple(raised.value.details) == ("failed", "cancelled")


async def test_ac20_a_retried_render_after_success_returns_the_recorded_version_id(
    seed: Seeder, world: World
) -> None:
    run_id = await _start(world)
    given = RetrievalInput(str(world.tenant_id), str(run_id))
    for stage in STAGE_NAMES[:-1]:
        await _call(_stage(stage), given)
    first = await _call(_stage("render"), given)
    again = await _call(_stage("render"), given)
    recorded = (await seed.run_row(run_id))["evidence_version_id"]
    assert first == again == str(recorded)


async def test_ac20_fail_run_ends_a_running_run(seed: Seeder, world: World) -> None:
    run_id = await _start(world)
    outcome = await _call(
        _fail_activity(),
        FailInput(str(world.tenant_id), str(run_id), "failed", "provider_unavailable"),
    )
    assert outcome == RetrievalOutcome("failed", "provider_unavailable")
    row = await seed.run_row(run_id)
    assert (row["status"], row["failure_code"]) == ("failed", "provider_unavailable")
    assert (await seed.actions(world.tenant_id)).count("sync_run.failed") == 1


async def test_ac20_fail_run_on_a_succeeded_run_returns_its_state_and_changes_nothing(
    seed: Seeder, world: World
) -> None:
    run_id = await _start(world)
    given = RetrievalInput(str(world.tenant_id), str(run_id))
    for stage in STAGE_NAMES:
        await _call(_stage(stage), given)
    before = await _tables(seed, world.tenant_id)
    events = await seed.actions(world.tenant_id)
    row_before = dict(await seed.run_row(run_id))
    outcome = await _call(
        _fail_activity(), FailInput(str(world.tenant_id), str(run_id), "failed", "internal_error")
    )
    assert outcome == RetrievalOutcome("succeeded", None, str(row_before["evidence_version_id"]))
    assert await _tables(seed, world.tenant_id) == before
    assert await seed.actions(world.tenant_id) == events
    assert dict(await seed.run_row(run_id)) == row_before


async def test_ac20_fail_run_on_a_failed_validation_run_returns_the_runs_own_code(
    seed: Seeder, world: World
) -> None:
    world.write_document(_unbalanced)
    run_id = await _start(world)
    given = RetrievalInput(str(world.tenant_id), str(run_id))
    await _call(_stage("pull_raw"), given)
    await _call(_stage("normalise_raw"), given)
    with pytest.raises(ApplicationError):
        await _call(_stage("validate_run"), given)
    events = await seed.actions(world.tenant_id)
    row_before = dict(await seed.run_row(run_id))
    outcome = await _call(
        _fail_activity(), FailInput(str(world.tenant_id), str(run_id), "failed", "internal_error")
    )
    assert outcome == RetrievalOutcome("failed_validation", "unbalanced", None)
    assert await seed.actions(world.tenant_id) == events
    assert dict(await seed.run_row(run_id)) == row_before


@pytest.mark.parametrize(
    ("status", "code", "expected"),
    [
        ("failed", "provider_unavailable", ("failed", "provider_unavailable")),
        ("failed", "internal_error", ("failed", "internal_error")),
        ("failed", "cancelled", ("failed", "cancelled")),
        ("failed_validation", "internal_error", ("failed_validation", "internal_error")),
        ("succeeded", "internal_error", ("failed", "internal_error")),
        ("running", "internal_error", ("failed", "internal_error")),
        ("anything", "internal_error", ("failed", "internal_error")),
        ("failed", "unbalanced", ("failed", "internal_error")),
        ("failed", "test-marker-free-text", ("failed", "internal_error")),
        ("failed", "", ("failed", "internal_error")),
    ],
)
async def test_ac20_fail_run_accepts_only_the_allowlisted_status_and_code(
    seed: Seeder, world: World, status: str, code: str, expected: tuple[str, str]
) -> None:
    run_id = await _start(world)
    outcome = await _call(
        _fail_activity(), FailInput(str(world.tenant_id), str(run_id), status, code)
    )
    assert isinstance(outcome, RetrievalOutcome)
    assert (outcome.status, outcome.code) == expected
    row = await seed.run_row(run_id)
    assert (row["status"], row["failure_code"]) == expected


async def test_ac20_fail_run_for_an_unknown_run_is_a_non_retryable_not_found(
    world: World,
) -> None:
    with pytest.raises(ApplicationError) as raised:
        await _call(
            _fail_activity(),
            FailInput(str(world.tenant_id), str(uuid.uuid4()), "failed", "internal_error"),
        )
    assert raised.value.type == "NotFound"
    assert raised.value.non_retryable


# --- duplicate start -----------------------------------------------------------------------------


async def test_ac20_the_workflow_id_is_bound_to_the_run() -> None:
    run_id = uuid.uuid4()
    assert workflow_id(run_id) == f"retrieval:{run_id}"


async def test_ac20_a_second_start_of_the_same_workflow_id_attaches_to_the_running_one(
    seed: Seeder, world: World, temporal: Client
) -> None:
    ctx = world.requester.context()
    first = await trigger_retrieval(
        ctx, engagement_id=world.engagement_id, request_item_id=world.item_id, period=PERIOD
    )
    second = await trigger_retrieval(
        ctx, engagement_id=world.engagement_id, request_item_id=world.item_id, period=PERIOD
    )
    assert first.status == "running"
    assert second.sync_run_id == first.sync_run_id
    wid = workflow_id(first.sync_run_id)
    # no worker has run yet: both starts met one open workflow
    open_ones = [w async for w in temporal.list_workflows(f"WorkflowId = '{wid}'")]
    assert len(open_ones) == 1
    async with _serving():
        outcome = await temporal.get_workflow_handle_for(RetrievalWorkflow.run, wid).result()
        # a third start, after completion, still finds the one workflow ID
        await temporal.start_workflow(
            "retrieval",
            RetrievalInput(str(world.tenant_id), str(first.sync_run_id)),
            id=wid,
            task_queue=queue_for("interactive"),
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )
    assert outcome.status == "succeeded"
    for table in ("sync_runs", "ledger_snapshots", "evidence_versions", "fulfilments"):
        assert await seed.count(table, world.tenant_id) == 1


async def test_ac20_a_retrigger_after_a_failed_run_makes_a_new_run_and_workflow_that_succeeds(
    seed: Seeder, world: World, temporal: Client
) -> None:
    ctx = world.requester.context()
    world.write_document(_unbalanced)
    first = await trigger_retrieval(
        ctx, engagement_id=world.engagement_id, request_item_id=world.item_id, period=PERIOD
    )
    async with _serving():
        failed = await temporal.get_workflow_handle_for(
            RetrievalWorkflow.run, workflow_id(first.sync_run_id)
        ).result()
        assert failed.status == "failed_validation"
        world.write_fixture()
        second = await trigger_retrieval(
            ctx, engagement_id=world.engagement_id, request_item_id=world.item_id, period=PERIOD
        )
        assert second.sync_run_id != first.sync_run_id
        assert second.status == "running"
        again = await temporal.get_workflow_handle_for(
            RetrievalWorkflow.run, workflow_id(second.sync_run_id)
        ).result()
    assert again.status == "succeeded"
    assert (await seed.run_row(first.sync_run_id))["status"] == "failed_validation"
    assert (await seed.run_row(second.sync_run_id))["status"] == "succeeded"
    assert await seed.item_status(world.item_id) == "received"


# --- failure text never reaches Temporal in the clear --------------------------------------------

MARKER = "test-marker-failure-text-8841"


async def test_ac20_failure_messages_never_appear_in_the_history(
    world: World, temporal: Client
) -> None:
    @activity.defn(name="retrieval.pull_raw")
    async def leaks(input: RetrievalInput) -> None:
        raise ApplicationError(
            f"provider said {MARKER}", MARKER, type="Unavailable", non_retryable=True
        )

    others = [a for a in ACTIVITIES if not a.__name__.startswith("pull_raw")]
    run_id = await _start(world)
    async with Worker(
        temporal,
        task_queue=queue_for("interactive"),
        workflows=[RetrievalWorkflow],
        activities=[leaks, *others],
    ):
        handle = await temporal.start_workflow(
            RetrievalWorkflow.run,
            RetrievalInput(str(world.tenant_id), str(run_id)),
            id=f"test-{uuid.uuid4()}",
            task_queue=queue_for("interactive"),
            execution_timeout=timedelta(seconds=30),
        )
        await handle.result()
        history = await handle.fetch_history()
    text = history.to_json()
    assert "ApplicationFailureInfo" in text or "applicationFailureInfo" in text
    assert MARKER not in text
    assert base64.b64encode(MARKER.encode()).decode().rstrip("=") not in text
    assert "provider said" not in text


# --- cancellation --------------------------------------------------------------------------------


@pytest.mark.usefixtures("worker")
async def test_ac20_a_cancelled_workflow_ends_its_run_as_cancelled_and_stays_cancelled(
    seed: Seeder, world: World, temporal: Client
) -> None:
    write_fault(world.directory, world.connection_id, PERIOD)
    run_id = await _start(world)
    handle = await temporal.start_workflow(
        RetrievalWorkflow.run,
        RetrievalInput(str(world.tenant_id), str(run_id)),
        id=f"test-{uuid.uuid4()}",
        task_queue=queue_for("interactive"),
        execution_timeout=timedelta(seconds=60),
    )
    async with asyncio.timeout(30):
        while True:
            pending = (await handle.describe()).raw_description.pending_activities
            if pending and pending[0].HasField("last_failure"):
                break
            await asyncio.sleep(0.2)
    await handle.cancel()
    with pytest.raises(WorkflowFailureError) as raised:
        await handle.result()
    assert isinstance(raised.value.cause, CancelledError)
    row = await seed.run_row(run_id)
    assert (row["status"], row["failure_code"]) == ("failed", "cancelled")
    assert await seed.item_status(world.item_id) == "open"


# --- work-class queues (AC-1, AC-2, AC-16) -------------------------------------------------------


async def _activity_queues(
    handle: WorkflowHandle[RetrievalWorkflow, RetrievalOutcome],
) -> set[str]:
    history = await handle.fetch_history()
    return {
        e.activity_task_scheduled_event_attributes.task_queue.name
        for e in history.events
        if e.HasField("activity_task_scheduled_event_attributes")
    }


async def _pollers(temporal: Client, queue: str) -> int:
    answer = await temporal.workflow_service.describe_task_queue(
        DescribeTaskQueueRequest(
            namespace=temporal.namespace,
            task_queue=TaskQueue(name=queue),
            task_queue_type=TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW,
        )
    )
    return len(answer.pollers)


@pytest.mark.usefixtures("worker")
async def test_ac1_the_worker_polls_one_queue_per_class_and_the_legacy_queue(
    temporal: Client,
) -> None:
    queues = [*(queue_for(c) for c in WORK_CLASSES), QUEUE]
    assert len(set(queues)) == 5
    async with asyncio.timeout(30):
        while True:
            counts = [await _pollers(temporal, queue) for queue in queues]
            if all(counts):
                break
            await asyncio.sleep(0.2)
    # a queue nobody serves has no poller
    assert await _pollers(temporal, f"{QUEUE}-unserved") == 0


@pytest.mark.usefixtures("worker")
async def test_ac2_a_dispatched_retrieval_and_its_activities_run_on_the_interactive_queue(
    seed: Seeder, world: World, temporal: Client
) -> None:
    ctx = world.requester.context()
    triggered = await trigger_retrieval(
        ctx, engagement_id=world.engagement_id, request_item_id=world.item_id, period=PERIOD
    )
    handle = temporal.get_workflow_handle_for(
        RetrievalWorkflow.run, workflow_id(triggered.sync_run_id)
    )
    async with asyncio.timeout(90):
        outcome = await handle.result()
    assert outcome.status == "succeeded"
    assert (await handle.describe()).task_queue == queue_for("interactive")
    assert await _activity_queues(handle) == {queue_for("interactive")}
    assert (await seed.run_row(triggered.sync_run_id))["status"] == "succeeded"


@pytest.mark.usefixtures("worker")
async def test_ac16_a_workflow_started_on_the_legacy_queue_completes_there(
    seed: Seeder, world: World, temporal: Client
) -> None:
    run_id = await _start(world)
    handle = await temporal.start_workflow(
        RetrievalWorkflow.run,
        RetrievalInput(str(world.tenant_id), str(run_id)),
        id=f"legacy-{uuid.uuid4()}",
        task_queue=QUEUE,  # the old single queue, as a workflow open before the release
        execution_timeout=timedelta(seconds=90),
    )
    async with asyncio.timeout(90):
        outcome = await handle.result()
    assert outcome.status == "succeeded"
    assert (await handle.describe()).task_queue == QUEUE
    assert await _activity_queues(handle) == {QUEUE}
    assert (await seed.run_row(run_id))["status"] == "succeeded"


async def test_ac16_nothing_serves_the_legacy_queue_when_it_is_switched_off(
    temporal: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    # a base queue of its own: earlier tests' pollers on QUEUE linger on the server
    base = f"no-legacy-{uuid.uuid4().hex[:10]}"
    monkeypatch.setenv("ABACUS_TEMPORAL_TASK_QUEUE", base)
    monkeypatch.setenv("ABACUS_SERVE_LEGACY_QUEUE", "false")
    settings.cache_clear()
    async with _serving() as built:
        assert [w.task_queue for w in built] == [queue_for(c) for c in WORK_CLASSES]
        await asyncio.sleep(1)
        assert await _pollers(temporal, base) == 0
        assert await _pollers(temporal, queue_for("interactive")) > 0


# --- worker startup ------------------------------------------------------------------------------


async def test_ac20_build_workers_polls_the_class_queues_and_the_configured_legacy_queue(
    temporal: Client,
) -> None:
    built = await build_workers()
    assert [w.task_queue for w in built] == [
        *(queue_for(c) for c in WORK_CLASSES),
        QUEUE,
    ]


async def test_ac20_build_workers_raises_without_a_usable_key_service(
    temporal: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    reset_key_service()
    monkeypatch.setenv("ABACUS_S3_ENDPOINT_URL", "https://s3.example.test")
    settings.cache_clear()
    with pytest.raises(RuntimeError, match="key service"):
        await build_workers()


async def test_ac20_build_workers_raises_when_the_database_is_unreachable(
    temporal: Client,
) -> None:
    await dispose_engine()
    configure_engine("postgresql+asyncpg://abacus_app:test-unused@127.0.0.1:1/abacus")
    with pytest.raises((OSError, DBAPIError)):
        await build_workers()


async def test_ac20_build_workers_raises_without_a_usable_payload_codec(
    temporal: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ABACUS_TEMPORAL_PAYLOAD_KEY", "test-too-short")
    settings.cache_clear()
    with pytest.raises(ValueError):
        await build_workers()


@pytest.fixture
def unlocked_bucket(s3_settings: dict[str, str]) -> Iterator[tuple[S3Client, str]]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    name = f"retrieval-wf-nolock-{uuid.uuid4().hex[:10]}"
    client.create_bucket(Bucket=name)
    yield client, name
    client.delete_bucket(Bucket=name)


async def test_ac20_check_ready_raises_for_a_bucket_without_object_lock(
    unlocked_bucket: tuple[S3Client, str],
) -> None:
    client, name = unlocked_bucket
    storage.configure_storage(client, name)
    with pytest.raises((RuntimeError, ClientError)):
        await check_ready()


async def test_ac20_check_ready_accepts_a_bucket_with_object_lock() -> None:
    await check_ready()


async def test_ac20_build_workers_raises_for_a_bucket_without_object_lock(
    temporal: Client, unlocked_bucket: tuple[S3Client, str]
) -> None:
    client, name = unlocked_bucket
    storage.configure_storage(client, name)
    with pytest.raises((RuntimeError, ClientError)):
        await build_workers()
