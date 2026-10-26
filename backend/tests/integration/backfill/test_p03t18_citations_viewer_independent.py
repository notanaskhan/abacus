# ac-test-author: ayushkbhatia
"""SPEC-322 AC-1, AC-2, AC-4, AC-5, AC-10, AC-16, AC-21 to AC-30, AC-36, AC-37 (P-03-T18,
TASK-1297): citations v2, the viewer and the logged reveal keep INV-1, INV-2 and INV-3.

Every citation is a code-verified, insert-only row; its quote is never stored. Every page image is
a masked rendition: an onshore reader gets PNGs with every detected region burned opaque, an
offshore reader gets the masked text view and a 403 on every image (DEC-369). A masked value is
revealed only to a live, onshore engagement member with recent MFA, once per call, logged without
the value (DEC-370). A wall or another firm reads as never-existed (404, no count); a client
principal holds no citation action.

Boundary: `create_app()` over HTTP as the firm's people and the client's, on the migrated
Postgres and the compose S3 image. Uploads go through the client upload route and the rendition
steps a v7 run calls (words, PII scan, masked preview). Citations are written with the public
writer `evidence.api.record_citations` as a person; an agent row is seeded as the superuser,
because an agent context is built only from a proven run. The moved detector receives the outbox
`evidence_version.created` event as the relay would deliver it.

Later decisions followed instead of the spec's words: DEC-370 (MFA for every kind; refusals other
than `mfa_required` are the plain `{"detail": "forbidden"}`), DEC-369 (`view: text` for offshore
readers, `TextOut`, page images refused to them; a clear value copied into a quote no longer
verifies).
"""

from __future__ import annotations

import io
import json
import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast

import asyncpg
import pytest
from PIL import Image
from types_boto3_s3 import S3Client

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.kernel.tin_patterns import has_tin
from abacus.kernel.uow import uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import (
    UPLOAD_VERSION,
    CitationAnchor,
    CitationClaim,
    Provenance,
    RecordedCitation,
    UploadInput,
    add_version,
    check_upload_content,
    on_version_created,
    record_citations,
    stage_content,
)
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.evidence.masked_previews import masked_preview_upload
from abacus.modules.evidence.pii import pii_scan_upload
from abacus.modules.evidence.processing import preview_upload as unmasked_preview_upload
from abacus.modules.evidence.words import words_upload
from abacus.modules.identity.api import AuthContext
from abacus_tools.synthetic.documents import letter_pdf, positioned_pdf, scanned_pdf, w2_pdf

from .support import Migrated, Net, Person, Seeder, Site

BUCKET: Final = "task1297-citations-viewer"
MASTER: Final = b"task1297-citations-viewer-master-key-01234"
PDF: Final = "application/pdf"
FORBIDDEN: Final = {"detail": "forbidden"}
NOT_FOUND: Final = {"detail": "not found"}
FLAGS: Final = (
    "uploads.processing",
    "evidence.citations_v2",
    "evidence.viewer_v1",
    "evidence.pii_reveal",
)
CLEAR_SSN: Final = "000-00-6081"
CLEAR_EIN: Final = "00-1230287"
SSN_MASK: Final = "•••-••-6081"
NAME_LINE: Final = "Brightwater Hale (Synthetic)"
# The W-2 prints the name line at x 36, baseline 676 on a 792 pt page: top-left y about 116.
NAME_BOX: Final = [30.0, 105.0, 290.0, 125.0]
EMPTY_BOX: Final = [400.0, 400.0, 500.0, 450.0]
COUNTS: Final = {
    "citations": "SELECT count(*) FROM citations WHERE tenant_id = $1",
    "citation_events": "SELECT count(*) FROM citation_events WHERE tenant_id = $1",
}
DISPLAY_FIELDS: Final = {
    "id",
    "n",
    "kind",
    "title",
    "loc",
    "quote",
    "quote_state",
    "value_text",
    "match_id",
    "state",
    "verified",
    "verification_reason",
    "created_by",
    "retrieved_at",
    "source",
    "used_in",
    "moved",
    "allowed_actions",
}


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
    forget_flags()
    yield
    forget_flags()
    storage.reset_storage()
    reset_key_service()


async def _rendered(given: UploadInput) -> None:
    """The steps a v7 upload run takes (DEC-369): extract, check, words, PII scan, masked page."""
    await extract_upload(given)
    await check_upload_content(given)
    await words_upload(given)
    await pii_scan_upload(given)
    await masked_preview_upload(given)


