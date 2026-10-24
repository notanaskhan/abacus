# ac-test-author: ayushkbhatia
"""P-06-T18 (ADR-162 §2, §5, §6; DEC-297): detached-key storage for client-channel uploads.

"A client upload opens only through its key row and firm uploads keep the content-addressed path
unchanged." A client's own upload is stored at `tenants/<tenant>/v/<version>` in envelope ABE2,
its wrapped data key in `evidence_object_keys`; its derived records are sealed under the same key
beside it; destroying the key leaves nothing anyone can open. Acceptance retains the key one-way
and the database refuses to clear a retained key; only the purge's definer may destroy one.

Boundary: `create_app()` over HTTP as a client admin and the firm's manager, the migrated
Postgres (app role and superuser), the compose S3 image with Object Lock, and the processing
activities on the stored version.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Final, cast

import asyncpg
import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from types_boto3_s3 import S3Client

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import UPLOAD_VERSION, UploadInput, check_upload_content
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.evidence.processing import preview_upload
from abacus_tools.synthetic.documents import bank_statement_pdf

from .support import Net, Person, Seeder, Site

BUCKET: Final = "p06t18-detached-keys"
MASTER: Final = b"p06t18-detached-keys-master-key-0123456789"
PDF: Final = "application/pdf"


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
def wired(raw: S3Client) -> Iterator[None]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, BUCKET)
    yield
    storage.reset_storage()
    reset_key_service()


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    manager: Person
    client: Person
    site: Site
    raw: S3Client

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def base(self) -> str:
        return f"/v1/engagements/{self.site.engagement_id}"

    async def upload(self, who: Person, content: bytes) -> httpx.Response:
        return await self.net.http.post(
            f"{self.base}/request-items/{self.site.item_id}/uploads",
            params={"filename": "statement.pdf"},
            content=content,
            headers={**self.net.headers(who), "Content-Type": PDF},
        )

    async def version(self, version_id: uuid.UUID) -> asyncpg.Record:
        rows = await self.seed.rows(
            "SELECT storage_mode, storage_key, storage_version_id, fingerprint, size_bytes "
            "FROM evidence_versions WHERE id = $1",
            version_id,
        )
        return rows[0]

    async def key_row(self, version_id: uuid.UUID) -> asyncpg.Record | None:
        rows = await self.seed.rows(
            "SELECT * FROM evidence_object_keys WHERE evidence_version_id = $1", version_id
        )
        return rows[0] if rows else None

    def stored(self, row: asyncpg.Record) -> storage.StoredObject:
        return storage.StoredObject(
            str(row["storage_key"]),
            str(row["storage_version_id"]),
            str(row["fingerprint"]),
            int(row["size_bytes"]),
        )

    async def processed(self, version_id: uuid.UUID) -> None:
        given = UploadInput(str(self.tenant_id), UPLOAD_VERSION, str(version_id))
        await extract_upload(given)
        await check_upload_content(given)
        await preview_upload(given)


@pytest.fixture
async def firm(net: Net, seed: Seeder, raw: S3Client) -> Firm:
    tenant_id = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'uploads.processing', 'true', 'test-seed', 'P-06-T18')",
        tenant_id,
    )
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, "Feld")
    manager = await seed.person(tenant_id)
    await seed.member(site, manager, "manager")
    client = await seed.client_contact(site, "client_admin")
    return Firm(net, tenant_id, manager, client, site, raw)


async def test_t18_a_client_upload_is_its_own_object_sealed_under_its_own_key(firm: Firm) -> None:
    content = bank_statement_pdf(last4="1181")
    response = await firm.upload(firm.client, content)
    assert response.status_code == 201, response.text
    version_id = uuid.UUID(response.json()["evidence_version_id"])
    row = await firm.version(version_id)
    assert row["storage_mode"] == "detached_key"
    assert row["storage_key"] == f"tenants/{firm.tenant_id}/v/{version_id}"
    key = await firm.key_row(version_id)
    assert key is not None
    assert key["wrapped_key"] is not None
    assert (key["retained_at"], key["destroyed_at"]) == (None, None)
    sealed = firm.raw.get_object(
        Bucket=BUCKET, Key=str(row["storage_key"]), VersionId=str(row["storage_version_id"])
    )["Body"].read()
    assert sealed[:4] == b"ABE2"  # envelope v2: no key inside the object
    assert bytes(cast(bytes, key["wrapped_key"])) not in sealed
    # It opens, through the key row, for the people allowed to read it.
    assert await storage.get(firm.tenant_id, firm.stored(row)) == content
    download = await firm.net.http.get(
        f"{firm.base}/evidence-versions/{version_id}/content",
        headers=firm.net.headers(firm.manager),
    )
    assert download.status_code == 200, download.text
    assert download.content == content


async def test_t18_firm_uploads_keep_the_content_addressed_path(firm: Firm) -> None:
    content = bank_statement_pdf(last4="2282")
    response = await firm.upload(firm.manager, content)
    assert response.status_code == 201, response.text
    version_id = uuid.UUID(response.json()["evidence_version_id"])
    row = await firm.version(version_id)
    assert row["storage_mode"] == "content_addressed"
    assert row["storage_key"] == storage.object_key(firm.tenant_id, str(row["fingerprint"]))
    assert await firm.key_row(version_id) is None
    sealed = firm.raw.get_object(
        Bucket=BUCKET, Key=str(row["storage_key"]), VersionId=str(row["storage_version_id"])
    )["Body"].read()
    assert sealed[:4] == b"ABE1"


async def test_t18_derived_records_are_sealed_under_the_versions_key(firm: Firm) -> None:
    """ADR-162 §6: the extraction and the preview pages live beside the version, so the same
    erase covers them."""
    response = await firm.upload(firm.client, bank_statement_pdf(last4="3383"))
    version_id = uuid.UUID(response.json()["evidence_version_id"])
    await firm.processed(version_id)
    prefix = f"tenants/{firm.tenant_id}/vd/{version_id}/"
    extracted = await firm.seed.value(
        "SELECT storage_key FROM upload_extractions WHERE evidence_version_id = $1", version_id
    )
    assert str(extracted).startswith(prefix)
    pages = await firm.seed.rows(
        "SELECT p.storage_key FROM upload_preview_pages p JOIN upload_previews v "
        "ON v.id = p.preview_id WHERE v.evidence_version_id = $1",
        version_id,
    )
    assert pages and all(str(p["storage_key"]).startswith(prefix) for p in pages)
    preview = await firm.net.http.get(
        f"{firm.base}/request-items/{firm.site.item_id}/uploads/{version_id}/preview/pages/1",
        headers=firm.net.headers(firm.manager),
    )
    assert preview.status_code == 200, preview.text
    assert preview.content[:8] == b"\x89PNG\r\n\x1a\n"


async def test_t18_without_its_key_row_the_upload_opens_for_no_one(firm: Firm) -> None:
    response = await firm.upload(firm.client, bank_statement_pdf(last4="4484"))
    version_id = uuid.UUID(response.json()["evidence_version_id"])
    await firm.processed(version_id)
    row = await firm.version(version_id)
    page = await firm.seed.rows(
        "SELECT p.storage_key, p.storage_version_id, p.fingerprint, p.size_bytes "
        "FROM upload_preview_pages p JOIN upload_previews v ON v.id = p.preview_id "
        "WHERE v.evidence_version_id = $1",
        version_id,
    )
    # The erase the purge performs (its definer is P-06-T19's): the wrapped key is gone.
    await firm.seed.run(
        "UPDATE evidence_object_keys SET wrapped_key = NULL, destroyed_at = now() "
        "WHERE evidence_version_id = $1",
        version_id,
    )
    with pytest.raises(storage.KeyDestroyed):
        await storage.get(firm.tenant_id, firm.stored(row))
    with pytest.raises(storage.KeyDestroyed):
        await storage.get(firm.tenant_id, firm.stored(page[0]))


async def test_t18_acceptance_retains_the_key_and_a_retained_key_is_never_cleared(
    firm: Firm,
) -> None:
    response = await firm.upload(firm.client, bank_statement_pdf(last4="5585"))
    version_id = uuid.UUID(response.json()["evidence_version_id"])
    accepted = await firm.net.call(
        "POST",
        f"{firm.base}/evidence-versions/{version_id}/decision/accept",
        firm.manager,
        body={},
    )
    assert accepted.status_code == 201, accepted.text
    key = await firm.key_row(version_id)
    assert key is not None and key["retained_at"] is not None
    with pytest.raises(asyncpg.InsufficientPrivilegeError):  # the guard, even for the owner
        await firm.seed.run(
            "UPDATE evidence_object_keys SET wrapped_key = NULL, destroyed_at = now() "
            "WHERE evidence_version_id = $1",
            version_id,
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await firm.seed.run(
            "UPDATE evidence_object_keys SET retained_at = NULL WHERE evidence_version_id = $1",
            version_id,
        )


async def test_t18_the_app_role_can_stamp_retention_only(firm: Firm) -> None:
    """The app role may not clear a key or call the destroy function outside the purge."""
    response = await firm.upload(firm.client, bank_statement_pdf(last4="6686"))
    version_id = uuid.UUID(response.json()["evidence_version_id"])
    person = TenantContext(firm.tenant_id, "human", str(firm.client.user_id))
    with pytest.raises(DBAPIError, match="permission denied"):
        async with tenant_session(person) as session:
            await session.execute(
                text(
                    "UPDATE evidence_object_keys SET wrapped_key = NULL "
                    "WHERE evidence_version_id = :v"
                ),
                {"v": version_id},
            )
    with pytest.raises(DBAPIError, match="only the withdrawal purge"):
        async with tenant_session(person) as session:
            await session.execute(text("SELECT evidence_key_destroy(:v)"), {"v": version_id})
    key = await firm.key_row(version_id)
    assert key is not None and key["wrapped_key"] is not None
