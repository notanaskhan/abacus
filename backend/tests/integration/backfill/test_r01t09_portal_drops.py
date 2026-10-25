"""R-01-T09 (R-01 Story 2.1, 2.3; DEC-58 a, c, g; DEC-323): portal drops and their code-rule sort.

- A decisive match (kind plus date and account) lands the dropped statement on its request as a
  `rule` fulfilment by the platform for the dropper, awaiting a person; `Scan_0914.pdf` waits in
  the inbox with `portal.drop_unsorted` for the engagement's leads.
- No drop links outside the dropper's scope: a request the client can't see is never a target,
  a forged or unpublished binder answers 404.
- Limits are the one upload policy, in this contract's words: 413 `file_too_large`, 415
  `type_not_allowed`; a duplicate is accepted and flagged, never refused, and waits for a person.
- The poll answers the dropper's own batch only; a replayed `Idempotency-Key` is the same file.

Boundary: `create_app()` over HTTP, the migrated Postgres (superuser seeding where no route makes
the row), the compose S3 image, the extraction and sort activities' bodies.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import date
from typing import Final, cast

import httpx
import pytest
from types_boto3_s3 import S3Client

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import drops, storage
from abacus.modules.evidence.api import UPLOAD_INBOX, UploadInput
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.evidence.drops import sort_drop
from abacus.modules.evidence.uploads import MAX_UPLOAD_BYTES
from abacus_tools.synthetic.documents import bank_statement_pdf, letter_pdf

from .support import Net, Person, Seeder, Site

BUCKET: Final = "r01t09-portal-drops"
MASTER: Final = b"r01t09-portal-drops-master-key-0123456789ab"
STATEMENT: Final = bank_statement_pdf(
    start=date(2025, 12, 1), end=date(2025, 12, 31), last4="4410"
)


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
    claire: Person
    site: Site
    binder_id: uuid.UUID
    statement_item: uuid.UUID
    other_item: uuid.UUID

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    async def drop(
        self,
        content: bytes,
        name: str,
        *,
        batch: uuid.UUID,
        key: str | None = None,
        binder: uuid.UUID | None = None,
        who: Person | None = None,
    ) -> httpx.Response:
        return await self.net.http.post(
            f"/v1/portal/binders/{binder or self.binder_id}/drops",
            params={"filename": name},
            content=content,
            headers={
                **self.net.headers(who or self.claire),
                "Content-Type": "application/octet-stream",
                "X-Drop-Batch": str(batch),
                "Idempotency-Key": key or str(uuid.uuid4()),
            },
        )

    async def sorted(self, file_id: uuid.UUID) -> str:
        given = UploadInput(str(self.tenant_id), UPLOAD_INBOX, str(file_id))
        await extract_upload(given)
        return await sort_drop(given)

    async def poll(self, batch: uuid.UUID, who: Person | None = None) -> httpx.Response:
        return await self.net.call("GET", f"/v1/portal/drops/{batch}", who or self.claire)


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    for flag in ("portal.drop_sort",):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'R-01-T09')",
            tenant_id,
            flag,
        )
    owner = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, owner.user_id, "Feld")
    manager = await seed.person(tenant_id)
    await seed.member(site, manager, "manager")
    claire = await seed.client_contact(site, "client_admin")
    binder_id = cast(
        uuid.UUID,
        await seed.value("SELECT request_list_id FROM request_items WHERE id = $1", site.item_id),
    )
    await seed.run("UPDATE request_lists SET status = 'published' WHERE id = $1", binder_id)
    statement = await seed.item(site, "Estimated payment confirmation, account 4410")
    await seed.run(
        "UPDATE request_items SET document_kind = 'bank_statement', "
        "document_kind_source = 'override' WHERE id = $1",
        statement,
    )
    other = await seed.item(site, "Form 1095-C")
    return Firm(net, tenant_id, manager, claire, site, binder_id, statement, other)


async def test_story_2_1_a_decisive_match_is_a_rule_link_awaiting_a_person(firm: Firm) -> None:
    batch = uuid.uuid4()
    response = await firm.drop(STATEMENT, "estimated-payment-q4.pdf", batch=batch)
    assert response.status_code == 202, response.text
    file_id = uuid.UUID(response.json()["file_id"])
    assert await firm.sorted(file_id) == "rule_linked"
    assert await firm.sorted(file_id) == "rule_linked"  # idempotent
    links = await firm.seed.rows(
        "SELECT created_by_kind, request_item_id, evidence_version_id FROM fulfilments "
        "WHERE request_item_id = $1",
        firm.statement_item,
    )
    assert [(r["created_by_kind"], r["request_item_id"]) for r in links] == [
        ("rule", firm.statement_item)
    ]
    audit = await firm.seed.rows(
        "SELECT actor_kind, on_behalf_of_user_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'fulfilment.created'",
        firm.tenant_id,
    )
    assert [(a["actor_kind"], a["on_behalf_of_user_id"]) for a in audit] == [
        ("system", firm.claire.user_id)
    ]
    # Nothing is accepted on anyone's behalf (ADR-005): no review decision exists.
    assert (
        await firm.seed.value(
            "SELECT count(*) FROM review_decisions WHERE evidence_version_id = $1",
            links[0]["evidence_version_id"],
        )
        == 0
    )
    polled = await firm.poll(batch)
    assert polled.status_code == 200, polled.text
    body = polled.json()
    assert body["settled"] is True and body["binder_id"] == str(firm.binder_id)
    assert [(f["outcome"], f["request_item_id"]) for f in body["files"]] == [
        ("rule_linked", str(firm.statement_item))
    ]


async def test_story_2_1_no_decisive_match_waits_and_tells_the_leads(firm: Firm) -> None:
    batch = uuid.uuid4()
    response = await firm.drop(letter_pdf(), "Scan_0914.pdf", batch=batch)
    assert response.status_code == 202, response.text
    file_id = uuid.UUID(response.json()["file_id"])
    assert await firm.sorted(file_id) == "waiting"
    row = await firm.seed.rows(
        "SELECT status, sort_outcome, channel FROM inbox_files WHERE id = $1", file_id
    )
    assert (row[0]["status"], row[0]["sort_outcome"], row[0]["channel"]) == (
        "waiting",
        "waiting",
        "portal_drop",
    )
    outbox = await firm.seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = 'portal.drop_unsorted'",
        firm.tenant_id,
    )
    assert [json.loads(o["payload"])["inbox_file_id"] for o in outbox] == [str(file_id)]
    body = (await firm.poll(batch)).json()
    assert [(f["outcome"], f["request_item_id"]) for f in body["files"]] == [("waiting", None)]


async def test_story_2_1_no_drop_links_outside_the_droppers_scope(firm: Firm) -> None:
    # The only request the statement would match is hidden from the client: it waits.
    await firm.seed.run(
        "UPDATE request_items SET client_visible = false WHERE id = $1", firm.statement_item
    )
    response = await firm.drop(STATEMENT, "estimated-payment-q4.pdf", batch=uuid.uuid4())
    assert await firm.sorted(uuid.UUID(response.json()["file_id"])) == "waiting"
    assert (
        await firm.seed.value(
            "SELECT count(*) FROM fulfilments WHERE tenant_id = $1 AND created_by_kind = 'rule'",
            firm.tenant_id,
        )
        == 0
    )
    # A forged binder, and a binder not yet published, answer 404 (INV-4).
    forged = await firm.drop(STATEMENT, "a.pdf", batch=uuid.uuid4(), binder=uuid.uuid4())
    assert forged.status_code == 404
    await firm.seed.run("UPDATE request_lists SET status = 'draft' WHERE id = $1", firm.binder_id)
    draft = await firm.drop(STATEMENT, "a.pdf", batch=uuid.uuid4())
    assert draft.status_code == 404


async def test_story_2_3_the_one_policy_refuses_in_this_contracts_words(firm: Firm) -> None:
    big = await firm.drop(b"%PDF-1.4\n" + bytes(MAX_UPLOAD_BYTES), "big.pdf", batch=uuid.uuid4())
    assert (big.status_code, big.json()["detail"]) == (413, "file_too_large")
    zipped = await firm.drop(b"PK\x03\x04" + bytes(64), "photos.zip", batch=uuid.uuid4())
    assert (zipped.status_code, zipped.json()["detail"]) == (415, "type_not_allowed")
    renamed = await firm.drop(STATEMENT, "statement.xlsx", batch=uuid.uuid4())
    assert (renamed.status_code, renamed.json()["detail"]) == (415, "type_not_allowed")
    assert (
        await firm.seed.value(
            "SELECT count(*) FROM inbox_files WHERE tenant_id = $1", firm.tenant_id
        )
        == 0
    )


async def test_story_2_3_a_duplicate_is_accepted_flagged_and_waits(firm: Firm) -> None:
    first = await firm.drop(STATEMENT, "estimated-payment-q4.pdf", batch=uuid.uuid4())
    assert await firm.sorted(uuid.UUID(first.json()["file_id"])) == "rule_linked"
    batch = uuid.uuid4()
    again = await firm.drop(STATEMENT, "estimated-payment-q4 (1).pdf", batch=batch)
    assert again.status_code == 202, again.text
    file_id = uuid.UUID(again.json()["file_id"])
    assert await firm.sorted(file_id) == "waiting"  # a person decides about a duplicate
    flagged = await firm.seed.value(
        "SELECT duplicate_of_version_id FROM inbox_files WHERE id = $1", file_id
    )
    assert flagged is not None
    body = (await firm.poll(batch)).json()
    # DEC-323 (security review): the client reads `waiting`; only the firm sees the flag.
    assert [f["outcome"] for f in body["files"]] == ["waiting"]


async def test_the_poll_is_the_droppers_own_and_a_replay_is_the_same_file(firm: Firm) -> None:
    batch, key = uuid.uuid4(), str(uuid.uuid4())
    first = await firm.drop(letter_pdf(), "Scan_0914.pdf", batch=batch, key=key)
    replay = await firm.drop(letter_pdf(), "Scan_0914.pdf", batch=batch, key=key)
    assert first.status_code == replay.status_code == 202
    assert first.json()["file_id"] == replay.json()["file_id"]
    unsorted = (await firm.poll(batch)).json()
    assert unsorted["settled"] is False and unsorted["files"][0]["outcome"] is None
    other = await firm.seed.client_contact(firm.site, "client_admin")
    assert (await firm.poll(batch, other)).status_code == 404
    assert (await firm.poll(uuid.uuid4())).status_code == 404


async def test_the_drop_is_off_with_its_flag(net: Net, seed: Seeder) -> None:
    tenant_id = await seed.firm()
    owner = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, owner.user_id, "Off")
    claire = await seed.client_contact(site, "client_admin")
    response = await net.http.post(
        f"/v1/portal/binders/{uuid.uuid4()}/drops",
        params={"filename": "a.pdf"},
        content=b"%PDF-1.4",
        headers={
            **net.headers(claire),
            "X-Drop-Batch": str(uuid.uuid4()),
            "Idempotency-Key": "k",
        },
    )
    assert response.status_code == 404


# --- Security review (DEC-323) -------------------------------------------------------------------

ACTIVE: Final = STATEMENT.replace(
    b"%%EOF", b"99 0 obj << /S /JavaScript /JS (app.alert\\(1\\);) >> endobj\n%%EOF"
)


async def _forced(firm: Firm, monkeypatch: pytest.MonkeyPatch) -> None:
    """The sort's first read found the statement request decisive; what happens next is the
    link's own re-check (a change between the read and the link)."""

    async def decisive(_row: object, _tenant: object) -> uuid.UUID:
        return firm.statement_item

    monkeypatch.setattr(drops, "_decisive", decisive)