def _person(who: Person) -> AuthContext:
    """`who` as a signed-in person with MFA a minute old (the writer's actor)."""
    return AuthContext(
        tenant=TenantContext(who.tenant_id, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=None,
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


@dataclass(frozen=True)
class World:
    net: Net
    tenant_id: uuid.UUID
    owner: Person
    samuel: Person  # onshore staff
    remy: Person  # offshore manager
    lena: Person  # staff, walled from the Ashford client
    rhea: Person  # reviewer: reads citations, may not reveal
    cora: Person  # client_service
    client: Person  # the client's admin
    site: Site
    w2: uuid.UUID

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def anchor(self) -> CitationAnchor:
        return CitationAnchor(
            type="request_item", id=self.site.item_id, engagement_id=self.site.engagement_id
        )

    async def upload(self, content: bytes, *, render: bool = True) -> uuid.UUID:
        """The client's upload of `content` to a new request item of the engagement."""
        item = await self.seed.item(self.site, f"Document {uuid.uuid4().hex[:6]}")
        response = await self.net.http.post(
            f"/v1/engagements/{self.site.engagement_id}/request-items/{item}/uploads",
            params={"filename": "document.pdf"},
            content=content,
            headers={**self.net.headers(self.client), "Content-Type": PDF},
        )
        assert response.status_code == 201, response.text
        version = uuid.UUID(response.json()["evidence_version_id"])
        if render:
            await _rendered(UploadInput(str(self.tenant_id), UPLOAD_VERSION, str(version)))
        return version

    async def cite(
        self, *claims: CitationClaim, by: Person | None = None
    ) -> list[RecordedCitation]:
        actor = _person(by or self.samuel)
        async with uow(actor.tenant) as tx:
            return await record_citations(tx, actor=actor, anchor=self.anchor, claims=claims)

    async def cite_w2(self, quote: str = NAME_LINE, **locator: object) -> RecordedCitation:
        [row] = await self.cite(
            CitationClaim(
                "document_text",
                {"evidence_version_id": str(self.w2), "page": 1, **locator},
                quote=quote,
            )
        )
        return row

    async def successor(self, content: bytes) -> uuid.UUID:
        """The next version of the W-2's evidence item, rendered, with `evidence_version.created`
        delivered to the moved detector as the relay would (at least once)."""
        item = cast(
            uuid.UUID,
            await self.seed.value(
                "SELECT evidence_item_id FROM evidence_versions WHERE id = $1", self.w2
            ),
        )
        stored = await stage_content(self.tenant_id, content)
        async with uow(TenantContext(self.tenant_id, "system", "test-seed")) as tx:
            ref = await add_version(
                tx,
                engagement_id=self.site.engagement_id,
                item=item,
                stored=stored,
                media_type=PDF,
                provenance=Provenance(source="upload", method="uploaded"),
            )
        await _rendered(UploadInput(str(self.tenant_id), UPLOAD_VERSION, str(ref.id)))
        rows = await self.seed.rows(
            "SELECT id, payload FROM outbox WHERE tenant_id = $1 "
            "AND event_type = 'evidence_version.created' ORDER BY seq",
            self.tenant_id,
        )
        for row in rows:
            payload = row["payload"]
            loaded = json.loads(payload) if isinstance(payload, str) else dict(payload)
            await on_version_created(
                OutboxEvent(row["id"], self.tenant_id, "evidence_version.created", loaded)
            )
        return ref.id

    async def region(self, kind: str, version: uuid.UUID | None = None) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.seed.value(
                "SELECT id FROM pii_regions WHERE evidence_version_id = $1 AND kind = $2",
                version or self.w2,
                kind,
            ),
        )

    async def reveals(self, who: Person) -> int:
        count = await self.seed.value(
            "SELECT count(*) FROM pii_reveals WHERE tenant_id = $1 AND user_id = $2",
            self.tenant_id,
            who.user_id,
        )
        return int(str(count))

    async def audit(self, action: str) -> list[asyncpg.Record]:
        return await self.seed.rows(
            "SELECT * FROM audit_events WHERE tenant_id = $1 AND action = $2 ORDER BY seq",
            self.tenant_id,
            action,
        )


async def _onshore_member(seed: Seeder, site: Site, role: str) -> Person:
    """An engagement member in a role the helper doesn't type, with confirmed independence."""
    who = await seed.person(site.tenant_id)
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, $4)",
        site.tenant_id,
        site.engagement_id,
        who.user_id,
        role,
    )
    await seed.run(
        "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status, "
        "statement_version, answered_at) VALUES ($1, $2, $3, 'confirmed', 'v1', "
        "clock_timestamp()) ON CONFLICT DO NOTHING",
        site.tenant_id,
        site.engagement_id,
        who.user_id,
    )
    return who


@pytest.fixture
async def world(net: Net, seed: Seeder) -> World:
    tenant_id = await seed.firm()
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'TASK-1297')",
            tenant_id,
            flag,
        )
    owner = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, owner.user_id, "Ashford")
    samuel = await seed.person(tenant_id)
    remy = await seed.person(tenant_id)
    lena = await seed.person(tenant_id)
    rhea = await seed.person(tenant_id)
    await seed.member(site, samuel, "staff")
    await seed.member(site, remy, "manager")
    await seed.member(site, lena, "staff")
    await seed.member(site, rhea, "reviewer")
    cora = await _onshore_member(seed, site, "client_service")
    await seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        tenant_id,
        remy.user_id,
    )
    client = await seed.client_contact(site, "client_admin")
    shell = World(
        net, tenant_id, owner, samuel, remy, lena, rhea, cora, client, site, uuid.uuid4()
    )
    w2 = await shell.upload(w2_pdf())
    await net.wall(owner, lena, site)
    return World(net, tenant_id, owner, samuel, remy, lena, rhea, cora, client, site, w2)


