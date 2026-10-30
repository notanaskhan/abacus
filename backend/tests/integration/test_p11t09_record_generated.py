"""P-11-T09 (TASK-2409; P-11 §4.2; C11 v1) against Postgres and the object store: rendered bytes
filed as an immutable evidence version.

The row's acceptance: a rendered PDF's evidence fingerprint equals its render_hash, its pages
open masked in SHL-08 (an engagement-scoped file announces `evidence_version.created`, which
starts the words, PII scan and masked preview steps as for uploads), and no code path rewrites
its bytes (bytes that are not the render's are refused; the version is insert-only).

The kind registered is a probe; the "PDF" is synthetic bytes (the renderer is P-11-T07's).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator, Mapping
from typing import cast

import pytest
from types_boto3_s3 import S3Client

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.storage import s3_client
from abacus.kernel.uow import uow
from abacus.modules.evidence import api as evidence
from abacus.modules.evidence import storage
from abacus.modules.reporting import api as c11
from abacus.modules.reporting import documents as docs
from abacus.modules.reporting import files as rendered

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

MASTER = b"generated-test-master-key-0123456789ab"
BUCKET = f"evidence-generated-{uuid.uuid4().hex[:12]}"
KIND = "notice_response"
PDF = b"%PDF-1.7\n% probe render\n"


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


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> object:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture(autouse=True)
def kind(monkeypatch: pytest.MonkeyPatch) -> None:
    async def provider(owner: c11.OwnerRef, scope: c11.RenderScope) -> Mapping[str, str]:
        return {"client.name": "Probe client"}

    async def approval(ref: c11.ApprovalRef) -> tuple[uuid.UUID, str] | None:
        return None

    async def keys(session: object, version_id: uuid.UUID) -> tuple[str, ...]:
        return ("client.name",)

    monkeypatch.setattr(docs, "report_template_variable_keys", keys)
    monkeypatch.setattr(c11, "_REGISTRY", {})
    c11.register_document_kind(
        c11.DocumentKind(
            kind=KIND, layout="letter", variables_provider=provider, approval_provider=approval
        )
    )


async def _drafted(seed: Seeder) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    tenant = await seed.firm()
    person = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, person.user_id)
    client = cast(
        uuid.UUID, await seed.value("SELECT id FROM clients WHERE tenant_id = $1", tenant)
    )
    ctx = TenantContext(tenant, "human", str(person.user_id))
    async with uow(ctx) as tx:
        ticket = await c11.render(
            tx,
            c11.RenderRequest(
                kind=KIND,
                owner_ref=c11.OwnerRef("notice", uuid.uuid4()),
                scope=c11.RenderScope(client_id=client, engagement_id=engagement),
                template_version_id=uuid.uuid4(),
                requested_by=c11.Requester("human", user_id=person.user_id),
            ),
        )
    return tenant, person.user_id, ticket.generated_document_id, engagement


async def test_ac1_the_evidence_fingerprint_equals_the_render_hash(seed: Seeder) -> None:
    tenant, user, document_id, _ = await _drafted(seed)
    render_hash = hashlib.sha256(PDF).hexdigest()
    stored = await evidence.store_generated(tenant, PDF)
    async with uow(TenantContext(tenant, "system", "reporting.render")) as tx:
        version_id = await rendered.record_file(
            tx,
            document_id=document_id,
            version_no=1,
            file_format="pdf",
            stored=stored,
            render_hash=render_hash,
            page_count=1,
            title="Probe notice response",
            requested_by=user,
        )
    row = await seed.rows(
        "SELECT fingerprint, channel, method, engagement_id FROM evidence_versions WHERE id = $1",
        version_id,
    )
    assert [(r["fingerprint"], r["channel"], r["method"]) for r in row] == [
        (render_hash, "generated", "uploaded")
    ]
    files = await seed.rows(
        "SELECT render_hash, evidence_version_id, byte_size FROM generated_document_files"
    )
    assert [(bytes(f["render_hash"]).hex(), f["evidence_version_id"]) for f in files] == [
        (render_hash, version_id)
    ]
    assert files[0]["byte_size"] == len(PDF)
    # SHL-08's masked pages follow from the upload pipeline, which this event starts.
    announced = await seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = "
        "'evidence_version.created' AND payload ->> 'evidence_version_id' = $2",
        tenant,
        str(version_id),
    )
    assert announced == 1
    assert await storage.get(tenant, stored) == PDF


async def test_ac1_bytes_that_are_not_the_renders_are_refused(seed: Seeder) -> None:
    tenant, user, document_id, _ = await _drafted(seed)
    stored = await evidence.store_generated(tenant, PDF + b"tampered")
    with pytest.raises(evidence.RenderHashMismatch):
        async with uow(TenantContext(tenant, "system", "reporting.render")) as tx:
            await rendered.record_file(
                tx,
                document_id=document_id,
                version_no=1,
                file_format="pdf",
                stored=stored,
                render_hash=hashlib.sha256(PDF).hexdigest(),
                page_count=1,
                title="Probe notice response",
                requested_by=user,
            )
    assert await seed.value("SELECT count(*) FROM generated_document_files") == 0


async def test_ac3_no_path_rewrites_a_generated_version(seed: Seeder) -> None:
    tenant, user, document_id, _ = await _drafted(seed)
    stored = await evidence.store_generated(tenant, PDF)
    ctx = TenantContext(tenant, "system", "reporting.render")
    async with uow(ctx) as tx:
        version_id = await rendered.record_file(
            tx,
            document_id=document_id,
            version_no=1,
            file_format="pdf",
            stored=stored,
            render_hash=hashlib.sha256(PDF).hexdigest(),
            page_count=1,
            title="Probe notice response",
            requested_by=user,
        )
    from sqlalchemy import text

    with pytest.raises(Exception):  # noqa: B017 -- the database refuses; its error class varies
        async with uow(ctx) as tx:
            await tx.session.execute(
                text("UPDATE evidence_versions SET size_bytes = 1 WHERE id = :v"),
                {"v": version_id},
            )
    with pytest.raises(Exception):  # noqa: B017 -- insert-only for the app role
        async with uow(ctx) as tx:
            await tx.session.execute(
                text("UPDATE generated_document_files SET page_count = 2"),
            )