async def _rule_links(firm: Firm) -> int:
    found = await firm.seed.value(
        "SELECT count(*) FROM fulfilments WHERE tenant_id = $1 AND created_by_kind = 'rule'",
        firm.tenant_id,
    )
    return found if isinstance(found, int) else -1


@pytest.mark.parametrize("change", ["delegated", "hidden", "unpublished", "revoked"])
async def test_sec1_the_link_checks_the_droppers_scope_again(
    firm: Firm, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    response = await firm.drop(STATEMENT, "estimated-payment-q4.pdf", batch=uuid.uuid4())
    assert response.status_code == 202, response.text
    file_id = uuid.UUID(response.json()["file_id"])
    if change == "delegated":
        await firm.seed.run_untriggered(
            "INSERT INTO request_delegations (tenant_id, request_item_id, contact_id, grant_id, "
            "granted_by) VALUES ($1, $2, $3, $4, $5)",
            firm.tenant_id,
            firm.statement_item,
            uuid.uuid4(),
            uuid.uuid4(),
            firm.manager.user_id,
        )
    elif change == "hidden":
        await firm.seed.run(
            "UPDATE request_items SET client_visible = false WHERE id = $1", firm.statement_item
        )
    elif change == "unpublished":
        await firm.seed.run(
            "UPDATE request_lists SET status = 'draft' WHERE id = $1", firm.binder_id
        )
    else:
        await firm.seed.revoke(firm.claire)
    await _forced(firm, monkeypatch)
    assert await firm.sorted(file_id) == "waiting"
    assert await _rule_links(firm) == 0


async def test_sec2_the_drop_authorises_before_it_reads_the_file(firm: Firm) -> None:
    read: list[int] = []

    async def body() -> AsyncIterator[bytes]:
        read.append(1)
        yield STATEMENT

    response = await firm.net.http.post(
        f"/v1/portal/binders/{uuid.uuid4()}/drops",
        params={"filename": "a.pdf"},
        content=body(),
        headers={
            **firm.net.headers(firm.claire),
            "X-Drop-Batch": str(uuid.uuid4()),
            "Idempotency-Key": "k",
        },
    )
    assert response.status_code == 404
    assert read == []  # refused before a byte of the file was read


async def test_sec5_a_duplicate_reads_waiting_to_the_client(firm: Firm) -> None:
    first = await firm.drop(STATEMENT, "estimated-payment-q4.pdf", batch=uuid.uuid4())
    assert await firm.sorted(uuid.UUID(first.json()["file_id"])) == "rule_linked"
    batch = uuid.uuid4()
    again = await firm.drop(STATEMENT, "estimated-payment-q4 (1).pdf", batch=batch)
    file_id = uuid.UUID(again.json()["file_id"])
    assert await firm.sorted(file_id) == "waiting"  # the same bytes are on that request
    assert (
        await firm.seed.value(
            "SELECT duplicate_of_version_id FROM inbox_files WHERE id = $1", file_id
        )
        is not None
    )  # the firm still sees the duplicate
    body = (await firm.poll(batch)).json()
    assert [f["outcome"] for f in body["files"]] == ["waiting"]  # no oracle for the client


async def test_sec6_the_poll_authorises_every_binder_and_keys_are_per_person(
    firm: Firm,
) -> None:
    second = cast(
        uuid.UUID,
        await firm.seed.value(
            "INSERT INTO request_lists (tenant_id, engagement_id, status, part) "
            "VALUES ($1, $2, 'published', 2) RETURNING id",
            firm.tenant_id,
            firm.site.engagement_id,
        ),
    )
    batch = uuid.uuid4()
    one = await firm.drop(letter_pdf(), "a.pdf", batch=batch)
    two = await firm.drop(letter_pdf(), "b.pdf", batch=batch, binder=second)
    assert one.status_code == two.status_code == 202, two.text
    assert (await firm.poll(batch)).status_code == 200
    await firm.seed.run("UPDATE request_lists SET status = 'draft' WHERE id = $1", second)
    assert (await firm.poll(batch)).status_code == 404
    # Another person's (batch, key) never blocks or answers for mine.
    other = await firm.seed.client_contact(firm.site, "client_admin")
    key = str(uuid.uuid4())
    mine = await firm.drop(letter_pdf(), "c.pdf", batch=batch, key=key)
    theirs = await firm.drop(letter_pdf(), "c.pdf", batch=batch, key=key, who=other)
    assert mine.status_code == theirs.status_code == 202, theirs.text
    assert mine.json()["file_id"] != theirs.json()["file_id"]


async def test_sec7_an_active_content_drop_is_never_rule_linked(
    firm: Firm, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = await firm.drop(ACTIVE, "estimated-payment-q4.pdf", batch=uuid.uuid4())
    assert response.status_code == 202, response.text
    await _forced(firm, monkeypatch)
    assert await firm.sorted(uuid.UUID(response.json()["file_id"])) == "waiting"
    assert await _rule_links(firm) == 0


async def test_sec7_a_staff_drop_is_recorded_on_the_clients_behalf(firm: Firm) -> None:
    response = await firm.drop(
        STATEMENT, "estimated-payment-q4.pdf", batch=uuid.uuid4(), who=firm.manager
    )
    assert response.status_code == 202, response.text
    assert await firm.sorted(uuid.UUID(response.json()["file_id"])) == "rule_linked"
    sources = await firm.seed.rows(
        "SELECT v.source FROM fulfilments f JOIN evidence_versions v "
        "ON v.tenant_id = f.tenant_id AND v.id = f.evidence_version_id "
        "WHERE f.request_item_id = $1",
        firm.statement_item,
    )
    assert [s["source"] for s in sources] == ["firm_upload_for_client"]


# --- The staff void of a wrong rule link (R-01 Story 2.2; TASK-1248) ---------------------------


async def _rule_linked(
    firm: Firm, batch: uuid.UUID | None = None
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """A dropped statement the rule linked to its request: (file, fulfilment, version)."""
    dropped = await firm.drop(STATEMENT, "estimated-payment-q4.pdf", batch=batch or uuid.uuid4())
    file_id = uuid.UUID(dropped.json()["file_id"])
    assert await firm.sorted(file_id) == "rule_linked"
    [link] = await firm.seed.rows(
        "SELECT id, evidence_version_id FROM fulfilments WHERE request_item_id = $1 "
        "AND created_by_kind = 'rule'",
        firm.statement_item,
    )
    return file_id, link["id"], link["evidence_version_id"]


async def _void(
    firm: Firm, fulfilment_id: uuid.UUID, *, key: str | None = None, who: Person | None = None
) -> httpx.Response:
    return await firm.net.http.post(
        f"/v1/engagements/{firm.site.engagement_id}/fulfilments/{fulfilment_id}/void",
        json={"reason": "wrong_request"},
        headers={
            **firm.net.headers(who or firm.manager),
            "Idempotency-Key": key or str(uuid.uuid4()),
        },
    )


async def test_story_2_2_a_person_voids_a_wrong_rule_link(firm: Firm) -> None:
    batch = uuid.uuid4()
    file_id, fulfilment_id, version = await _rule_linked(firm, batch)
    key = str(uuid.uuid4())
    response = await _void(firm, fulfilment_id, key=key)
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["fulfilment_id"], body["request_item_id"], body["request_status"]) == (
        str(fulfilment_id),
        str(firm.statement_item),
        "requested",
    )
    [row] = await firm.seed.rows(
        "SELECT voided_at, voided_by, void_reason FROM fulfilments WHERE id = $1", fulfilment_id
    )
    assert row["voided_at"] is not None and row["void_reason"] == "wrong_request"
    assert row["voided_by"] == firm.manager.user_id
    [inbox] = await firm.seed.rows(
        "SELECT status, assigned_item_id, assigned_version_id, decided_at, sort_outcome "
        "FROM inbox_files WHERE id = $1",
        file_id,
    )
    assert (inbox["status"], inbox["assigned_item_id"], inbox["assigned_version_id"]) == (
        "waiting",
        None,
        None,
    )
    assert inbox["decided_at"] is None and inbox["sort_outcome"] == "rule_linked"
    status = await firm.seed.value(
        "SELECT status FROM request_items WHERE id = $1", firm.statement_item
    )
    assert status == "requested"
    audit = await firm.seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'fulfilment.voided'",
        firm.tenant_id,
    )
    assert [(a["actor_kind"], a["actor_id"]) for a in audit] == [
        ("human", str(firm.manager.user_id))
    ]
    events = await firm.seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = 'fulfilment.voided'",
        firm.tenant_id,
    )
    assert len(events) == 1 and json.loads(events[0]["payload"])["evidence_version_id"] == str(
        version
    )
    replay = await _void(firm, fulfilment_id, key=key)
    assert replay.status_code == 200 and replay.json() == body
    # The version is retired with the link (evidence reads leave it out), and the dropper's poll
    # reads the file as waiting, with no request.
    retired = await firm.seed.value(
        "SELECT voided_by FROM evidence_version_voids WHERE evidence_version_id = $1", version
    )
    assert retired == firm.manager.user_id
    polled = (await firm.poll(batch)).json()
    assert [(f["outcome"], f["request_item_id"]) for f in polled["files"]] == [("waiting", None)]
    # The request no longer reads the link.
    links = await firm.seed.value(
        "SELECT count(*) FROM fulfilments WHERE request_item_id = $1 AND voided_at IS NULL",
        firm.statement_item,
    )
    assert links == 0