# --- Story 1: a citation is a first-class, verified record --------------------------------


async def test_ac1_a_verified_document_citation_stores_a_hash_and_never_the_quote(
    world: World,
) -> None:
    row = await world.cite_w2(bbox=NAME_BOX)
    assert (row.kind, row.verified, row.verification_reason) == ("document_text", True, None)
    stored = await world.seed.rows(
        "SELECT to_jsonb(c) AS doc, c.quote_sha256, c.created_by_kind, c.created_by_user_id "
        "FROM citations c WHERE c.id = $1",
        row.id,
    )
    [record] = stored
    assert record["created_by_kind"] == "human"
    assert record["created_by_user_id"] == world.samuel.user_id
    assert len(bytes(record["quote_sha256"])) == 32  # the words it resolved to, hashed
    assert "Brightwater" not in str(record["doc"])  # no quote text anywhere in the row
    actions = await world.audit("citation.created")
    assert [a["target_id"] for a in actions] == [str(row.id)]
    assert "Brightwater" not in json.dumps([dict(a) for a in actions], default=str)


@pytest.mark.parametrize(
    ("locator", "quote", "reason"),
    [
        ({"page": 9}, NAME_LINE, "page_not_found"),
        ({"page": 1}, "Statement of cash flows for the quarter", "quote_not_found"),
        ({"page": 1, "bbox": EMPTY_BOX}, None, "bbox_mismatch"),
    ],
)
async def test_ac2_an_unsupported_claim_is_stored_unverified_with_its_reason(
    world: World, locator: dict[str, object], quote: str | None, reason: str
) -> None:
    [row] = await world.cite(
        CitationClaim(
            "document_text", {"evidence_version_id": str(world.w2), **locator}, quote=quote
        )
    )
    assert (row.verified, row.verification_reason) == (False, reason)
    read = await world.net.call("GET", f"/v1/citations/{row.id}", world.samuel)
    assert read.status_code == 200, read.text
    assert (read.json()["verified"], read.json()["verification_reason"]) == (False, reason)


async def test_ac3_a_quote_without_a_bbox_is_verified_on_the_page_text(world: World) -> None:
    row = await world.cite_w2()
    assert (row.verified, row.verification_reason) == (True, None)


async def test_ac25_a_quote_copied_from_masked_text_verifies_and_the_clear_value_does_not(
    world: World,
) -> None:
    """DEC-369: verification runs on the masked projection of a scanned page."""
    masked = await world.cite_w2(quote=SSN_MASK)
    clear = await world.cite_w2(quote=CLEAR_SSN)
    assert (masked.verified, masked.verification_reason) == (True, None)
    assert (clear.verified, clear.verification_reason) == (False, "quote_not_found")


@pytest.mark.parametrize("table", ["citations", "citation_events"])
@pytest.mark.parametrize(
    "statement",
    ["UPDATE {t} SET tenant_id = tenant_id", "DELETE FROM {t}", "TRUNCATE {t} CASCADE"],
)
async def test_ac4_the_database_rejects_any_change_to_citation_rows_for_every_role(
    world: World, migrated_db: Migrated, table: str, statement: str
) -> None:
    row = await world.cite_w2()
    await world.seed.run(  # one event, so both tables hold a row the statement could touch
        "INSERT INTO citation_events (tenant_id, citation_id, kind, cause_ref, actor_kind) "
        "VALUES ($1, $2, 'broken', 'test-seed', 'system')",
        world.tenant_id,
        row.id,
    )
    sql = statement.format(t=table)
    with pytest.raises(asyncpg.PostgresError):  # the superuser: the trigger refuses
        await world.seed.run(sql)
    app = await asyncpg.connect(migrated_db.app_url.replace("postgresql+asyncpg", "postgresql"))
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):  # the app role: no grant
            await app.execute(sql)
    finally:
        await app.close()
    left = await world.seed.value(COUNTS[table], world.tenant_id)
    assert int(str(left)) >= 1


async def test_ac1_an_agent_citation_reads_as_the_person_via_agent(world: World) -> None:
    row = await world.cite_w2()
    agent_id = cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO citations (tenant_id, engagement_id, cited_from_type, cited_from_id, n, "
            "kind, source_type, source_id, source_version, locator, match_id, quote_sha256, "
            "verified, verification_reason, verifier_version, created_by_kind, "
            "created_by_run_id, on_behalf_of_user_id) "
            "SELECT tenant_id, engagement_id, cited_from_type, cited_from_id, n + 1, kind, "
            "source_type, source_id, source_version, locator, match_id, quote_sha256, verified, "
            "verification_reason, verifier_version, 'agent', $2, $3 FROM citations WHERE id = $1 "
            "RETURNING id",
            row.id,
            uuid.uuid4(),
            world.samuel.user_id,
        ),
    )
    read = await world.net.call("GET", f"/v1/citations/{agent_id}", world.samuel)
    assert read.status_code == 200, read.text
    assert read.json()["created_by"] == {"kind": "agent", "label": "Test person via Agent"}


