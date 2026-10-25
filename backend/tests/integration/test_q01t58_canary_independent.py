"""Q-01-T58 (ADR-078): acceptance tests for the canary (Q-01-T30), written from the Q-01 F6 text
before the workflow existed.

F6: "Given CanaryWorkflow on 'Canary & Co' (firms.synthetic = true), when it runs every 15
minutes, then it creates a request item, uploads a synthetic PDF, waits for scan, extraction and
preview, runs the screener on the route the environment's boundary allows and fails the run
unless every flag it gets back carries a code-verified citation or is shown Uncited (INV-2),
observes the outbox event, and sends a reminder to success@simulator.amazonses.com. Two
consecutive failures page." T58's acceptance: the canary "fails a run with an uncited flag,
writes no row or object outside synthetic tenants, and pages on the second consecutive failure
only", with a boundary-appropriate screener route.

The workflow runs on a real Temporal dev server with a scripted probe and a recording heartbeat;
the synthetic-only rule is also proved on the real service probe against Postgres and the S3
gateway. Same-session authorship (solo lane): independence is nominal, see TASK-1234.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from datetime import timedelta

import pytest
from temporalio.client import Client, ScheduleActionExecutionStartWorkflow
from temporalio.worker import Worker
from types_boto3_s3 import S3Client

from abacus.kernel import dispatch
from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import configure_engine, configure_relay_engine, dispose_engine
from abacus.kernel.dispatch import PlatformSchedule, queue_for
from abacus.kernel.storage import s3_client
from abacus.kernel.temporal import configure_temporal_client, data_converter
from abacus.modules.evidence import storage
from abacus.modules.platform import canary as canary_module
from abacus.modules.platform.api import (
    CANARY_ACTIVITIES,
    CanaryFlag,
    CanaryInput,
    CanaryNotSynthetic,
    CanaryPlan,
    CanaryResult,
    CanaryScreen,
    CanaryStepFailed,
    CanaryWorkflow,
    RecordingHeartbeat,
    canary_workflow_id,
    configure_canary_probe,
    configure_heartbeat,
)
from abacus.worker.canary_probe import ServiceProbe

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

QUEUE = f"t58-{uuid.uuid4().hex[:8]}"
MASTER = b"canary-test-master-key-0123456789abcdef0"
BUCKET = f"canary-{uuid.uuid4().hex[:12]}"
STEPS = (
    "prepare",
    "create_item",
    "upload",
    "wait_processing",
    "screen",
    "observe_outbox",
    "send_simulator",
)


def _verified(category: str = "balance") -> CanaryFlag:
    return CanaryFlag(category, (True, False), shown_uncited=False)


@dataclass
class ScriptedProbe:
    """The canary's steps, scripted: which step fails (and how), what the screener returns."""

    fail_at: str | None = None
    failure: Exception = field(default_factory=lambda: CanaryStepFailed("scripted"))
    screened: CanaryScreen = field(
        default_factory=lambda: CanaryScreen("fake", ran=False, flags=())
    )
    calls: list[str] = field(default_factory=list[str])

    def _step(self, name: str) -> None:
        self.calls.append(name)
        if self.fail_at == name:
            raise self.failure

    async def prepare(self, tenant_id: uuid.UUID) -> CanaryPlan:
        self._step("prepare")
        return CanaryPlan(str(tenant_id), str(uuid.uuid4()), str(uuid.uuid4()))

    async def create_item(self, plan: CanaryPlan) -> uuid.UUID:
        self._step("create_item")
        return uuid.uuid4()

    async def upload(self, plan: CanaryPlan, item_id: uuid.UUID) -> uuid.UUID:
        self._step("upload")
        return uuid.uuid4()

    async def wait_processing(
        self, plan: CanaryPlan, item_id: uuid.UUID, version_id: uuid.UUID
    ) -> None:
        self._step("wait_processing")

    async def screen(
        self, plan: CanaryPlan, item_id: uuid.UUID, version_id: uuid.UUID
    ) -> CanaryScreen:
        self._step("screen")
        return self.screened

    async def observe_outbox(self, plan: CanaryPlan, version_id: uuid.UUID) -> None:
        self._step("observe_outbox")

    async def send_simulator(self, plan: CanaryPlan) -> None:
        self._step("send_simulator")


@pytest.fixture
def probe() -> Iterator[ScriptedProbe]:
    scripted = ScriptedProbe()
    configure_canary_probe(scripted)
    yield scripted
    configure_canary_probe(None)


@pytest.fixture
def pager() -> Iterator[RecordingHeartbeat]:
    recording = RecordingHeartbeat()
    configure_heartbeat(recording)
    yield recording
    configure_heartbeat(None)


@pytest.fixture
async def temporal(temporal_target: str, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Client]:
    monkeypatch.setenv("ABACUS_TEMPORAL_TASK_QUEUE", QUEUE)
    settings.cache_clear()
    client = await Client.connect(temporal_target, data_converter=data_converter())
    configure_temporal_client(client)
    yield client
    configure_temporal_client(None)
    settings.cache_clear()


