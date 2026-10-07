"""AC-9, AC-10, AC-11, AC-20: the retrieval API over HTTP (TASK-010b interface contract and
revision 1, "API").

Rows are seeded as the superuser (`migrated_db.superuser_dsn`) with fresh firms per test. HTTP goes
through `httpx.ASGITransport(app=create_app())` with tokens from `FakeIdentityProvider`. Tests that
only need to see the workflow start use a recording stand-in for the Temporal client; the ones that
need a run to finish use the real dev server with an in-process worker on a queue of this module.
Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from contextlib import AsyncExitStack, asynccontextmanager
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol, cast

import asyncpg
import httpx
import pytest
from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.service import RPCError, RPCStatusCode
from temporalio.worker import Worker
from types_boto3_s3 import S3Client

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.dispatch import queue_for
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import (
    TenantContext,
    configure_engine,
    configure_relay_engine,
    dispose_engine,
)
from abacus.kernel.storage import s3_client
from abacus.kernel.temporal import configure_temporal_client, data_converter
from abacus.modules.connections.api import Period, RetrievalInput, RetrievalWorkflow, workflow_id
from abacus.modules.evidence import storage
from abacus.modules.identity.api import AuthContext, configure_verifier, reset_verifier
from abacus.worker.__main__ import build_workers
from abacus_tools.fakes.identity import FakeIdentityProvider
from abacus_tools.synthetic import generate
from abacus_tools.synthetic.connector_fixtures import (
    trial_balance_document,
    write_raw,
    write_trial_balance,
)

MASTER = b"retrieval-test-master-key-0123456789abcdef"
BUCKET = f"retrieval-api-{uuid.uuid4().hex[:12]}"
QUEUE = f"retrieval-api-{uuid.uuid4().hex[:12]}"
ENTITY = generate(1).client_entities[0]
TB = ENTITY.trial_balances[-1]
PERIOD = Period(ENTITY.period_start, TB.as_of)
ENTITY_NAME = "Seeded entity"
Role = Literal["engagement_partner", "manager", "senior", "staff", "reviewer"]
Json = dict[str, object]
RESPONSE_KEYS = {
    "sync_run_id",
    "request_item_id",
    "status",
    "failure_code",
    "evidence_version_id",
    "started_at",
    "finished_at",
}
DISTINCT_INPUT = "ZX-DISTINCTIVE-9137-input"


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
    subject: str

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

    async def person(self, tenant_id: uuid.UUID, firm_role: str | None = None) -> Person:
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
        return Person(user_id, tenant_id, subject)

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


# --- Temporal and HTTP fixtures ------------------------------------------------------------------


@pytest.fixture(autouse=True)
def task_queue(monkeypatch: pytest.MonkeyPatch, fake_dir: Path) -> Iterator[None]:
    monkeypatch.setenv("ABACUS_TEMPORAL_TASK_QUEUE", QUEUE)
    settings.cache_clear()
    yield
    settings.cache_clear()


@pytest.fixture(autouse=True)
def reset_temporal() -> Iterator[None]:
    yield
    configure_temporal_client(None)


class Recorder:
    """Stands in for the Temporal client: records starts, or fails them."""

    def __init__(self, failure: BaseException | None = None) -> None:
        self.failure = failure
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def start_workflow(self, *args: object, **kwargs: object) -> None:
        self.calls.append((args, kwargs))
        if self.failure is not None:
            raise self.failure


def _use(recorder: Recorder) -> Recorder:
    configure_temporal_client(cast(Client, recorder))
    return recorder


@pytest.fixture
def recorder() -> Recorder:
    return _use(Recorder())


@asynccontextmanager
async def _serving() -> AsyncIterator[list[Worker]]:
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


@pytest.fixture
async def worker(temporal: Client) -> AsyncIterator[list[Worker]]:
    async with _serving() as built:
        yield built


@pytest.fixture
def idp() -> Iterator[FakeIdentityProvider]:
    provider = FakeIdentityProvider()
    configure_verifier(provider.verifier())
    yield provider
    reset_verifier()


@pytest.fixture
async def http(idp: FakeIdentityProvider) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@dataclass(frozen=True)
class Api:
    http: httpx.AsyncClient
    idp: FakeIdentityProvider
    world: World

    def headers(self, who: Person) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.idp.token(who.subject)}"}

    def body(self, **overrides: object) -> Json:
        body: Json = {
            "request_item_id": str(self.world.item_id),
            "period_start": PERIOD.start.isoformat(),
            "period_end": PERIOD.end.isoformat(),
        }
        body.update(overrides)
        return body

    async def post(
        self,
        who: Person | None = None,
        *,
        engagement_id: uuid.UUID | None = None,
        body: Json | None = None,
    ) -> httpx.Response:
        return await self.http.post(
            f"/v1/engagements/{engagement_id or self.world.engagement_id}/retrievals",
            json=body if body is not None else self.body(),
            headers=self.headers(who or self.world.requester),
        )

    async def get(
        self,
        run_id: object,
        who: Person | None = None,
        *,
        engagement_id: uuid.UUID | None = None,
    ) -> httpx.Response:
        return await self.http.get(
            f"/v1/engagements/{engagement_id or self.world.engagement_id}/retrievals/{run_id}",
            headers=self.headers(who or self.world.requester),
        )

    async def finished(self, run_id: object) -> Json:
        async with asyncio.timeout(60):
            while True:
                response = await self.get(run_id)
                assert response.status_code == 200, response.text
                found = cast(Json, response.json())
                if found["status"] != "running":
                    return found
                await asyncio.sleep(0.2)


@pytest.fixture
def api(http: httpx.AsyncClient, idp: FakeIdentityProvider, world: World) -> Api:
    return Api(http, idp, world)


def _unbalanced(document: dict[str, object]) -> None:
    lines = cast(list[dict[str, object]], document["lines"])
    lines[0]["debit"] = str(Decimal(str(lines[0]["debit"])) + Decimal("5.00"))
    totals = cast(dict[str, str], document["control_totals"])
    totals["debit"] = str(Decimal(totals["debit"]) + Decimal("5.00"))


def _assert_shape(found: Json) -> None:
    assert set(found) == RESPONSE_KEYS
    uuid.UUID(cast(str, found["sync_run_id"]))
    datetime.fromisoformat(cast(str, found["started_at"]))


async def _other_firm_engagement(seed: Seeder) -> tuple[uuid.UUID, uuid.UUID]:
    other = await seed.firm()
    person = await seed.person(other)
    entity = await seed.entity(other)
    engagement = await seed.engagement(other, entity, person.user_id)
    await seed.member(engagement, person, "staff")
    return engagement, await seed.item(other, engagement, person.user_id)


# --- POST: 202 and the workflow start ------------------------------------------------------------


async def test_ac9_a_trigger_answers_202_with_a_running_run(
    api: Api, seed: Seeder, world: World, recorder: Recorder
) -> None:
    response = await api.post()
    assert response.status_code == 202, response.text
    found = cast(Json, response.json())
    _assert_shape(found)
    assert found["request_item_id"] == str(world.item_id)
    assert found["status"] == "running"
    assert found["failure_code"] is None
    assert found["evidence_version_id"] is None
    assert found["finished_at"] is None
    row = await seed.run_row(uuid.UUID(cast(str, found["sync_run_id"])))
    assert row["status"] == "running"
    assert row["started_by"] == str(world.requester.user_id)
    assert (row["period_start"], row["period_end"]) == (PERIOD.start, PERIOD.end)


async def test_ac9_the_trigger_starts_the_workflow_bound_to_the_run(
    api: Api, world: World, recorder: Recorder
) -> None:
    found = cast(Json, (await api.post()).json())
    run_id = uuid.UUID(cast(str, found["sync_run_id"]))
    [(args, kwargs)] = recorder.calls
    assert args[0] == RetrievalWorkflow.run
    assert args[1] == RetrievalInput(str(world.tenant_id), str(run_id))
    assert kwargs["id"] == workflow_id(run_id) == f"retrieval:{run_id}"
    assert kwargs["task_queue"] == queue_for("interactive")
    assert kwargs["id_reuse_policy"] == WorkflowIDReusePolicy.ALLOW_DUPLICATE
    assert kwargs["id_conflict_policy"] == WorkflowIDConflictPolicy.USE_EXISTING
    assert kwargs["execution_timeout"] == timedelta(hours=6)


async def test_ac9_a_second_trigger_for_the_same_item_and_period_returns_the_same_run(
    api: Api, seed: Seeder, world: World, recorder: Recorder
) -> None:
    first = cast(Json, (await api.post()).json())
    again = await api.post()
    assert again.status_code == 202
    assert cast(Json, again.json())["sync_run_id"] == first["sync_run_id"]
    assert await seed.count("sync_runs", world.tenant_id) == 1
    # both starts name the same workflow, so Temporal attaches the second to the first
    assert {cast(str, kw["id"]) for _, kw in recorder.calls} == {
        workflow_id(uuid.UUID(cast(str, first["sync_run_id"])))
    }


async def test_ac9_two_people_triggering_the_same_item_and_period_share_one_run(
    api: Api, seed: Seeder, world: World, recorder: Recorder
) -> None:
    colleague = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, colleague, "manager")
    first = cast(Json, (await api.post()).json())
    second = cast(Json, (await api.post(colleague)).json())
    assert second["sync_run_id"] == first["sync_run_id"]
    assert await seed.count("sync_runs", world.tenant_id) == 1


async def test_ac10_a_trigger_after_success_returns_the_succeeded_run_and_starts_nothing(
    api: Api, seed: Seeder, world: World, temporal: Client, worker: Worker
) -> None:
    first = cast(Json, (await api.post()).json())
    done = await api.finished(first["sync_run_id"])
    assert done["status"] == "succeeded"
    spy = _use(Recorder())
    again = await api.post()
    assert again.status_code == 202
    found = cast(Json, again.json())
    _assert_shape(found)
    assert found["sync_run_id"] == first["sync_run_id"]
    assert found["status"] == "succeeded"
    assert found["failure_code"] is None
    assert found["evidence_version_id"] == done["evidence_version_id"]
    assert found["finished_at"] is not None
    assert spy.calls == []
    assert await seed.count("sync_runs", world.tenant_id) == 1
    assert await seed.count("evidence_versions", world.tenant_id) == 1


async def test_ac10_a_trigger_runs_through_to_a_succeeded_run_with_timestamps(
    api: Api, seed: Seeder, world: World, temporal: Client, worker: Worker
) -> None:
    started = cast(Json, (await api.post()).json())
    done = await api.finished(started["sync_run_id"])
    _assert_shape(done)
    assert done["status"] == "succeeded"
    assert done["failure_code"] is None
    assert done["started_at"] == started["started_at"]
    assert done["finished_at"] is not None
    assert datetime.fromisoformat(cast(str, done["finished_at"])) >= datetime.fromisoformat(
        cast(str, done["started_at"])
    )
    version = uuid.UUID(cast(str, done["evidence_version_id"]))
    assert await seed.value("SELECT count(*) FROM evidence_versions WHERE id = $1", version) == 1
    assert await seed.item_status(world.item_id) == "received"


async def test_ac11_an_unbalanced_trial_balance_ends_failed_validation(
    api: Api, seed: Seeder, world: World, temporal: Client, worker: Worker
) -> None:
    world.write_document(_unbalanced)
    started = cast(Json, (await api.post()).json())
    done = await api.finished(started["sync_run_id"])
    assert (done["status"], done["failure_code"]) == ("failed_validation", "unbalanced")
    assert done["evidence_version_id"] is None
    assert done["finished_at"] is not None
    assert await seed.item_status(world.item_id) == "open"


async def test_ac11_a_trigger_after_a_failed_run_makes_a_new_run_that_can_succeed(
    api: Api, seed: Seeder, world: World, temporal: Client, worker: Worker
) -> None:
    world.write_document(_unbalanced)
    first = cast(Json, (await api.post()).json())
    assert (await api.finished(first["sync_run_id"]))["status"] == "failed_validation"
    world.write_fixture()
    second = await api.post()
    assert second.status_code == 202
    found = cast(Json, second.json())
    assert found["sync_run_id"] != first["sync_run_id"]
    assert found["status"] == "running"
    done = await api.finished(found["sync_run_id"])
    assert done["status"] == "succeeded"
    # the failed run keeps its own record
    old = cast(Json, (await api.get(first["sync_run_id"])).json())
    assert (old["status"], old["failure_code"]) == ("failed_validation", "unbalanced")
    assert await seed.count("sync_runs", world.tenant_id) == 2
    assert await seed.count("evidence_versions", world.tenant_id) == 1


# --- POST: authorisation, tenancy and validation -------------------------------------------------


def _assert_forbidden(response: httpx.Response) -> None:
    assert response.status_code == 403
    assert response.json() == {"detail": "forbidden"}


def _assert_not_found(response: httpx.Response) -> None:
    assert response.status_code == 404
    assert response.json() == {"detail": "not found"}


async def test_ac20_a_reviewer_is_forbidden_and_nothing_is_written(
    api: Api, seed: Seeder, world: World, recorder: Recorder
) -> None:
    reviewer = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, reviewer, "reviewer")
    _assert_forbidden(await api.post(reviewer))
    assert await seed.count("sync_runs", world.tenant_id) == 0
    assert await seed.count("audit_events", world.tenant_id) == 0
    assert recorder.calls == []


async def test_ac20_someone_with_no_relationship_to_the_engagement_is_forbidden(
    api: Api, seed: Seeder, world: World, recorder: Recorder
) -> None:
    stranger = await seed.person(world.tenant_id)
    _assert_forbidden(await api.post(stranger))
    assert await seed.count("sync_runs", world.tenant_id) == 0
    assert recorder.calls == []


async def test_ac20_another_firms_engagement_is_not_found(
    api: Api, seed: Seeder, world: World, recorder: Recorder
) -> None:
    engagement, item = await _other_firm_engagement(seed)
    _assert_not_found(
        await api.post(engagement_id=engagement, body=api.body(request_item_id=str(item)))
    )
    assert await seed.count("sync_runs", world.tenant_id) == 0
    assert recorder.calls == []


async def test_ac20_an_unknown_engagement_is_not_found(api: Api, recorder: Recorder) -> None:
    _assert_not_found(await api.post(engagement_id=uuid.uuid4()))
    assert recorder.calls == []


async def test_ac20_another_firms_request_item_is_not_found(
    api: Api, seed: Seeder, world: World, recorder: Recorder
) -> None:
    _, foreign_item = await _other_firm_engagement(seed)
    _assert_not_found(await api.post(body=api.body(request_item_id=str(foreign_item))))
    assert await seed.count("sync_runs", world.tenant_id) == 0


async def test_ac20_an_unknown_request_item_is_not_found(
    api: Api, seed: Seeder, world: World, recorder: Recorder
) -> None:
    _assert_not_found(await api.post(body=api.body(request_item_id=str(uuid.uuid4()))))
    assert await seed.count("sync_runs", world.tenant_id) == 0


async def test_ac20_an_item_of_another_engagement_is_not_found(
    api: Api, seed: Seeder, world: World, recorder: Recorder
) -> None:
    other = await seed.engagement(world.tenant_id, world.entity_id, world.requester.user_id)
    item = await seed.item(world.tenant_id, other, world.requester.user_id)
    _assert_not_found(await api.post(body=api.body(request_item_id=str(item))))
    assert await seed.count("sync_runs", world.tenant_id) == 0


async def test_ac20_without_a_token_the_answer_is_401(api: Api, http: httpx.AsyncClient) -> None:
    response = await http.post(
        f"/v1/engagements/{api.world.engagement_id}/retrievals", json=api.body()
    )
    assert response.status_code == 401
    response = await http.get(
        f"/v1/engagements/{api.world.engagement_id}/retrievals/{uuid.uuid4()}"
    )
    assert response.status_code == 401


# --- POST: 409 -----------------------------------------------------------------------------------


@pytest.mark.parametrize("state", ["revoked", "expired", "none"])
async def test_ac20_without_an_active_connection_the_answer_is_409_no_connection(
    api: Api, seed: Seeder, world: World, recorder: Recorder, state: str
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
    else:
        await seed.run("DELETE FROM connections WHERE id = $1", world.connection_id)
    response = await api.post()
    assert response.status_code == 409
    assert response.json() == {"detail": "no_connection"}
    assert await seed.count("sync_runs", world.tenant_id) == 0
    assert recorder.calls == []


@pytest.mark.parametrize("status", ["ready_for_review", "needs_revision"])
async def test_ac20_an_item_past_receipt_is_409_item_not_open(
    api: Api, seed: Seeder, world: World, recorder: Recorder, status: str
) -> None:
    await seed.run("UPDATE request_items SET status = $2 WHERE id = $1", world.item_id, status)
    response = await api.post()
    assert response.status_code == 409
    assert response.json() == {"detail": "item_not_open"}
    assert await seed.count("sync_runs", world.tenant_id) == 0
    assert recorder.calls == []


async def test_ac20_a_received_item_may_be_retrieved_again(
    api: Api, seed: Seeder, world: World, recorder: Recorder
) -> None:
    await seed.run("UPDATE request_items SET status = 'received' WHERE id = $1", world.item_id)
    assert (await api.post()).status_code == 202


async def test_ac20_an_archived_engagement_is_forbidden(
    api: Api, seed: Seeder, world: World, recorder: Recorder
) -> None:
    await seed.run("UPDATE engagements SET status = 'archived' WHERE id = $1", world.engagement_id)
    _assert_forbidden(await api.post())
    assert await seed.count("sync_runs", world.tenant_id) == 0
    assert recorder.calls == []


# --- POST: 422 -----------------------------------------------------------------------------------


ITEM = str(uuid.uuid4())
VALID = {"request_item_id": ITEM, "period_start": "2025-01-01", "period_end": "2025-12-31"}


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"period_start": "2025-01-01", "period_end": "2025-12-31"},
        {k: v for k, v in VALID.items() if k != "period_end"},
        {**VALID, "request_item_id": "not-a-uuid"},
        {**VALID, "period_start": "yesterday"},
        {**VALID, "period_start": "2025-12-31", "period_end": "2025-01-01"},
        {**VALID, "extra": DISTINCT_INPUT},
        {**VALID, "request_item_id": DISTINCT_INPUT},
    ],
)
async def test_ac20_an_invalid_body_is_422_and_never_echoes_the_input(
    api: Api, seed: Seeder, world: World, recorder: Recorder, body: Json
) -> None:
    response = await api.post(body=body)
    assert response.status_code == 422
    assert DISTINCT_INPUT not in response.text
    assert '"input"' not in response.text
    assert await seed.count("sync_runs", world.tenant_id) == 0
    assert recorder.calls == []


async def test_ac20_an_end_before_the_start_is_422(api: Api, recorder: Recorder) -> None:
    response = await api.post(body=api.body(period_start="2025-12-31", period_end="2025-01-01"))
    assert response.status_code == 422


async def test_ac20_a_one_day_period_is_accepted(api: Api, recorder: Recorder) -> None:
    response = await api.post(body=api.body(period_start="2025-06-30", period_end="2025-06-30"))
    assert response.status_code == 202


# --- POST: 503 and compensation ------------------------------------------------------------------


FAILURES = [
    RPCError("test-unreachable", RPCStatusCode.UNAVAILABLE, b""),
    OSError("test-connection refused"),
    RuntimeError("test-client closed"),
    ValueError("test-anything at all"),
]


@pytest.mark.parametrize("failure", FAILURES, ids=lambda f: type(f).__name__)
async def test_ac20_an_unreachable_temporal_is_503_and_ends_the_new_run_as_failed(
    api: Api, seed: Seeder, world: World, failure: BaseException
) -> None:
    _use(Recorder(failure))
    response = await api.post()
    assert response.status_code == 503
    assert response.json() == {"detail": "service unavailable"}
    assert str(failure) not in response.text
    [row] = await seed.rows("SELECT * FROM sync_runs WHERE tenant_id = $1", world.tenant_id)
    assert (row["status"], row["failure_code"]) == ("failed", "workflow_unavailable")
    assert row["finished_at"] is not None
    assert await seed.item_status(world.item_id) == "open"
    assert (await seed.actions(world.tenant_id)).count("sync_run.failed") == 1


async def test_ac20_after_a_503_a_new_trigger_makes_a_new_run_that_starts(
    api: Api, seed: Seeder, world: World
) -> None:
    _use(Recorder(OSError("test-down")))
    assert (await api.post()).status_code == 503
    spy = _use(Recorder())
    response = await api.post()
    assert response.status_code == 202
    assert len(spy.calls) == 1
    assert await seed.count("sync_runs", world.tenant_id) == 2


async def test_ac20_a_503_for_a_run_someone_else_created_leaves_that_run_running(
    api: Api, seed: Seeder, world: World
) -> None:
    _use(Recorder())
    first = cast(Json, (await api.post()).json())
    assert first["status"] == "running"
    colleague = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, colleague, "manager")
    _use(Recorder(OSError("test-down")))
    response = await api.post(colleague)
    assert response.status_code == 503
    assert response.json() == {"detail": "service unavailable"}
    row = await seed.run_row(uuid.UUID(cast(str, first["sync_run_id"])))
    assert (row["status"], row["failure_code"]) == ("running", None)
    assert await seed.count("sync_runs", world.tenant_id) == 1
    assert (await seed.actions(world.tenant_id)).count("sync_run.failed") == 0


# --- GET: the status endpoint --------------------------------------------------------------------


async def test_ac20_the_status_of_a_running_run(
    api: Api, world: World, recorder: Recorder
) -> None:
    started = cast(Json, (await api.post()).json())
    response = await api.get(started["sync_run_id"])
    assert response.status_code == 200
    found = cast(Json, response.json())
    _assert_shape(found)
    assert found == started
    assert found["finished_at"] is None


async def test_ac10_the_status_of_a_succeeded_run_has_both_timestamps_and_the_version(
    api: Api, world: World, temporal: Client, worker: Worker
) -> None:
    started = cast(Json, (await api.post()).json())
    done = await api.finished(started["sync_run_id"])
    assert done["status"] == "succeeded"
    assert done["evidence_version_id"] is not None
    assert done["started_at"] is not None
    assert done["finished_at"] is not None


@pytest.mark.parametrize("role", ["engagement_partner", "manager", "senior", "staff", "reviewer"])
async def test_ac20_every_member_may_read_the_status_including_a_reviewer(
    api: Api, seed: Seeder, world: World, recorder: Recorder, role: Role
) -> None:
    started = cast(Json, (await api.post()).json())
    member = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, member, role)
    response = await api.get(started["sync_run_id"], member)
    assert response.status_code == 200, response.text
    assert cast(Json, response.json())["sync_run_id"] == started["sync_run_id"]


async def test_ac20_a_firm_admin_who_is_not_a_member_is_forbidden_to_read_the_status(
    api: Api, seed: Seeder, world: World, recorder: Recorder
) -> None:
    started = cast(Json, (await api.post()).json())
    admin = await seed.person(world.tenant_id, firm_role="firm_admin")
    _assert_forbidden(await api.get(started["sync_run_id"], admin))


async def test_ac20_someone_with_no_relationship_may_not_read_the_status(
    api: Api, seed: Seeder, world: World, recorder: Recorder
) -> None:
    started = cast(Json, (await api.post()).json())
    stranger = await seed.person(world.tenant_id)
    _assert_forbidden(await api.get(started["sync_run_id"], stranger))


async def test_ac20_an_unknown_run_is_not_found(api: Api) -> None:
    _assert_not_found(await api.get(uuid.uuid4()))


async def test_ac20_a_run_of_another_engagement_is_not_found(
    api: Api, seed: Seeder, world: World, recorder: Recorder
) -> None:
    started = cast(Json, (await api.post()).json())
    other = await seed.engagement(world.tenant_id, world.entity_id, world.requester.user_id)
    await seed.member(other, world.requester, "staff")
    _assert_not_found(await api.get(started["sync_run_id"], engagement_id=other))


async def test_ac20_a_run_of_another_firm_is_not_found(
    api: Api, seed: Seeder, world: World, recorder: Recorder
) -> None:
    started = cast(Json, (await api.post()).json())
    other_firm = await seed.firm()
    person = await seed.person(other_firm)
    entity = await seed.entity(other_firm)
    engagement = await seed.engagement(other_firm, entity, person.user_id)
    await seed.member(engagement, person, "staff")
    _assert_not_found(await api.get(started["sync_run_id"], person, engagement_id=engagement))
    _assert_not_found(await api.get(started["sync_run_id"], person))


async def test_ac20_a_malformed_run_id_is_422(api: Api) -> None:
    assert (await api.get("not-a-uuid")).status_code == 422