# --- Citation reads: the display contract, walls, client principals, other firms ----------


async def test_ac6_the_display_carries_the_contract_fields_and_no_stored_hash(
    world: World,
) -> None:
    row = await world.cite_w2(bbox=NAME_BOX)
    read = await world.net.call("GET", f"/v1/citations/{row.id}", world.samuel)
    assert read.status_code == 200, read.text
    body = read.json()
    assert set(body) == DISPLAY_FIELDS
    assert (body["id"], body["kind"], body["state"], body["verified"]) == (
        str(row.id),
        "document_text",
        "valid",
        True,
    )
    assert body["created_by"]["kind"] == "human"
    assert body["source"]["evidence_version_id"] == str(world.w2)
    assert body["quote_state"] in {"shown", "withheld", "changed"}
    assert "quote_sha256" not in read.text


async def test_ac6_a_quote_is_reread_from_the_masked_layer(world: World) -> None:
    row = await world.cite_w2(quote=SSN_MASK)
    read = await world.net.call("GET", f"/v1/citations/{row.id}", world.samuel)
    assert read.status_code == 200, read.text
    assert CLEAR_SSN not in read.text and not has_tin(read.text)


async def test_ac7_the_anchor_stack_lists_the_citations_in_order(world: World) -> None:
    first = await world.cite_w2()
    second = await world.cite_w2(quote=SSN_MASK)
    listed = await world.net.http.get(
        "/v1/citations",
        params={"anchor_type": "request_item", "anchor_id": str(world.site.item_id)},
        headers=world.net.headers(world.samuel),
    )
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert [i["id"] for i in body["items"]] == [str(first.id), str(second.id)]
    assert [i["n"] for i in body["items"]] == sorted(i["n"] for i in body["items"])
    assert body["total"] == 2


async def test_ac5_lena_walled_from_ashford_gets_not_found_and_no_count(world: World) -> None:
    row = await world.cite_w2()
    single = await world.net.call("GET", f"/v1/citations/{row.id}", world.lena)
    assert (single.status_code, single.json()) == (404, NOT_FOUND)
    listed = await world.net.http.get(
        "/v1/citations",
        params={"anchor_type": "request_item", "anchor_id": str(world.site.item_id)},
        headers=world.net.headers(world.lena),
    )
    if listed.status_code == 200:  # a list omits it, with no hidden count
        assert listed.json()["items"] == [] and listed.json()["total"] == 0
        assert listed.json()["counts"] == {}
    else:
        assert listed.status_code == 404
    assert str(row.id) not in listed.text
    by_version = await world.net.http.get(
        "/v1/citations",
        params={"source_version_id": str(world.w2)},
        headers=world.net.headers(world.lena),
    )
    assert str(row.id) not in by_version.text


async def test_ac5_a_client_principal_is_refused_every_citation_route(world: World) -> None:
    row = await world.cite_w2()
    calls = [
        ("GET", f"/v1/citations/{row.id}"),
        ("GET", f"/v1/citations?anchor_type=request_item&anchor_id={world.site.item_id}"),
        ("POST", f"/v1/citations/{row.id}/relink"),
    ]
    for method, path in calls:
        response = await world.net.call(method, path, world.client)
        assert response.status_code == 403, (path, response.text)
        assert response.json()["detail"] == "forbidden"
        assert NAME_LINE not in response.text


async def test_ac5_client_service_never_reads_citations(world: World) -> None:
    row = await world.cite_w2()
    response = await world.net.call("GET", f"/v1/citations/{row.id}", world.cora)
    assert response.status_code in {403, 404}, response.text
    assert str(row.id) not in response.text


async def test_ac5_the_reviewer_reads_citations(world: World) -> None:
    row = await world.cite_w2()
    response = await world.net.call("GET", f"/v1/citations/{row.id}", world.rhea)
    assert response.status_code == 200, response.text


async def test_ac22_another_firm_reads_a_citation_and_its_version_as_never_existed(
    world: World,
) -> None:
    row = await world.cite_w2()
    elsewhere = await world.seed.firm()
    for flag in FLAGS:
        await world.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'TASK-1297')",
            elsewhere,
            flag,
        )
    outsider = await world.seed.person(elsewhere, "firm_admin")
    for path in (
        f"/v1/citations/{row.id}",
        f"/v1/evidence-versions/{world.w2}/viewer",
        f"/v1/evidence-versions/{world.w2}/pages/1",
        f"/v1/evidence-versions/{world.w2}/text",
    ):
        response = await world.net.call("GET", path, outsider)
        assert response.status_code == 404, (path, response.text)
    reveal = await world.net.call(
        "POST",
        f"/v1/evidence-versions/{world.w2}/pii-reveals",
        outsider,
        body={"region_id": str(await world.region("ssn"))},
    )
    assert reveal.status_code == 404, reveal.text
    assert CLEAR_SSN not in reveal.text