@pytest.fixture
async def worker(temporal: Client) -> AsyncIterator[None]:
    async with Worker(
        temporal,
        task_queue=queue_for("time_sensitive"),
        workflows=[CanaryWorkflow],
        activities=list(CANARY_ACTIVITIES),  # type: ignore[arg-type]  # activity defs
    ):
        yield


async def _run(temporal: Client, tenant: str | None = None) -> CanaryResult:
    tenant = tenant or str(uuid.uuid4())
    return await temporal.execute_workflow(
        CanaryWorkflow.run,
        CanaryInput(tenant),
        id=f"{canary_workflow_id(tenant)}-{uuid.uuid4().hex[:6]}",
        task_queue=queue_for("time_sensitive"),
        execution_timeout=timedelta(minutes=2),
    )


# --- INV-2: a flag without a code-verified citation fails the run ----------------------------


async def test_ac_a_run_with_an_uncited_flag_fails_at_the_screener(
    temporal: Client, worker: None, probe: ScriptedProbe, pager: RecordingHeartbeat
) -> None:
    probe.screened = CanaryScreen(
        "fake", ran=True, flags=(_verified(), CanaryFlag("cutoff", (False,), shown_uncited=False))
    )
    result = await _run(temporal)
    assert (result.passed, result.failed_step, result.code) == (False, "screen", "uncited_flag")
    assert probe.calls == list(STEPS[:5])  # nothing after the screener ran


async def test_ac_a_flag_whose_citation_was_never_verified_fails_the_run(
    temporal: Client, worker: None, probe: ScriptedProbe, pager: RecordingHeartbeat
) -> None:
    probe.screened = CanaryScreen(
        "fake", ran=True, flags=(CanaryFlag("balance", (None,), shown_uncited=True),)
    )
    result = await _run(temporal)
    assert (result.passed, result.code) == (False, "uncited_flag")


async def test_ac_verified_or_uncited_flags_pass_and_every_step_runs(
    temporal: Client, worker: None, probe: ScriptedProbe, pager: RecordingHeartbeat
) -> None:
    probe.screened = CanaryScreen(
        "fake",
        ran=True,
        flags=(_verified(), CanaryFlag("cutoff", (False,), shown_uncited=True)),
    )
    result = await _run(temporal)
    assert result.passed, result
    assert (result.failed_step, result.code, result.route) == (None, None, "fake")
    assert probe.calls == list(STEPS)
    assert pager.calls == ["beat"]


# --- Synthetic only ---------------------------------------------------------------------------


async def test_ac_a_firm_that_is_not_synthetic_stops_the_run_before_any_write(
    temporal: Client, worker: None, probe: ScriptedProbe, pager: RecordingHeartbeat
) -> None:
    probe.fail_at = "prepare"
    probe.failure = CanaryNotSynthetic("not synthetic")
    result = await _run(temporal)
    assert (result.passed, result.failed_step, result.code) == (False, "prepare", "not_synthetic")
    assert probe.calls == ["prepare"]  # one attempt, then nothing: no item, no upload, no mail


# --- The route the boundary allows ------------------------------------------------------------


@pytest.mark.parametrize(
    ("boundary", "screened", "code"),
    [
        ("synthetic_only", CanaryScreen("fake", ran=False, flags=()), None),
        ("synthetic_only", CanaryScreen("fake", ran=True, flags=(_verified(),)), None),
        ("synthetic_only", CanaryScreen("bedrock", ran=True, flags=()), "route_not_allowed"),
        ("synthetic_only", CanaryScreen("direct", ran=True, flags=()), "route_not_allowed"),
        ("client_data", CanaryScreen("bedrock", ran=True, flags=(_verified(),)), None),
        ("client_data", CanaryScreen("fake", ran=True, flags=()), "route_not_allowed"),
        ("client_data", CanaryScreen("bedrock", ran=False, flags=()), "screener_not_run"),
    ],
)
async def test_ac_the_screener_runs_only_on_the_route_the_boundary_allows(
    temporal: Client,
    worker: None,
    probe: ScriptedProbe,
    pager: RecordingHeartbeat,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
    screened: CanaryScreen,
    code: str | None,
) -> None:
    monkeypatch.setattr(canary_module, "boundary", lambda: boundary)
    probe.screened = screened
    result = await _run(temporal)
    assert (result.passed, result.code) == (code is None, code)
    if code is not None:
        assert result.failed_step == "screen"


# --- Paging: the second consecutive failure, once ---------------------------------------------


async def _trigger_and_wait(temporal: Client, schedule_id: str, runs: int) -> CanaryResult:
    handle = temporal.get_schedule_handle(schedule_id)
    await handle.trigger()
    for _ in range(300):
        recent = (await handle.describe()).info.recent_actions
        if len(recent) >= runs:
            newest = max(recent, key=lambda a: a.started_at).action
            assert isinstance(newest, ScheduleActionExecutionStartWorkflow)
            return await temporal.get_workflow_handle(
                newest.workflow_id, result_type=CanaryResult
            ).result()
        await asyncio.sleep(0.1)
    raise AssertionError(f"run {runs} of {schedule_id} did not start")


