# ac-test-author: ayushkbhatia
"""TASK-1207 security review (DEC-52, DEC-319 narrowed; F-03 section 4.4): an offshore member
reads a client's documents only through masked renditions.

Offshore is not a wall, so Remy Vidal (an offshore manager) works on the engagement like Mia (an
onshore manager on the same team). But a W-2's box a holds an SSN, so every route that serves the
document unmasked refuses him at the condition layer (403, nothing served, no content-read row):
the original file, the legacy preview JSON (its `page_lines` carry the raw text), the legacy page
PNGs, and the inbox previews. Mia gets each one as before. A wall still comes first: walled from
the client, Remy gets 404 on the same routes. The logged PII reveal answers 403 to him too.

Boundary: `create_app()` over HTTP as the firm's people and the client's, the migrated Postgres,
the compose S3 image with Object Lock, and the processing activities. Expectations come from
DEC-52 and the review's findings, not from the implementation.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Final

import pytest
from types_boto3_s3 import S3Client

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import (
    UPLOAD_INBOX,
    UPLOAD_VERSION,
    UploadInput,
    check_upload_content,
)
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.evidence.masked_previews import masked_preview_upload
from abacus.modules.evidence.pii import pii_scan_upload
from abacus.modules.evidence.words import words_upload
from abacus_tools.synthetic.documents import w2_pdf

from .support import Net, Person, Seeder, Site


async def preview_upload(given: UploadInput) -> str:
    """The rendition steps of a v7 run (P-03-T15): word layer, PII scan, masked rendition."""
    await words_upload(given)
    await pii_scan_upload(given)
    return await masked_preview_upload(given)


BUCKET: Final = "task1207-offshore-reads"
MASTER: Final = b"task1207-offshore-reads-master-key-0123456"
PDF: Final = "application/pdf"
FORBIDDEN: Final = {"detail": "forbidden"}


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
    mia: Person
    remy: Person
    site: Site
    version: uuid.UUID
    inbox: uuid.UUID

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    def paths(self) -> dict[str, str]:
        """The routes that serve the W-2 unmasked (the review's item 1)."""
        e = f"/v1/engagements/{self.site.engagement_id}"
        item = f"{e}/request-items/{self.site.item_id}/uploads/{self.version}"
        return {
            "original": f"{e}/evidence-versions/{self.version}/content",
            "upload_preview": f"{item}/preview",
            "upload_page": f"{item}/preview/pages/1",
            "version_preview": f"{e}/evidence-versions/{self.version}/preview",
            "version_page": f"{e}/evidence-versions/{self.version}/preview/pages/1",
            "inbox_preview": f"{e}/inbox/{self.inbox}/preview",
            "inbox_page": f"{e}/inbox/{self.inbox}/preview/pages/1",
        }

    async def content_reads(self, who: Person) -> int:
        """The person's content reads: access events and `evidence_version.read` audit rows."""
        accessed = await self.seed.value(
            "SELECT count(*) FROM access_events WHERE tenant_id = $1 AND actor_id::text = $2",
            self.tenant_id,
            str(who.user_id),
        )
        audited = await self.seed.value(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND actor_id::text = $2 "
            "AND action = 'evidence_version.read'",
            self.tenant_id,
            str(who.user_id),
        )
        return int(str(accessed)) + int(str(audited))


async def _offshore(seed: Seeder, who: Person) -> None:
    await seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        who.tenant_id,
        who.user_id,
    )


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    for flag in ("uploads.processing", "evidence.pii_reveal"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'TASK-1207')",
            tenant_id,
            flag,
        )
    owner = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, owner.user_id, "Ashford")
    mia = await seed.person(tenant_id)
    remy = await seed.person(tenant_id)
    for who in (mia, remy):
        await seed.member(site, who, "manager")
    admin = await seed.client_contact(site, "client_admin")
    base = f"/v1/engagements/{site.engagement_id}"
    uploaded = await net.http.post(
        f"{base}/request-items/{site.item_id}/uploads",
        params={"filename": "w2.pdf"},
        content=w2_pdf(),
        headers={**net.headers(admin), "Content-Type": PDF},
    )
    assert uploaded.status_code == 201, uploaded.text
    version = uuid.UUID(uploaded.json()["evidence_version_id"])
    dropped = await net.http.post(
        f"{base}/inbox",
        params={"filename": "w2.pdf"},
        content=w2_pdf(),
        headers={**net.headers(mia), "Content-Type": PDF},
    )
    assert dropped.status_code == 201, dropped.text
    inbox = uuid.UUID(dropped.json()["id"])
    for given in (
        UploadInput(str(tenant_id), UPLOAD_VERSION, str(version)),
        UploadInput(str(tenant_id), UPLOAD_INBOX, str(inbox)),
    ):
        await extract_upload(given)
        await check_upload_content(given)
        await preview_upload(given)
    await _offshore(seed, remy)
    return Firm(net, tenant_id, owner, mia, remy, site, version, inbox)