async def test_story_2_2_only_an_unaccepted_rule_link_is_voidable(firm: Firm) -> None:
    _, fulfilment_id, version = await _rule_linked(firm)
    assert (await _void(firm, fulfilment_id)).status_code == 200
    again = await _void(firm, fulfilment_id)
    assert again.status_code == 409 and again.json() == {
        "detail": "not_voidable",
        "facts": {"fulfilment_id": str(fulfilment_id)},
    }
    # A link a person made is theirs to change, never a void's.
    human = cast(
        uuid.UUID,
        await firm.seed.value(
            "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
            "evidence_version_id, created_by_kind, created_by_id) VALUES ($1, $2, $3, $4, "
            "'human', $5) RETURNING id",
            firm.tenant_id,
            firm.site.engagement_id,
            firm.other_item,
            version,
            str(firm.manager.user_id),
        ),
    )
    assert (await _void(firm, human)).json()["detail"] == "not_voidable"


async def test_story_2_2_an_accepted_rule_link_is_not_voidable(firm: Firm) -> None:
    _, fulfilment_id, version = await _rule_linked(firm)
    await firm.seed.run_untriggered(
        "INSERT INTO review_decisions (tenant_id, engagement_id, evidence_version_id, "
        "request_item_id, decision, corrects_proposal, actor_kind, actor_id) VALUES "
        "($1, $2, $3, $4, 'accept', false, 'human', $5)",
        firm.tenant_id,
        firm.site.engagement_id,
        version,
        firm.statement_item,
        str(firm.manager.user_id),
    )
    refused = await _void(firm, fulfilment_id)
    assert refused.status_code == 409 and refused.json()["detail"] == "not_voidable"
    assert (
        await firm.seed.value("SELECT voided_at FROM fulfilments WHERE id = $1", fulfilment_id)
        is None
    )


