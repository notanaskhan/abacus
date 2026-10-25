"""Q-01-T30: the canary's service probe against Postgres and the S3 gateway. Each step runs as the
canary staff member through the product's own services: the synthetic PDF is accepted and
scanned, waiting ends once the upload is extracted and previewed (here the processing worker's
activities are run by hand), the upload's outbox event is seen once the relay has published it,
the screener step reports the fake route as not run (DEC-358), and the reminder to the SES
simulator goes the way a synthetic firm's mail goes (the sink)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
from types_boto3_s3 import S3Client

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import configure_engine, configure_relay_engine, dispose_engine
from abacus.kernel.storage import s3_client
from abacus.kernel.uow.relay import RoutingPublisher, event_state, relay_once
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import UPLOAD_VERSION, UploadInput, process_upload
from abacus.modules.evidence.processing import preview_upload
from abacus.modules.platform.api import (
    CanaryPlan,
    CanaryScreen,
    CanaryStepFailed,
)
from abacus.worker import canary_probe
from abacus.worker.canary_probe import ServiceProbe, canary_pdf

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

MASTER = b"canary-probe-master-key-0123456789abcde"
BUCKET = f"canary-probe-{uuid.uuid4().hex[:12]}"


@pytest.fixture(autouse=True)
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


@pytest.fixture(autouse=True)
def bucket(bucket_client: S3Client) -> Iterator[S3Client]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(bucket_client, BUCKET)
    yield bucket_client
    storage.reset_storage()
    reset_key_service()


@pytest.fixture
async def plan(migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch) -> CanaryPlan:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    staff = await seed.person(tenant)
    engagement = await seed.engagement(tenant, await seed.entity(tenant), staff.user_id)
    await seed.member(engagement, staff, "manager")
    monkeypatch.setenv("ABACUS_CANARY_TENANT_ID", str(tenant))
    monkeypatch.setenv("ABACUS_CANARY_STAFF_USER_ID", str(staff.user_id))
    monkeypatch.setenv("ABACUS_CANARY_ENGAGEMENT_ID", str(engagement))
    settings.cache_clear()
    return await ServiceProbe().prepare(tenant)


def test_the_synthetic_statement_is_a_pdf_unique_to_each_run() -> None:
    first, second = canary_pdf("a" * 32), canary_pdf("b" * 32)
    assert first.startswith(b"%PDF-1.4") and first.rstrip().endswith(b"%%EOF")
    assert first != second


async def test_prepare_refuses_a_firm_other_than_the_configured_canary(plan: CanaryPlan) -> None:
    with pytest.raises(CanaryStepFailed) as refused:
        await ServiceProbe().prepare(uuid.uuid4())
    assert refused.value.code == "not_configured"


async def test_waiting_ends_once_the_upload_is_extracted_and_previewed(
    plan: CanaryPlan, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(canary_probe, "PROCESSING_SECONDS", 0.0)
    probe = ServiceProbe()
    item = await probe.create_item(plan)
    version = await probe.upload(plan, item)
    with pytest.raises(CanaryStepFailed) as waiting:
        await probe.wait_processing(plan, item, version)  # nothing processed it yet
    assert waiting.value.code == "processing_timeout"
    given = UploadInput(plan.tenant_id, UPLOAD_VERSION, str(version))
    assert await process_upload(given) == "extracted"
    await preview_upload(given)
    await probe.wait_processing(plan, item, version)


async def test_the_outbox_event_is_seen_once_the_relay_has_published_it(
    plan: CanaryPlan, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(canary_probe, "OUTBOX_SECONDS", 0.0)
    probe = ServiceProbe()
    version = await probe.upload(plan, await probe.create_item(plan))
    tenant = uuid.UUID(plan.tenant_id)
    state = await event_state(
        tenant, "evidence.uploaded", field="evidence_version_id", value=str(version)
    )
    assert state == "pending"
    with pytest.raises(CanaryStepFailed) as lagging:
        await probe.observe_outbox(plan, version)
    assert lagging.value.code == "outbox_lag"
    for _ in range(20):  # every pending event of every test firm, until ours is out
        await relay_once(RoutingPublisher({}))
        if (
            await event_state(
                tenant, "evidence.uploaded", field="evidence_version_id", value=str(version)
            )
            == "published"
        ):
            break
    await probe.observe_outbox(plan, version)


async def test_an_upload_that_never_happened_has_no_event(plan: CanaryPlan) -> None:
    with pytest.raises(CanaryStepFailed) as absent:
        await ServiceProbe().observe_outbox(plan, uuid.uuid4())
    assert absent.value.code == "event_absent"


async def test_the_screener_step_on_the_fake_route_reports_it_did_not_run(
    plan: CanaryPlan,
) -> None:
    probe = ServiceProbe()
    item = await probe.create_item(plan)
    version = await probe.upload(plan, item)
    assert await probe.screen(plan, item, version) == CanaryScreen("fake", ran=False, flags=())


async def test_the_reminder_goes_the_way_a_synthetic_firms_mail_goes(plan: CanaryPlan) -> None:
    await ServiceProbe().send_simulator(plan)  # the sink takes it: no error