ROUTES: Final = (
    "original",
    "upload_preview",
    "upload_page",
    "version_preview",
    "version_page",
    "inbox_preview",
    "inbox_page",
)


@pytest.mark.parametrize("route", ROUTES)
async def test_review1_an_onshore_manager_still_reads_the_w2(firm: Firm, route: str) -> None:
    response = await firm.net.call("GET", firm.paths()[route], firm.mia)
    assert response.status_code == 200, (route, response.text)
    if route.endswith("page") or route == "original":
        assert await firm.content_reads(firm.mia) > 0  # the control: such a read is logged


@pytest.mark.parametrize("route", ROUTES)
async def test_review1_an_offshore_manager_is_refused_the_unmasked_w2_at_the_condition(
    firm: Firm, route: str
) -> None:
    response = await firm.net.call("GET", firm.paths()[route], firm.remy)
    assert (response.status_code, response.json()) == (403, FORBIDDEN), route
    assert "6081" not in response.text
    assert await firm.content_reads(firm.remy) == 0  # nothing was read for him


@pytest.mark.parametrize("route", ROUTES)
async def test_review1_a_wall_comes_first_for_an_offshore_member(firm: Firm, route: str) -> None:
    """Walls are unaffected: walled from the client, Remy reads the W-2 as never-existed."""
    await firm.net.wall(firm.owner, firm.remy, firm.site)
    response = await firm.net.call("GET", firm.paths()[route], firm.remy)
    assert response.status_code == 404, (route, response.text)


async def test_review5_the_logged_pii_reveal_refuses_an_offshore_member(firm: Firm) -> None:
    """`pii.reveal` is `not_offshore`: Remy is refused at the condition (403) and nothing is
    revealed; Mia, allowed, gets the W-2's SSN once, `no-store` (P-03-T16, SPEC-322 AC-26)."""
    path = f"/v1/evidence-versions/{firm.version}/pii-reveals"
    region = await firm.seed.value(
        "SELECT id FROM pii_regions WHERE evidence_version_id = $1 AND kind = 'ssn'",
        firm.version,
    )
    body = {"region_id": str(region)}
    remy = await firm.net.call("POST", path, firm.remy, body=body)
    assert (remy.status_code, remy.json()) == (403, FORBIDDEN)
    assert "6081" not in remy.text
    count = "SELECT count(*) FROM pii_reveals WHERE user_id = $1"
    assert await firm.seed.value(count, firm.remy.user_id) == 0
    mia = await firm.net.call("POST", path, firm.mia, body=body)
    assert mia.status_code == 201, mia.text
    assert mia.headers["cache-control"] == "no-store"
    answer = mia.json()
    assert (answer["value"], answer["kind"], answer["expires_in"]) == ("000-00-6081", "ssn", 30)
    assert await firm.seed.value(count, firm.mia.user_id) == 1
    unknown = await firm.net.call("POST", path, firm.mia, body={"region_id": str(uuid.uuid4())})
    assert unknown.status_code == 404


async def test_review_l3_the_twenty_first_reveal_answers_429_with_retry_after(firm: Firm) -> None:
    """P-03-T16 review L3: the cap's refusal carries `Retry-After` beside `facts.retry_after`."""
    region = await firm.seed.value(
        "SELECT id FROM pii_regions WHERE evidence_version_id = $1 AND kind = 'ssn'",
        firm.version,
    )
    for _ in range(20):  # twenty reveals in the past hour, as the reveal writes them
        await firm.seed.run(
            "INSERT INTO pii_reveals (tenant_id, region_id, evidence_version_id, user_id, "
            "actor_kind, expires_at) VALUES ($1, $2, $3, $4, 'human', "
            "clock_timestamp() + interval '30 seconds')",
            firm.tenant_id,
            region,
            firm.version,
            firm.mia.user_id,
        )
    path = f"/v1/evidence-versions/{firm.version}/pii-reveals"
    refused = await firm.net.call("POST", path, firm.mia, body={"region_id": str(region)})
    assert refused.status_code == 429, refused.text
    body = refused.json()
    assert body["detail"] == "reveal_rate_limited" and "value" not in body
    assert refused.headers["retry-after"] == str(body["facts"]["retry_after"])
    assert 0 < int(refused.headers["retry-after"]) <= 3600