async def test_story_2_2_a_client_or_another_firm_cannot_void(firm: Firm, seed: Seeder) -> None:
    _, fulfilment_id, _ = await _rule_linked(firm)
    assert (await _void(firm, fulfilment_id, who=firm.claire)).status_code in (403, 404)
    other_tenant = await seed.firm()
    outsider = await seed.person(other_tenant, "firm_admin")
    assert (await _void(firm, fulfilment_id, who=outsider)).status_code in (403, 404)
    assert (
        await firm.seed.value("SELECT voided_at FROM fulfilments WHERE id = $1", fulfilment_id)
        is None
    )


async def test_story_2_2_the_database_refuses_any_other_change_to_a_fulfilment(
    firm: Firm,
) -> None:
    _, fulfilment_id, _ = await _rule_linked(firm)
    with pytest.raises(Exception, match="fulfilment"):
        await firm.seed.run(
            "UPDATE fulfilments SET request_item_id = $2 WHERE id = $1",
            fulfilment_id,
            firm.other_item,
        )
    with pytest.raises(Exception, match="retired only"):  # a retire without its void
        await firm.seed.run(
            "INSERT INTO evidence_version_voids (tenant_id, evidence_version_id, engagement_id, "
            "fulfilment_id, voided_by) SELECT tenant_id, evidence_version_id, engagement_id, id, "
            "$2 FROM fulfilments WHERE id = $1",
            fulfilment_id,
            firm.manager.user_id,
        )
    with pytest.raises(Exception, match="fulfilment"):  # a void not made by the acting person
        await firm.seed.run(
            "UPDATE fulfilments SET voided_at = now(), voided_by = $2, "
            "void_reason = 'wrong_request' WHERE id = $1",
            fulfilment_id,
            firm.manager.user_id,
        )


async def test_story_2_2_the_void_is_off_with_its_flag(net: Net, seed: Seeder) -> None:
    tenant_id = await seed.firm()
    owner = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, owner.user_id, "Flagless")
    response = await net.http.post(
        f"/v1/engagements/{site.engagement_id}/fulfilments/{uuid.uuid4()}/void",
        json={"reason": "wrong_request"},
        headers={**net.headers(owner), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 404
