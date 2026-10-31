# ac-test-author: ayushkbhatia
"""P-11-T09 (ADR-078; TASK-2433; DEC-1481): the independent suite for
`evidence.api.record_generated`, written from the row and P-11 §4.2 AC6.1 to AC6.3, not from
the builder's tests.

The row's acceptance: "A rendered PDF's evidence fingerprint equals its render_hash, its pages
open masked in SHL-08, and no code path rewrites its bytes." AC6.1 adds Object Lock and "the
retention record type of the document kind (ADR P-14)". So, through the render job as the outbox
drives it: the file's evidence version carries channel `generated` and the render's hash as its
fingerprint; the stored object is locked at least until the firm's policy for the kind's record
type runs out (the default period when the kind names none); the version runs the upload steps
(words, PII scan, masked preview), so a W-2's SSN becomes a sealed region with its last four
only; bytes stored under another tenant are refused; and the database refuses UPDATE and DELETE
of the evidence version and the generated rows, for the app and the superuser alike.

**Found by this suite:** the render job stored every file with the default lock and never read
the kind's `retention_record_type` (DEC-1481).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import cast

import asyncpg
import pytest
from sqlalchemy import text
from types_boto3_s3 import S3Client

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.storage import s3_client
from abacus.kernel.uow import uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.evidence import api as evidence
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import (
    UPLOAD_VERSION,
    UploadInput,
    check_upload_content,
    masked_preview_upload,
    pii_scan_upload,
    words_upload,
)
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.reporting import api as c11
from abacus.modules.reporting import render_job
from abacus.modules.reporting.render.core import LocatedOutput, RenderInput, RenderOutput
from abacus.modules.reporting.render.regions import PageSize
from abacus_tools.synthetic.documents import w2_pdf

from .agent_tests.support import Seeder
from .test_p11t11_reporting_routes import (
    KIND,
    Probe,
    _draft,  # pyright: ignore[reportPrivateUsage] -- P-11-T11's harness
    _world,  # pyright: ignore[reportPrivateUsage] -- P-11-T11's harness
    engines,
    probe,
    seed,
)

__all__ = ["engines", "probe", "seed"]

MASTER = b"generated-independent-master-key-01234567"
BUCKET = f"evidence-p11t09-ind-{uuid.uuid4().hex[:12]}"

RENDERED = w2_pdf()  # the render's bytes: a page with an SSN on it
YEARS = 9  # the firm's policy for the record type, longer than the default period
DAY = timedelta(days=1)


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture(autouse=True)
def configured(raw: S3Client) -> Iterator[None]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, BUCKET)
    yield
    storage.reset_storage()
    reset_key_service()


@pytest.fixture
def kept(monkeypatch: pytest.MonkeyPatch, probe: Probe) -> Probe:
    """The probe kind, registered with a record type, rendering a W-2."""
    registered = c11.document_kind(KIND)
    monkeypatch.setattr(c11, "_REGISTRY", {})
    c11.register_document_kind(
        c11.DocumentKind(
            kind=KIND,
            layout="letter",
            variables_provider=registered.variables_provider,
            approval_provider=registered.approval_provider,
            retention_record_type="engagement_letter",
        )
    )

    def located(request: RenderInput) -> LocatedOutput:
        probe.renders += 1
        digest = hashlib.sha256(RENDERED).hexdigest()
        return LocatedOutput(RenderOutput(RENDERED, 1, digest, ()), (), (PageSize(612.0, 792.0),))

    monkeypatch.setattr(render_job, "render_located_isolated", located)
    return probe


async def _rendered(seed: Seeder) -> tuple[uuid.UUID, uuid.UUID]:
    """A draft rendered by the job as the outbox starts it; its tenant and evidence version."""
    partner, engagement, client = await _world(seed)
    document_id = await _draft(partner, engagement, client)
    await c11.SUBSCRIPTIONS[c11.RENDER_REQUESTED](
        OutboxEvent(
            event_id=uuid.uuid4(),
            tenant_id=partner.tenant_id,
            event_type=c11.RENDER_REQUESTED,
            payload={"generated_document_id": str(document_id), "version_no": 1},
        )
    )
    version = await seed.value(
        "SELECT evidence_version_id FROM generated_document_files WHERE tenant_id = $1",
        partner.tenant_id,
    )
    assert version is not None
    return partner.tenant_id, cast(uuid.UUID, version)


def _locked_until(client: S3Client, key: str, version_id: str) -> datetime:
    found = client.get_object_retention(Bucket=BUCKET, Key=key, VersionId=version_id)
    return found["Retention"]["RetainUntilDate"]  # pyright: ignore[reportTypedDictNotRequiredAccess] -- a locked object always answers it


async def _stored(seed: Seeder, version: uuid.UUID) -> asyncpg.Record:
    return (
        await seed.rows(
            "SELECT fingerprint, channel, storage_key, storage_version_id FROM evidence_versions "
            "WHERE id = $1",
            version,
        )
    )[0]


async def test_ac61_a_render_is_locked_for_its_kinds_record_type(
    seed: Seeder, raw: S3Client, kept: Probe
) -> None:
    partner, engagement, client = await _world(seed)
    await seed.as_actor(  # the policy's version row is the tenant's (forced RLS)
        partner.tenant_id,
        ("human", str(partner.user_id)),
        "INSERT INTO retention_policies (tenant_id, record_type, service_line, firm_years, "
        "clock_start_event, updated_by) VALUES ($1, 'engagement_letter', 'any', $2, "
        "'report_release', 'p11t09-independent')",
        partner.tenant_id,
        YEARS,
    )
    before = datetime.now(UTC)
    document_id = await _draft(partner, engagement, client)
    await c11.SUBSCRIPTIONS[c11.RENDER_REQUESTED](
        OutboxEvent(
            event_id=uuid.uuid4(),
            tenant_id=partner.tenant_id,
            event_type=c11.RENDER_REQUESTED,
            payload={"generated_document_id": str(document_id), "version_no": 1},
        )
    )
    files = await seed.rows(
        "SELECT render_hash, evidence_version_id FROM generated_document_files "
        "WHERE tenant_id = $1",
        partner.tenant_id,
    )
    assert len(files) == 1
    row = await _stored(seed, cast(uuid.UUID, files[0]["evidence_version_id"]))
    assert row["channel"] == "generated"
    assert row["fingerprint"] == bytes(files[0]["render_hash"]).hex()
    assert row["fingerprint"] == hashlib.sha256(RENDERED).hexdigest()
    until = _locked_until(raw, str(row["storage_key"]), str(row["storage_version_id"]))
    assert until >= before + timedelta(days=YEARS * 365.25) - DAY


async def test_ac61_without_a_policy_the_default_period_holds(
    seed: Seeder, raw: S3Client, kept: Probe
) -> None:
    before = datetime.now(UTC)
    _, version = await _rendered(seed)
    row = await _stored(seed, version)
    until = _locked_until(raw, str(row["storage_key"]), str(row["storage_version_id"]))
    assert until >= before + timedelta(days=settings().evidence_retention_days) - DAY


async def test_ac53_the_pages_run_the_upload_steps_and_open_masked(
    seed: Seeder, kept: Probe
) -> None:
    tenant, version = await _rendered(seed)
    announced = await seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = "
        "'evidence_version.created' AND payload ->> 'evidence_version_id' = $2",
        tenant,
        str(version),
    )
    assert announced == 1  # what starts the upload run for an engagement-scoped file
    given = UploadInput(str(tenant), UPLOAD_VERSION, str(version))
    await extract_upload(given)
    await check_upload_content(given)
    await words_upload(given)
    assert await pii_scan_upload(given) >= 1
    assert await masked_preview_upload(given) not in ("none", "withdrawn")
    regions = await seed.rows(
        "SELECT kind, last4, value_sealed FROM pii_regions WHERE evidence_version_id = $1", version
    )
    ssn = [r for r in regions if r["last4"] == "6081"]
    assert ssn and all(r["value_sealed"] is not None for r in ssn)
    assert all("000-00-6081" not in str(r["last4"]) for r in regions)


async def test_ac61_bytes_stored_for_another_tenant_are_refused(seed: Seeder) -> None:
    partner, engagement, client = await _world(seed)
    other = await seed.firm()
    stored = await evidence.store_generated(other, RENDERED)
    digest = hashlib.sha256(RENDERED).hexdigest()
    with pytest.raises(storage.IntegrityError):
        async with uow(TenantContext(partner.tenant_id, "system", "reporting.render")) as tx:
            await evidence.record_generated(
                tx,
                tenant_id=partner.tenant_id,
                client_id=client,
                engagement_id=engagement,
                work_item_id=None,
                file=evidence.GeneratedFile(
                    stored=stored,
                    render_hash=digest,
                    media_type="application/pdf",
                    title="Probe",
                    provenance="probe",
                ),
                requested_by=partner.user_id,
            )
    assert (
        await seed.value(
            "SELECT count(*) FROM evidence_versions WHERE tenant_id = $1", partner.tenant_id
        )
        == 0
    )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE evidence_versions SET size_bytes = 1 WHERE id = $1",
        "DELETE FROM evidence_versions WHERE id = $1",
        "UPDATE generated_document_files SET page_count = 2 WHERE evidence_version_id = $1",
        "DELETE FROM generated_document_files WHERE evidence_version_id = $1",
        "UPDATE generated_document_versions SET mode = 'final' WHERE id = "
        "(SELECT version_id FROM generated_document_files WHERE evidence_version_id = $1)",
        "DELETE FROM generated_document_versions WHERE id = "
        "(SELECT version_id FROM generated_document_files WHERE evidence_version_id = $1)",
    ],
)
async def test_ac63_no_role_rewrites_or_deletes_a_generated_version(
    seed: Seeder, kept: Probe, statement: str
) -> None:
    tenant, version = await _rendered(seed)
    with pytest.raises(asyncpg.PostgresError):  # the superuser: triggers hold for every role
        await seed.run(statement, version)
    with pytest.raises(Exception):  # noqa: B017 -- the app role; its error class varies by guard
        async with uow(TenantContext(tenant, "system", "reporting.render")) as tx:
            await tx.session.execute(text(statement.replace("$1", ":v")), {"v": version})
    assert (await _stored(seed, version))["fingerprint"] == hashlib.sha256(RENDERED).hexdigest()