async def test_ac41_every_route_family_is_absent_with_its_flag_off(world: World) -> None:
    row = await world.cite_w2()
    await world.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1", world.tenant_id
    )
    forget_flags()
    for method, path, body in (
        ("GET", f"/v1/citations/{row.id}", None),
        ("GET", f"/v1/evidence-versions/{world.w2}/viewer", None),
        (
            "POST",
            f"/v1/evidence-versions/{world.w2}/pii-reveals",
            {"region_id": str(await world.region("ssn"))},
        ),
    ):
        response = await world.net.call(method, path, world.samuel, body=body)
        assert response.status_code == 404, (path, response.text)
    assert await world.reveals(world.samuel) == 0


# --- Story 6: moved, relink -----------------------------------------------------------------


def _corrected_w2() -> bytes:
    """A corrected W-2: the name line where it was, new wording elsewhere."""
    return positioned_pdf([[(36.0, 676.0, NAME_LINE), (36.0, 600.0, "Corrected copy")]])


async def test_ac10_a_superseded_source_reads_moved_and_offers_relink(world: World) -> None:
    row = await world.cite_w2(bbox=NAME_BOX)
    successor = await world.successor(_corrected_w2())
    read = await world.net.call("GET", f"/v1/citations/{row.id}", world.samuel)
    assert read.status_code == 200, read.text
    body = read.json()
    assert body["state"] == "moved"
    assert body["moved"] is not None
    assert "citation.relink" in body["allowed_actions"]
    events = await world.seed.rows(
        "SELECT kind, actor_kind, cause_ref FROM citation_events WHERE citation_id = $1", row.id
    )
    assert [(e["kind"], e["actor_kind"]) for e in events] == [("moved", "system")]
    assert events[0]["cause_ref"] is not None and successor is not None
    reviewer = await world.net.call("GET", f"/v1/citations/{row.id}", world.rhea)
    assert "citation.relink" not in reviewer.json()["allowed_actions"]


async def test_ac36_samuel_relinks_a_moved_citation_onto_its_successor(world: World) -> None:
    row = await world.cite_w2(bbox=NAME_BOX)
    successor = await world.successor(_corrected_w2())
    response = await world.net.call("POST", f"/v1/citations/{row.id}/relink", world.samuel)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"] != str(row.id)
    assert body["verified"] is True
    assert body["source"]["evidence_version_id"] == str(successor)
    supersedes = await world.seed.value(
        "SELECT supersedes_id FROM citations WHERE id = $1", uuid.UUID(body["id"])
    )
    assert supersedes == row.id
    [event] = await world.seed.rows(
        "SELECT actor_kind, actor_user_id, successor_citation_id FROM citation_events "
        "WHERE citation_id = $1 AND kind = 'relinked'",
        row.id,
    )
    assert (event["actor_kind"], event["actor_user_id"]) == ("human", world.samuel.user_id)
    assert event["successor_citation_id"] == uuid.UUID(body["id"])
    [audited] = await world.audit("citation.relinked")
    assert (audited["actor_kind"], audited["actor_id"]) == ("human", str(world.samuel.user_id))
    old = await world.net.call("GET", f"/v1/citations/{row.id}", world.samuel)
    assert old.json()["state"] == "relinked"


async def test_ac36_a_citation_that_has_not_moved_answers_not_moved(world: World) -> None:
    row = await world.cite_w2(bbox=NAME_BOX)
    response = await world.net.call("POST", f"/v1/citations/{row.id}/relink", world.samuel)
    assert (response.status_code, response.json()) == (409, {"detail": "not_moved"})


async def test_ac36_text_gone_from_the_successor_answers_relink_unverified(world: World) -> None:
    row = await world.cite_w2(bbox=NAME_BOX)
    await world.successor(letter_pdf())
    response = await world.net.call("POST", f"/v1/citations/{row.id}/relink", world.samuel)
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "relink_unverified"
    relinked = await world.seed.value(
        "SELECT count(*) FROM citation_events WHERE citation_id = $1 AND kind = 'relinked'",
        row.id,
    )
    assert relinked == 0


async def test_ac37_relink_is_refused_to_roles_without_it_and_the_database_refuses_a_machine(
    world: World,
) -> None:
    row = await world.cite_w2(bbox=NAME_BOX)
    await world.successor(_corrected_w2())
    for who in (world.rhea, world.client, world.lena):
        response = await world.net.call("POST", f"/v1/citations/{row.id}/relink", who)
        assert response.status_code in {403, 404}, response.text
        if who is world.lena:
            assert response.status_code == 404  # the wall comes first
    assert await world.audit("citation.relinked") == []
    with pytest.raises(asyncpg.CheckViolationError):  # INV-1 in the database
        await world.seed.run(
            "INSERT INTO citation_events (tenant_id, citation_id, kind, successor_citation_id, "
            "actor_kind) VALUES ($1, $2, 'relinked', $2, 'system')",
            world.tenant_id,
            row.id,
        )


# --- Story 3: the viewer: manifest, masked pages, regions, search, text -----------------------