async def test_ac_pages_on_the_second_consecutive_failure_only(
    temporal: Client, worker: None, probe: ScriptedProbe, pager: RecordingHeartbeat
) -> None:
    tenant = str(uuid.uuid4())
    job = PlatformSchedule(
        id=canary_workflow_id(tenant),
        workflow=CanaryWorkflow,
        every=timedelta(minutes=15),
        note="t58",
        arg=CanaryInput(tenant),
    )
    await dispatch.schedule(job)
    await dispatch.pause(job.id, note="t58: triggered by hand only")
    try:
        script = ["fail", "fail", "fail", "pass", "fail", "fail"]
        paged: list[bool] = []
        for n, outcome in enumerate(script, start=1):
            probe.fail_at = "observe_outbox" if outcome == "fail" else None
            probe.failure = CanaryStepFailed("outbox_lag")
            result = await _trigger_and_wait(temporal, job.id, n)
            assert result.passed == (outcome == "pass")
            paged.append(result.paged)
        assert paged == [False, True, False, False, False, True]
        assert pager.calls == [
            "fail:observe_outbox:outbox_lag",  # run 2
            "beat",  # run 4
            "fail:observe_outbox:outbox_lag",  # run 6
        ]
    finally:
        await dispatch.delete(job.id)


# --- The real probe writes only in the synthetic firm -----------------------------------------


@pytest.fixture
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    configure_relay_engine(migrated_db.relay_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture(scope="module")
def bucket_client(s3_settings: dict[str, str]) -> S3Client:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True)
    return client


@pytest.fixture
def bucket(bucket_client: S3Client) -> Iterator[S3Client]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(bucket_client, BUCKET)
    yield bucket_client
    storage.reset_storage()
    reset_key_service()


@dataclass(frozen=True)
class CanaryFirm:
    tenant_id: uuid.UUID
    staff: Person
    engagement_id: uuid.UUID


async def _firm(seed: Seeder, *, synthetic: bool) -> CanaryFirm:
    tenant = await seed.firm()
    if synthetic:
        await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    staff = await seed.person(tenant)
    engagement = await seed.engagement(tenant, await seed.entity(tenant), staff.user_id)
    await seed.member(engagement, staff, "manager")
    return CanaryFirm(tenant, staff, engagement)


def _configure(monkeypatch: pytest.MonkeyPatch, firm: CanaryFirm) -> None:
    monkeypatch.setenv("ABACUS_CANARY_TENANT_ID", str(firm.tenant_id))
    monkeypatch.setenv("ABACUS_CANARY_STAFF_USER_ID", str(firm.staff.user_id))
    monkeypatch.setenv("ABACUS_CANARY_ENGAGEMENT_ID", str(firm.engagement_id))
    settings.cache_clear()


_COUNTS = (
    "SELECT (SELECT count(*) FROM request_items WHERE tenant_id = $1), "
    "(SELECT count(*) FROM evidence_versions WHERE tenant_id = $1), "
    "(SELECT count(*) FROM audit_events WHERE tenant_id = $1), "
    "(SELECT count(*) FROM outbox WHERE tenant_id = $1)"
)


async def _counts(seed: Seeder, tenant: uuid.UUID) -> tuple[int, ...]:
    [row] = await seed.rows(_COUNTS, tenant)
    return tuple(int(v) for v in row.values())


async def test_ac_the_service_probe_refuses_a_firm_that_is_not_synthetic(
    engines: None, migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    real = await _firm(seed, synthetic=False)
    _configure(monkeypatch, real)
    before = await _counts(seed, real.tenant_id)
    with pytest.raises(CanaryNotSynthetic):
        await ServiceProbe().prepare(real.tenant_id)
    assert await _counts(seed, real.tenant_id) == before


async def test_ac_the_service_probe_writes_only_in_the_synthetic_firm(
    engines: None,
    bucket: S3Client,
    migrated_db: MigratedDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    canary = await _firm(seed, synthetic=True)
    bystander = await _firm(seed, synthetic=False)
    _configure(monkeypatch, canary)
    before = await _counts(seed, bystander.tenant_id)
    probe = ServiceProbe()
    plan = await probe.prepare(canary.tenant_id)
    item = await probe.create_item(plan)
    version = await probe.upload(plan, item)
    assert await _counts(seed, bystander.tenant_id) == before
    grown = await _counts(seed, canary.tenant_id)
    assert grown[0] == 1 and grown[1] == 1  # one item, one version, in the canary firm
    owners = await seed.rows(
        "SELECT DISTINCT tenant_id FROM evidence_versions WHERE id = $1", version
    )
    assert [r["tenant_id"] for r in owners] == [canary.tenant_id]
    keys = [o.get("Key", "") for o in bucket.list_objects_v2(Bucket=BUCKET).get("Contents", [])]
    assert keys and all(k.startswith(f"tenants/{canary.tenant_id}/") for k in keys)
