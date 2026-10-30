# ac-test-author: ayushkbhatia
"""N-02-T20 follow-up (TASK-2145; N-02 §4.3; SIG-02 a; DEC-1181): an envelope document's preview
page, `GET /v1/envelopes/{id}/documents/{doc}/pages/{n}`.

The page is the evidence viewer's masked rendition of the document's version: a PNG served
`no-store` and `nosniff`, logged as a content read, never the raw file. A document of another
envelope answers 404, a generated document (P-11) 409 `preview_unavailable`, and a walled person
404 with no hint (INV-3).

Boundary: `create_app()` over HTTP as each signed-in person; a real W-2 upload run through
extraction, the PII scan and the masked rendition; envelope rows seeded through SQL.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Final, cast

import pytest
from types_boto3_s3 import S3Client

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import UPLOAD_VERSION, UploadInput, check_upload_content
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.evidence.masked_previews import masked_preview_upload
from abacus.modules.evidence.pii import pii_scan_upload
from abacus.modules.evidence.words import words_upload
from abacus_tools.synthetic.documents import w2_pdf

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio
BUCKET: Final = "task2145-envelope-previews"
MASTER: Final = b"task2145-envelope-previews-master-key-012"
PDF: Final = "application/pdf"
PNG_MAGIC: Final = b"\x89PNG\r\n\x1a\n"


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
    owner: Person
    grace: Person
    walled: Person
    site: Site
    envelope: uuid.UUID
    document: uuid.UUID
    generated: uuid.UUID


_numbers = iter(range(1, 10_000))


async def _envelope(seed: Seeder, site: Site, by: Person) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO envelopes (tenant_id, number, purpose, policy_family, client_id, "
            "engagement_id, title, provider, drafted_by_kind, drafted_by) VALUES ($1, $2, "
            "'form_8879', 'efile_authorization', $3, $4, 'Form 8879 (2025)', 'docusign', "
            "'human', $5) RETURNING id",
            site.tenant_id,
            next(_numbers),
            site.client_id,
            site.engagement_id,
            by.user_id,
        ),
    )


async def _document(
    seed: Seeder, site: Site, envelope: uuid.UUID, order: int, version: uuid.UUID | None
) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            'INSERT INTO envelope_documents (tenant_id, envelope_id, "order", '
            "evidence_version_id, generated_document_version_id, sha256) VALUES ($1, $2, $3, "
            "$4, $5, $6) RETURNING id",
            site.tenant_id,
            envelope,
            order,
            version,
            None if version is not None else uuid.uuid4(),
            "0" * 64,
        ),
    )


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    for flag in ("uploads.processing", "evidence.viewer_v1", "signatures.envelopes"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'TASK-2145')",
            tenant_id,
            flag,
        )
    owner = await seed.person(tenant_id, "firm_admin")
    grace = await seed.person(tenant_id, "firm_admin")
    walled = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, owner.user_id, "Harborview")
    await seed.member(site, grace, "manager")
    await net.wall(owner, walled, site)
    admin = await seed.client_contact(site, "client_admin")
    uploaded = await net.http.post(
        f"/v1/engagements/{site.engagement_id}/request-items/{site.item_id}/uploads",
        params={"filename": "w2.pdf"},
        content=w2_pdf(),
        headers={**net.headers(admin), "Content-Type": PDF},
    )
    assert uploaded.status_code == 201, uploaded.text
    version = uuid.UUID(uploaded.json()["evidence_version_id"])
    given = UploadInput(str(tenant_id), UPLOAD_VERSION, str(version))
    await extract_upload(given)
    await check_upload_content(given)
    await words_upload(given)
    await pii_scan_upload(given)
    await masked_preview_upload(given)
    envelope = await _envelope(seed, site, grace)
    document = await _document(seed, site, envelope, 1, version)
    generated = await _document(seed, site, envelope, 2, None)
    return Firm(net, tenant_id, owner, grace, walled, site, envelope, document, generated)


def _page(firm: Firm, document: uuid.UUID, envelope: uuid.UUID | None = None) -> str:
    return f"/v1/envelopes/{envelope or firm.envelope}/documents/{document}/pages/1"


async def test_the_preview_is_the_masked_page_served_no_store_and_logged(firm: Firm) -> None:
    reads_before = await firm.net.seed.value(
        "SELECT count(*) FROM access_events WHERE tenant_id = $1", firm.tenant_id
    )
    page = await firm.net.call("GET", _page(firm, firm.document), firm.grace)
    assert page.status_code == 200, page.text
    assert page.content.startswith(PNG_MAGIC)
    assert page.headers["content-type"] == "image/png"
    assert page.headers["cache-control"] == "private, no-store"
    assert page.headers["x-content-type-options"] == "nosniff"
    reads_after = await firm.net.seed.value(
        "SELECT count(*) FROM access_events WHERE tenant_id = $1", firm.tenant_id
    )
    assert cast(int, reads_after) > cast(int, reads_before)


async def test_another_envelopes_document_is_404(firm: Firm) -> None:
    other = await _envelope(firm.net.seed, firm.site, firm.grace)
    answer = await firm.net.call("GET", _page(firm, firm.document, other), firm.grace)
    assert answer.status_code == 404


async def test_a_generated_document_has_no_preview_yet(firm: Firm) -> None:
    answer = await firm.net.call("GET", _page(firm, firm.generated), firm.grace)
    assert answer.status_code == 409
    assert answer.json()["detail"] == "preview_unavailable"


async def test_a_walled_person_gets_404_with_no_hint(firm: Firm) -> None:
    answer = await firm.net.call("GET", _page(firm, firm.document), firm.walled)
    assert answer.status_code == 404
    assert "Harborview" not in answer.text