async def test_ac13_the_manifest_carries_geometry_and_mask_tokens_never_text(world: World) -> None:
    response = await world.net.call(
        "GET", f"/v1/evidence-versions/{world.w2}/viewer", world.samuel
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["status"], body["kind"], body["page_count"], body["view"]) == (
        "ready",
        "pages",
        1,
        "images",
    )
    [page] = body["pages"]
    assert page["n"] == 1 and page["pii_scan"] == "done"
    kinds = {m["kind"]: m["display"] for m in body["pii_masks"]}
    assert kinds.get("ssn") == SSN_MASK
    assert "ein" in kinds
    assert "pii.reveal" in body["allowed_actions"]
    for words in (CLEAR_SSN, CLEAR_EIN, "Employee", "Wages", "Brightwater"):
        assert words not in response.text


async def test_ac24_every_region_on_the_served_page_is_burned_opaque(world: World) -> None:
    manifest = (
        await world.net.call("GET", f"/v1/evidence-versions/{world.w2}/viewer", world.samuel)
    ).json()
    page = await world.net.call("GET", f"/v1/evidence-versions/{world.w2}/pages/1", world.samuel)
    assert page.status_code == 200, page.text
    assert page.headers["content-type"] == "image/png"
    assert page.headers["cache-control"] == "no-store"
    assert page.headers["x-content-type-options"] == "nosniff"
    image = Image.open(io.BytesIO(page.content))
    assert image.width == 1240
    assert "A" not in image.getbands()  # no alpha: nothing shows through
    pixels = image.convert("RGB")
    [geometry] = manifest["pages"]
    scale = image.width / float(geometry["width_pt"])
    assert manifest["pii_masks"], "the W-2 has detected regions"
    for mask in manifest["pii_masks"]:
        x0, top, x1, bottom = (float(v) * scale for v in mask["rect"])
        inside = {
            pixels.getpixel((x, y))
            for x in range(int(x0) + 1, int(x1) - 1)
            for y in range(int(top) + 1, int(bottom) - 1)
        }
        assert len(inside) == 1, (mask["kind"], len(inside))  # one flat colour: no glyph left


async def test_ac24_an_unmasked_rendition_is_never_stored(world: World) -> None:
    rows = await world.seed.rows(
        "SELECT mask_version FROM upload_previews WHERE evidence_version_id = $1", world.w2
    )
    assert rows and all(r["mask_version"] is not None for r in rows)


async def test_ac24_a_legacy_preview_serves_the_masked_text(world: World) -> None:
    path = f"/v1/engagements/{world.site.engagement_id}/evidence-versions/{world.w2}/preview"
    response = await world.net.call("GET", path, world.samuel)
    assert response.status_code == 200, response.text
    assert CLEAR_SSN not in response.text and CLEAR_EIN not in response.text
    assert not has_tin(response.text)


async def test_ac24_a_pre_masking_preview_answers_preview_outdated(world: World) -> None:
    version = await world.upload(w2_pdf(), render=False)
    given = UploadInput(str(world.tenant_id), UPLOAD_VERSION, str(version))
    await extract_upload(given)
    await unmasked_preview_upload(given)  # a v3 run, before masking existed
    page = await world.net.call("GET", f"/v1/evidence-versions/{version}/pages/1", world.samuel)
    assert (page.status_code, page.json()) == (409, {"detail": "preview_outdated"})
    assert CLEAR_SSN.encode() not in page.content


async def test_ac16_a_version_without_a_masked_rendition_reads_processing(world: World) -> None:
    version = await world.upload(w2_pdf(), render=False)
    response = await world.net.call("GET", f"/v1/evidence-versions/{version}/viewer", world.samuel)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "processing"


async def test_ac13_regions_light_a_citation_by_its_match_id(world: World) -> None:
    row = await world.cite_w2(bbox=NAME_BOX)
    assert row.match_id is not None
    response = await world.net.http.get(
        f"/v1/evidence-versions/{world.w2}/regions",
        params={"match_ids": row.match_id},
        headers=world.net.headers(world.samuel),
    )
    assert response.status_code == 200, response.text
    [item] = response.json()["items"]
    assert (item["match_id"], item["page"], item["citation_id"]) == (
        row.match_id,
        1,
        str(row.id),
    )
    assert item["rects"] and all(len(rect) == 4 for rect in item["rects"])


async def test_ac21_search_returns_rects_only_scans_the_masked_layer_and_never_logs_the_query(
    world: World, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    path = f"/v1/evidence-versions/{world.w2}/search"
    hit = await world.net.http.get(
        path, params={"q": "Wages"}, headers=world.net.headers(world.samuel)
    )
    assert hit.status_code == 200, hit.text
    body = hit.json()
    assert body["total"] >= 1 and body["truncated"] is False
    assert all(set(i) == {"page", "rects"} for i in body["items"])
    assert "Wages" not in hit.text
    clear = await world.net.http.get(
        path, params={"q": CLEAR_SSN}, headers=world.net.headers(world.samuel)
    )
    assert clear.status_code == 200 and clear.json()["total"] == 0
    assert "Wages" not in caplog.text and CLEAR_SSN not in caplog.text


async def test_ac22_lena_walled_from_ashford_reads_every_viewer_route_as_never_existed(
    world: World,
) -> None:
    base = f"/v1/evidence-versions/{world.w2}"
    for path in (
        f"{base}/viewer",
        f"{base}/pages/1",
        f"{base}/text",
        f"{base}/search?q=Wages",
        f"{base}/regions?match_ids=x",
    ):
        response = await world.net.call("GET", path, world.lena)
        assert (response.status_code, response.json()) == (404, NOT_FOUND), path
    reveal = await world.net.call(
        "POST",
        f"{base}/pii-reveals",
        world.lena,
        body={"region_id": str(await world.region("ssn"))},
    )
    assert reveal.status_code == 404
    assert await world.reveals(world.lena) == 0


async def test_activity_reruns_write_no_second_trust_layer_row(world: World) -> None:
    """Word-layer replay at the activity boundary: words, scan and masked preview are idempotent
    on (source, version), so a retried or replayed activity adds nothing."""
    tables = ("evidence_pages", "pii_scan_runs", "pii_regions", "upload_previews")

    async def counts() -> list[int]:
        found: list[int] = []
        for table in tables:
            value = await world.seed.value(
                f"SELECT count(*) FROM {table} WHERE evidence_version_id = $1",  # noqa: S608
                world.w2,
            )
            found.append(int(str(value)))
        return found

    before = await counts()
    given = UploadInput(str(world.tenant_id), UPLOAD_VERSION, str(world.w2))
    await words_upload(given)
    await pii_scan_upload(given)
    await masked_preview_upload(given)
    assert await counts() == before
    assert all(n > 0 for n in before)


# --- Story 4: masked PII, offshore readers and the logged reveal -----------------------------


async def test_ac23_the_w2_box_a_ssn_is_a_sealed_region(world: World) -> None:
    rows = await world.seed.rows(
        "SELECT kind, last4, value_sealed FROM pii_regions WHERE evidence_version_id = $1",
        world.w2,
    )
    ssn = [r for r in rows if r["kind"] == "ssn"]
    assert [r["last4"] for r in ssn] == ["6081"]
    assert CLEAR_SSN.encode() not in bytes(ssn[0]["value_sealed"])
    assert b"000006081" not in bytes(ssn[0]["value_sealed"])


async def test_ac28_an_offshore_reader_gets_the_text_view_and_no_page_image(world: World) -> None:
    base = f"/v1/evidence-versions/{world.w2}"
    manifest = await world.net.call("GET", f"{base}/viewer", world.remy)
    assert manifest.status_code == 200, manifest.text
    assert manifest.json()["view"] == "text"
    assert "pii.reveal" not in manifest.json()["allowed_actions"]
    page = await world.net.call("GET", f"{base}/pages/1", world.remy)
    assert (page.status_code, page.json()) == (403, FORBIDDEN)
    text = await world.net.call("GET", f"{base}/text", world.remy)
    assert text.status_code == 200, text.text
    assert text.headers["cache-control"] == "no-store"
    [item] = text.json()["items"]
    assert SSN_MASK in item["text"] and CLEAR_SSN not in item["text"]
    assert CLEAR_EIN not in text.text and not has_tin(text.text)


async def test_ac30_a_page_no_scan_reads_is_not_scannable_and_refused_offshore(
    world: World,
) -> None:
    version = await world.upload(scanned_pdf())
    base = f"/v1/evidence-versions/{version}"
    manifest = await world.net.call("GET", f"{base}/viewer", world.samuel)
    assert manifest.status_code == 200, manifest.text
    assert [p["pii_scan"] for p in manifest.json()["pages"]] == ["not_scannable"]
    onshore = await world.net.call("GET", f"{base}/pages/1", world.samuel)
    assert onshore.status_code == 200, onshore.text
    offshore = await world.net.call("GET", f"{base}/pages/1", world.remy)
    assert (offshore.status_code, offshore.json()) == (403, FORBIDDEN)
    text = await world.net.call("GET", f"{base}/text", world.remy)
    assert text.status_code == 200, text.text
    assert [i["unread"] for i in text.json()["items"]] == [True]


async def test_ac26_samuel_reveals_the_ssn_once_logged_without_the_value(world: World) -> None:
    region = await world.region("ssn")
    response = await world.net.call(
        "POST",
        f"/v1/evidence-versions/{world.w2}/pii-reveals",
        world.samuel,
        body={"region_id": str(region)},
    )
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers.get("pragma") == "no-cache"
    body = response.json()
    assert (body["value"], body["kind"], body["expires_in"]) == (CLEAR_SSN, "ssn", 30)
    assert body["mask_id"] == str(region)
    assert body["revealed_by"] and body["revealed_at"]
    [row] = await world.seed.rows(
        "SELECT reason_code, mfa_at, revealed_at, expires_at, region_id FROM pii_reveals "
        "WHERE tenant_id = $1 AND user_id = $2",
        world.tenant_id,
        world.samuel.user_id,
    )
    assert (row["reason_code"], row["region_id"]) == ("source_review", region)
    assert row["mfa_at"] is not None
    assert row["expires_at"] - row["revealed_at"] == timedelta(seconds=30)
    [audited] = await world.audit("pii.revealed")
    assert (audited["actor_kind"], audited["actor_id"]) == ("human", str(world.samuel.user_id))
    assert audited["target_id"] == str(world.w2)
    assert "6081" not in json.dumps(dict(audited), default=str)
    accessed = await world.seed.rows(
        "SELECT kind, subject_type, subject_id, flags FROM access_events "
        "WHERE tenant_id = $1 AND actor_id = $2 AND kind = 'pii.revealed'",
        world.tenant_id,
        world.samuel.user_id,
    )
    assert [(a["subject_type"], a["subject_id"]) for a in accessed] == [("pii_region", region)]
    assert "pii_tin" in accessed[0]["flags"]
    outbox = await world.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type LIKE 'pii.%'",
        world.tenant_id,
    )
    assert outbox == 0  # audit only, never fanned out


async def test_ac26_an_ein_reveals_as_the_form_prints_it(world: World) -> None:
    response = await world.net.call(
        "POST",
        f"/v1/evidence-versions/{world.w2}/pii-reveals",
        world.samuel,
        body={"region_id": str(await world.region("ein"))},
    )
    assert response.status_code == 201, response.text
    assert (response.json()["value"], response.json()["kind"]) == (CLEAR_EIN, "ein")


async def test_ac27_a_reveal_without_recent_mfa_asks_for_a_step_up(world: World) -> None:
    response = await world.net.call(
        "POST",
        f"/v1/evidence-versions/{world.w2}/pii-reveals",
        world.samuel,
        body={"region_id": str(await world.region("ssn"))},
        mfa=False,
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "forbidden"
    assert response.json()["facts"]["reason"] == "mfa_required"
    assert CLEAR_SSN not in response.text
    assert await world.reveals(world.samuel) == 0
    manifest = await world.net.call(
        "GET", f"/v1/evidence-versions/{world.w2}/viewer", world.samuel, mfa=False
    )
    assert "pii.reveal" in manifest.json()["allowed_actions"]  # the chip shows; step-up follows


@pytest.mark.parametrize("who", ["remy", "rhea", "client", "cora"])
async def test_ac28_the_reveal_is_refused_and_no_value_leaves_the_server(
    world: World, who: str
) -> None:
    person = cast(Person, getattr(world, who))
    response = await world.net.call(
        "POST",
        f"/v1/evidence-versions/{world.w2}/pii-reveals",
        person,
        body={"region_id": str(await world.region("ssn"))},
    )
    if who in {"remy", "rhea", "client"}:
        assert (response.status_code, response.json()) == (403, FORBIDDEN)
    else:  # client_service: refused, as forbidden or as never-existed
        assert response.status_code in {403, 404}, response.text
    assert CLEAR_SSN not in response.text and "6081" not in response.text
    assert await world.reveals(person) == 0
    assert await world.audit("pii.revealed") == []


async def test_ac28_a_region_of_another_version_is_not_found(world: World) -> None:
    other = await world.upload(w2_pdf())
    response = await world.net.call(
        "POST",
        f"/v1/evidence-versions/{world.w2}/pii-reveals",
        world.samuel,
        body={"region_id": str(await world.region("ssn", other))},
    )
    assert response.status_code == 404, response.text
    assert CLEAR_SSN not in response.text
    assert await world.reveals(world.samuel) == 0


async def test_ac28_the_database_holds_no_machine_or_anonymous_reveal(world: World) -> None:
    region = await world.region("ssn")
    with pytest.raises(asyncpg.CheckViolationError):
        await world.seed.run(
            "INSERT INTO pii_reveals (tenant_id, region_id, evidence_version_id, user_id, "
            "actor_kind, expires_at) VALUES ($1, $2, $3, $4, 'agent', "
            "clock_timestamp() + interval '30 seconds')",
            world.tenant_id,
            region,
            world.w2,
            world.samuel.user_id,
        )
    with pytest.raises(asyncpg.NotNullViolationError):
        await world.seed.run(
            "INSERT INTO pii_reveals (tenant_id, region_id, evidence_version_id, user_id, "
            "actor_kind, expires_at) VALUES ($1, $2, $3, NULL, 'human', "
            "clock_timestamp() + interval '30 seconds')",
            world.tenant_id,
            region,
            world.w2,
        )


async def test_ac29_the_twenty_first_reveal_in_an_hour_is_throttled_and_audited(
    world: World,
) -> None:
    region = await world.region("ssn")
    for _ in range(20):
        await world.seed.run(
            "INSERT INTO pii_reveals (tenant_id, region_id, evidence_version_id, user_id, "
            "actor_kind, expires_at) VALUES ($1, $2, $3, $4, 'human', "
            "clock_timestamp() + interval '30 seconds')",
            world.tenant_id,
            region,
            world.w2,
            world.samuel.user_id,
        )
    response = await world.net.call(
        "POST",
        f"/v1/evidence-versions/{world.w2}/pii-reveals",
        world.samuel,
        body={"region_id": str(region)},
    )
    assert response.status_code == 429, response.text
    body = response.json()
    assert body["detail"] == "reveal_rate_limited"
    assert body["facts"]["limit"] == 20 and body["facts"]["retry_after"] > 0
    assert CLEAR_SSN not in response.text
    assert await world.reveals(world.samuel) == 20
    assert len(await world.audit("pii.reveal_throttled")) == 1
