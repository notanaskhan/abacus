# ac-test-author: ayushkbhatia
"""SPEC-018, SPEC-021, SPEC-023 and SPEC-031 back-fills (TASK-033, TASK-037, TASK-039,
TASK-060; Q-03-T047, TASK-1438): request-list import, request item detail, uploads on the
client's behalf with the inbox, and the client hub; the client hub never returns a firm status
code or an agent field.

Boundary: `create_app()` over HTTP on the migrated Postgres and the compose S3 image, as the
firm's team, an outsider, another firm and the client's people. Workbooks are built here with
openpyxl; files go through the upload and inbox routes.

Later decisions and contracts followed instead of the specs' words:
- SPEC-018 AC-5 lists who may not import; F-03-T30 (ADR-147) adds `client_service` to
  `request_item.create`, so the refusals tested are staff, reviewer and the client.
- SPEC-021 AC-5 refuses "a client user" the versions and content routes; SPEC-020 and SPEC-031
  since gave `client_admin` `evidence.read` on client-visible items (`client_visible_only`), so the
  refusal tested is a client on an item hidden from the client, and anyone outside the
  engagement.
- SPEC-031's client words: the client history's `outcome` is `in_review`, `replaced`,
  `accepted`, `sent_back` or `not_accepted` (C5, `docs/contracts/portal-pbc.md` "client words");
  firm request codes (status-vocabulary `request`), review decision codes and screening words
  never appear in a client-hub answer.
"""

from __future__ import annotations

import io
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Final, cast

import httpx
import pytest
from openpyxl import Workbook
from types_boto3_s3 import S3Client

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import storage
from abacus_tools.synthetic.documents import letter_pdf

from .support import Net, Person, Seeder, Site

BUCKET: Final = "task1438-requests-client-hub"
MASTER: Final = b"task1438-requests-client-hub-master-key-01"
PDF: Final = "application/pdf"
XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# Firm-side words a client must never be handed (status-vocabulary `request`, `evidence_screening`,
# the review decisions) and the fields that carry an agent's work.
FIRM_CODES: Final = {
    "draft",
    "requested",
    "uploaded",
    "received",
    "returned",
    "not_applicable",
    "under_review",
    "passed",
    "flagged",
    "not_screened",
    "rejected",
    "reject",
    "accept",
    "send_back_pending",
}
AGENT_KEYS: Final = {
    "confidence",
    "rationale",
    "citations",
    "screening",
    "run_id",
    "agent",
    "agent_run_id",
    "proposal",
    "seen_proposal",
    "drafted",
    "suggested_action",
}
CLIENT_OUTCOMES: Final = {"in_review", "replaced", "accepted", "sent_back", "not_accepted"}


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


def _workbook(rows: list[list[object]], *, sheet: str = "PBC") -> bytes:
    book = Workbook()
    ws = book.active
    assert ws is not None
    ws.title = sheet
    for row in rows:
        ws.append(row)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        found: set[str] = set()
        for k, v in cast(dict[str, object], value).items():
            found |= {k} | _keys(v)
        return found
    if isinstance(value, list):
        found = set()
        for v in cast(list[object], value):
            found |= _keys(v)
        return found
    return set()


def _strings(value: object) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, dict):
        values = list(cast(dict[str, object], value).values())
    elif isinstance(value, list):
        values = cast(list[object], value)
    else:
        return set()
    found: set[str] = set()
    for v in values:
        found |= _strings(v)
    return found


@dataclass(frozen=True)
class World:
    net: Net
    tenant_id: uuid.UUID
    owner: Person
    manager: Person
    senior: Person
    staff: Person
    reviewer: Person
    outsider: Person  # a firm member not on the engagement
    client: Person  # client_admin
    contributor: Person  # client_contributor
    site: Site

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def base(self) -> str:
        return f"/v1/engagements/{self.site.engagement_id}"

    async def items(self, who: Person | None = None) -> list[dict[str, Any]]:
        response = await self.net.call("GET", f"{self.base}/request-items", who or self.manager)
        assert response.status_code == 200, response.text
        return cast(list[dict[str, Any]], response.json())

    async def upload(
        self,
        item: uuid.UUID,
        content: bytes,
        who: Person | None = None,
        *,
        name: str = "statement.pdf",
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        return await self.net.http.post(
            f"{self.base}/request-items/{item}/uploads",
            params={"filename": name, **(params or {})},
            content=content,
            headers={**self.net.headers(who or self.client), "Content-Type": PDF},
        )

    async def inbox_add(self, content: bytes, name: str, who: Person) -> httpx.Response:
        return await self.net.http.post(
            f"{self.base}/inbox",
            params={"filename": name},
            content=content,
            headers={**self.net.headers(who), "Content-Type": PDF},
        )

    async def preview(self, data: bytes, who: Person | None = None) -> httpx.Response:
        return await self.net.http.post(
            f"{self.base}/request-items/import/preview",
            content=data,
            headers={**self.net.headers(who or self.manager), "Content-Type": XLSX},
        )

    async def import_(
        self, data: bytes, who: Person | None = None, **mapping: str | int
    ) -> httpx.Response:
        params = {"sheet": "PBC", "description": 0, "area": 1, **mapping}
        return await self.net.http.post(
            f"{self.base}/request-items/import",
            params={k: str(v) for k, v in params.items()},
            content=data,
            headers={**self.net.headers(who or self.manager), "Content-Type": XLSX},
        )

    async def reason(self, applies_to: str) -> str:
        response = await self.net.call(
            "GET", f"{self.base}/review-reason-codes/{applies_to}", self.manager
        )
        assert response.status_code == 200, response.text
        codes = [c for c in response.json() if not c["requires_note"]] or response.json()
        return str(codes[0]["code"])


async def _member(seed: Seeder, site: Site, role: str) -> Person:
    who = await seed.person(site.tenant_id)
    await seed.member(site, who, cast(Any, role))
    return who


@pytest.fixture
async def world(net: Net, seed: Seeder) -> World:
    tenant_id = await seed.firm()
    owner = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, owner.user_id, "Granite")
    manager = await _member(seed, site, "manager")
    senior = await _member(seed, site, "senior")
    staff = await _member(seed, site, "staff")
    reviewer = await _member(seed, site, "reviewer")
    outsider = await seed.person(tenant_id)
    client = await seed.client_contact(site, "client_admin")
    contributor = await seed.client_contact(site, "client_contributor")
    return World(
        net,
        tenant_id,
        owner,
        manager,
        senior,
        staff,
        reviewer,
        outsider,
        client,
        contributor,
        site,
    )


# === SPEC-018: request list import (TASK-033) ================================================

HEADER: Final[list[object]] = ["Description", "Area", "Tier"]


def _pbc(n: int) -> list[list[object]]:
    rows: list[list[object]] = [HEADER]
    rows.extend([f"Request {i:02d}", "Cash", "B"] for i in range(1, n + 1))
    return rows


async def test_spec018_ac1_preview_returns_sheets_headers_twenty_rows_and_a_mapping(
    world: World,
) -> None:
    before_items = len(await world.items())
    before_audit = await world.seed.actions(world.tenant_id)
    response = await world.preview(_workbook(_pbc(25)))
    assert response.status_code == 200, response.text
    [sheet] = response.json()
    assert sheet["name"] == "PBC"
    assert sheet["headers"] == HEADER
    assert len(sheet["rows"]) == 20
    assert sheet["rows"][0] == ["Request 01", "Cash", "B"]
    assert (sheet["suggested_description"], sheet["suggested_area"]) == (0, 1)
    assert len(await world.items()) == before_items
    assert await world.seed.actions(world.tenant_id) == before_audit


async def test_spec018_ac2_import_creates_one_item_per_row_with_area_and_tier_and_audits_once(
    world: World,
) -> None:
    before = {i["id"] for i in await world.items()}
    rows: list[list[object]] = [
        HEADER,
        ["Bank confirmations for every account", "Cash", "A"],
        ["Fixed asset roll-forward", "Property and equipment", ""],
        ["", "Cash", "B"],  # empty: skipped
    ]
    response = await world.import_(_workbook(rows), tier=2)
    assert response.status_code == 201, response.text
    counts = response.json()
    assert (counts["created"], counts["empty"], counts["duplicates"]) == (2, 1, 0)
    assert counts["unmatched_areas"] == 2  # no methodology applied: the cells' own text
    created = {i["description"]: i for i in await world.items() if i["id"] not in before}
    assert set(created) == {"Bank confirmations for every account", "Fixed asset roll-forward"}
    assert created["Bank confirmations for every account"]["audit_area"] == "Cash"
    assert created["Bank confirmations for every account"]["retrievability_tier"] == "A"
    assert created["Fixed asset roll-forward"]["audit_area"] == "Property and equipment"
    assert created["Fixed asset roll-forward"]["retrievability_tier"] is None
    actions = await world.seed.actions(world.tenant_id)
    assert actions.count("request_list.imported") == 1


async def test_spec018_ac3_duplicates_are_skipped_case_and_space_insensitively(
    world: World,
) -> None:
    await world.seed.item(world.site, "Accounts receivable aging")
    rows: list[list[object]] = [
        HEADER,
        ["  accounts   RECEIVABLE aging ", "cash", ""],  # the item already on the engagement
        ["Inventory count sheets", "Inventory", ""],
        ["inventory  count sheets", "INVENTORY", ""],  # repeats a row of the file
    ]
    response = await world.import_(_workbook(rows))
    assert response.status_code == 201, response.text
    assert (response.json()["created"], response.json()["duplicates"]) == (1, 2)
    matching = [i for i in await world.items() if "receivable" in i["description"].lower()]
    assert [i["description"] for i in matching] == ["Accounts receivable aging"]  # unchanged


@pytest.mark.parametrize(
    "case",
    ["missing_column", "not_a_workbook", "no_such_sheet"],
)
async def test_spec018_ac4_a_bad_workbook_imports_nothing_and_names_its_problems(
    world: World, case: str
) -> None:
    before = len(await world.items())
    data = (
        b"PK\x03\x04 not really a workbook" if case == "not_a_workbook" else (_workbook(_pbc(3)))
    )
    mapping: dict[str, str | int] = {}
    if case == "missing_column":
        mapping = {"description": 7}
    if case == "no_such_sheet":
        mapping = {"sheet": "Elsewhere"}
    response = await world.import_(data, None, **mapping)
    assert response.status_code == 422, response.text
    problems = response.json()["detail"]
    assert problems and all(isinstance(p.get("type"), str) and p["type"] for p in problems)
    assert len(await world.items()) == before


@pytest.mark.parametrize("who", ["staff", "reviewer", "client"])
async def test_spec018_ac5_people_without_request_item_create_are_refused(
    world: World, who: str
) -> None:
    person = cast(Person, getattr(world, who))
    before = len(await world.items())
    preview = await world.preview(_workbook(_pbc(2)), person)
    imported = await world.import_(_workbook(_pbc(2)), person)
    assert preview.status_code == 403, preview.text
    assert imported.status_code == 403, imported.text
    assert len(await world.items()) == before


async def test_spec018_ac5_a_senior_may_import(world: World) -> None:
    response = await world.import_(_workbook(_pbc(1)), world.senior)
    assert response.status_code == 201, response.text


# === SPEC-021: request item detail (TASK-037) ================================================


async def _two_versions(world: World) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    item = await world.seed.item(world.site, f"Bank statement {uuid.uuid4().hex[:6]}")
    first = await world.upload(item, letter_pdf(), name="december.pdf")
    assert first.status_code == 201, first.text
    second = await world.upload(item, letter_pdf() + b"\n%second", name="december-v2.pdf")
    assert second.status_code == 201, second.text
    return (
        item,
        uuid.UUID(first.json()["evidence_version_id"]),
        uuid.UUID(second.json()["evidence_version_id"]),
    )


async def test_spec021_ac1_versions_newest_first_with_provenance(world: World) -> None:
    item, first, second = await _two_versions(world)
    response = await world.net.call(
        "GET", f"{world.base}/request-items/{item}/versions", world.staff
    )
    assert response.status_code == 200, response.text
    versions = response.json()
    assert [v["id"] for v in versions] == [str(second), str(first)]
    newest = versions[0]
    assert newest["file_name"] == "december-v2.pdf"
    assert newest["uploaded_by"] == str(world.client.user_id)
    assert newest["uploaded_by_name"]
    assert newest["media_type"] == PDF
    assert newest["size_bytes"] > 0 and len(newest["fingerprint"]) >= 8
    assert newest["version_no"] > versions[1]["version_no"]


async def test_spec021_ac2_download_is_an_attachment_audited_and_verified(world: World) -> None:
    _item, first, _second = await _two_versions(world)
    before = (await world.seed.actions(world.tenant_id)).count("evidence_version.read")
    response = await world.net.call(
        "GET", f"{world.base}/evidence-versions/{first}/content", world.staff
    )
    assert response.status_code == 200, response.text
    assert response.content == letter_pdf()
    assert response.headers["content-type"].startswith(PDF)
    assert response.headers["content-disposition"].startswith("attachment")
    after = (await world.seed.actions(world.tenant_id)).count("evidence_version.read")
    assert after == before + 1


async def test_spec021_ac2_content_whose_fingerprint_does_not_match_is_refused(
    world: World,
) -> None:
    _item, first, _second = await _two_versions(world)
    await world.seed.run_untriggered(
        "UPDATE evidence_versions SET fingerprint = $2 WHERE id = $1", first, "0" * 64
    )
    response = await world.net.call(
        "GET", f"{world.base}/evidence-versions/{first}/content", world.staff
    )
    assert response.status_code == 409, response.text
    assert response.content != letter_pdf()


async def test_spec021_ac4_a_manager_sends_back_the_newest_and_the_detail_shows_it(
    world: World,
) -> None:
    item, _first, second = await _two_versions(world)
    code = await world.reason("send_back")
    decided = await world.net.call(
        "POST",
        f"{world.base}/evidence-versions/{second}/decision/send-back",
        world.manager,
        body={"reason_code": code, "note": "Please send all pages."},
    )
    assert decided.status_code == 201, decided.text
    versions = (
        await world.net.call("GET", f"{world.base}/request-items/{item}/versions", world.staff)
    ).json()
    assert versions[0]["decision"]["decision"] in {"send_back", "sent_back"}
    assert versions[0]["decision"]["reason_code"] == code
    assert versions[0]["decision"]["decided_by"] == str(world.manager.user_id)


async def test_spec021_ac4_a_person_without_the_right_sees_the_state_but_cannot_decide(
    world: World,
) -> None:
    _item, _first, second = await _two_versions(world)
    response = await world.net.call(
        "POST",
        f"{world.base}/evidence-versions/{second}/decision/accept",
        world.reviewer,
        body={},
    )
    assert response.status_code == 403, response.text


async def test_spec021_ac5_outside_the_engagement_the_versions_and_content_are_refused(
    world: World,
) -> None:
    item, first, _second = await _two_versions(world)
    for path in (
        f"{world.base}/request-items/{item}/versions",
        f"{world.base}/evidence-versions/{first}/content",
    ):
        response = await world.net.call("GET", path, world.outsider)
        assert response.status_code in {403, 404}, (path, response.text)
        assert response.content != letter_pdf()
    elsewhere = await world.seed.firm()
    stranger = await world.seed.person(elsewhere, "firm_admin")
    foreign = await world.net.call(
        "GET", f"{world.base}/evidence-versions/{first}/content", stranger
    )
    assert foreign.status_code in {403, 404}, foreign.text
    assert foreign.content != letter_pdf()


async def test_spec021_ac5_a_client_is_refused_an_item_hidden_from_the_client(
    world: World,
) -> None:
    item, first, _second = await _two_versions(world)
    hidden = await world.net.call(
        "PUT",
        f"{world.base}/request-items/{item}/client-visibility",
        world.manager,
        body={"client_visible": False},
    )
    assert hidden.status_code == 200, hidden.text
    for path in (
        f"{world.base}/request-items/{item}/versions",
        f"{world.base}/evidence-versions/{first}/content",
    ):
        response = await world.net.call("GET", path, world.client)
        assert response.status_code in {403, 404}, (path, response.text)
        assert response.content != letter_pdf()


# === SPEC-023: uploads on the client's behalf, the inbox and matching (TASK-039) =============


async def test_spec023_ac1_a_team_upload_for_the_client_is_marked_and_audited(
    world: World,
) -> None:
    item = await world.seed.item(world.site, "Loan agreement")
    response = await world.upload(
        item,
        letter_pdf(),
        world.staff,
        name="loan.pdf",
        params={"on_behalf": "true", "note": "Handed over at the planning meeting"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["on_behalf"] is True
    assert body["note"] == "Handed over at the planning meeting"
    assert body["uploaded_by"] == str(world.staff.user_id)
    version = uuid.UUID(body["evidence_version_id"])
    source = await world.seed.value("SELECT source FROM evidence_versions WHERE id = $1", version)
    assert source == "firm_upload_for_client"
    status = next(i for i in await world.items() if i["id"] == str(item))["status"]
    assert status != "requested"  # the item is received
    assert any("upload" in a for a in await world.seed.actions(world.tenant_id))
    view = await world.net.call(
        "GET", f"{world.base}/request-items/{item}/client-view", world.client
    )
    assert view.status_code == 200, view.text
    [entry] = view.json()["history"]
    assert entry["added_by"] == "firm"  # "Added by your auditor"


async def test_spec023_ac2_dropped_files_wait_unassigned_and_a_duplicate_is_refused(
    world: World,
) -> None:
    await world.seed.item(world.site, "Bank statements for December")
    added = await world.inbox_add(letter_pdf(), "Bank statements December.pdf", world.client)
    assert added.status_code == 201, added.text
    body = added.json()
    assert len(body["suggestions"]) <= 3
    listed = await world.net.call("GET", f"{world.base}/inbox", world.manager)
    assert str(body["id"]) in {f["id"] for f in listed.json()}
    again = await world.inbox_add(letter_pdf(), "Again.pdf", world.client)
    assert again.status_code == 409, again.text


async def test_spec023_ac3_suggestions_show_score_and_words_and_a_contributor_sees_only_theirs(
    world: World,
) -> None:
    mine = await world.seed.item(
        world.site, "Payroll register December", assignee=world.contributor
    )
    theirs = await world.seed.item(world.site, "Payroll tax returns December")
    added = await world.inbox_add(letter_pdf(), "Payroll December.pdf", world.contributor)
    assert added.status_code == 201, added.text
    suggestions = added.json()["suggestions"]
    assert suggestions, "a file named after two items is matched"
    for s in suggestions:
        assert isinstance(s["score"], int) and s["matched"]
    seen = {s["request_item_id"] for s in suggestions}
    assert str(mine) in seen
    assert str(theirs) not in seen
    for f in (await world.net.call("GET", f"{world.base}/inbox", world.contributor)).json():
        assert str(theirs) not in {s["request_item_id"] for s in f["suggestions"]}


async def test_spec023_ac4_assigning_makes_evidence_audits_and_empties_the_inbox(
    world: World,
) -> None:
    item = await world.seed.item(world.site, "Insurance policy")
    added = await world.inbox_add(letter_pdf(), "policy.pdf", world.client)
    file_id = added.json()["id"]
    assigned = await world.net.call(
        "POST",
        f"{world.base}/inbox/{file_id}/assign",
        world.manager,
        body={"request_item_id": str(item), "followed_suggestion": False},
    )
    assert assigned.status_code == 201, assigned.text
    version = assigned.json()["evidence_version_id"]
    uploads = await world.net.call(
        "GET", f"{world.base}/request-items/{item}/uploads", world.manager
    )
    assert version in {u["evidence_version_id"] for u in uploads.json()}
    inbox = await world.net.call("GET", f"{world.base}/inbox", world.manager)
    assert file_id not in {f["id"] for f in inbox.json()}
    audited = await world.seed.rows(
        "SELECT to_jsonb(a)::text AS doc FROM audit_events a WHERE tenant_id = $1 "
        "AND action LIKE 'inbox%' ORDER BY seq",
        world.tenant_id,
    )
    assert any("followed" in str(r["doc"]) for r in audited)


async def test_spec023_ac4_an_item_that_takes_no_more_evidence_refuses_the_file(
    world: World,
) -> None:
    item = await world.seed.item(world.site, "Lease schedule", status="not_applicable")
    added = await world.inbox_add(letter_pdf(), "lease.pdf", world.client)
    file_id = added.json()["id"]
    refused = await world.net.call(
        "POST",
        f"{world.base}/inbox/{file_id}/assign",
        world.manager,
        body={"request_item_id": str(item)},
    )
    assert refused.status_code == 409, refused.text
    inbox = await world.net.call("GET", f"{world.base}/inbox", world.manager)
    assert file_id in {f["id"] for f in inbox.json()}


async def test_spec023_ac5_a_discarded_file_leaves_the_inbox_and_becomes_no_evidence(
    world: World,
) -> None:
    added = await world.inbox_add(letter_pdf(), "unrelated.pdf", world.client)
    file_id = added.json()["id"]
    before = await world.seed.value(
        "SELECT count(*) FROM evidence_versions WHERE tenant_id = $1", world.tenant_id
    )
    discarded = await world.net.call("POST", f"{world.base}/inbox/{file_id}/discard", world.client)
    assert discarded.status_code == 200, discarded.text
    inbox = await world.net.call("GET", f"{world.base}/inbox", world.manager)
    assert file_id not in {f["id"] for f in inbox.json()}
    after = await world.seed.value(
        "SELECT count(*) FROM evidence_versions WHERE tenant_id = $1", world.tenant_id
    )
    assert after == before
    assert any("discard" in a for a in await world.seed.actions(world.tenant_id))


# === SPEC-031: the client hub (TASK-060) =====================================================


async def _guided(world: World, item: uuid.UUID, **guidance: object) -> httpx.Response:
    body = {
        "why": "To confirm the cash balance at year end",
        "good_looks_like": "The bank's own statement for each account, covering December 31",
        "still_needed": "We still need 4471",
        "blocks_fieldwork": True,
        "effort": "medium",
        **guidance,
    }
    return await world.net.call(
        "PUT", f"{world.base}/request-items/{item}/guidance", world.manager, body=body
    )


async def test_spec031_ac1_the_client_sees_the_firms_words_due_date_and_assignee(
    world: World,
) -> None:
    item = await world.seed.item(world.site, "Bank statements for December")
    assert (await _guided(world, item)).status_code == 200
    mine = [i for i in await world.items(world.client) if i["id"] == str(item)]
    assert len(mine) == 1
    seen = mine[0]
    assert seen["description"] == "Bank statements for December"
    assert seen["why"] == "To confirm the cash balance at year end"
    assert seen["good_looks_like"].startswith("The bank's own statement")
    assert seen["still_needed"] == "We still need 4471"
    assert {"due_on", "client_assignee_user_id", "status"} <= set(seen)
    assert seen.get("guidance_source") != "drafted"


async def test_spec031_ac2_with_no_template_and_no_kind_the_fields_are_empty(
    world: World,
) -> None:
    item = await world.seed.item(world.site, "Minutes of board meetings")
    seen = next(i for i in await world.items(world.client) if i["id"] == str(item))
    assert (seen["why"], seen["good_looks_like"]) == (None, None)


async def test_spec031_ac2_a_document_kind_supplies_fixed_copy(world: World) -> None:
    item = await world.seed.item(world.site, "December statements")
    kind = await world.net.call(
        "PUT",
        f"{world.base}/request-items/{item}/document-kind",
        world.manager,
        body={"document_kind": "bank_statement"},
    )
    assert kind.status_code == 200, kind.text
    seen = next(i for i in await world.items(world.client) if i["id"] == str(item))
    assert seen["why"] and seen["good_looks_like"]
    assert seen["guidance_source"] == "kind_default"


async def test_spec031_ac3_only_partner_manager_or_senior_edit_guidance_and_it_is_audited(
    world: World,
) -> None:
    item = await world.seed.item(world.site, "Bank statements")
    before = len(await world.seed.actions(world.tenant_id))
    assert (await _guided(world, item)).status_code == 200
    assert len(await world.seed.actions(world.tenant_id)) == before + 1
    for who in (world.staff, world.reviewer, world.client):
        refused = await world.net.call(
            "PUT",
            f"{world.base}/request-items/{item}/guidance",
            who,
            body={"why": "Because", "blocks_fieldwork": False},
        )
        assert refused.status_code in {403, 404}, refused.text
    seen = next(i for i in await world.items() if i["id"] == str(item))
    assert seen["why"] == "To confirm the cash balance at year end"


async def test_spec031_ac5_no_trial_balance_means_no_gap_line(world: World) -> None:
    item = await world.seed.item(world.site, "Bank statements for December")
    await world.net.call(
        "PUT",
        f"{world.base}/request-items/{item}/document-kind",
        world.manager,
        body={"document_kind": "bank_statement"},
    )
    assert (await world.upload(item, letter_pdf())).status_code == 201
    view = await world.net.call(
        "GET", f"{world.base}/request-items/{item}/client-view", world.client
    )
    assert view.status_code == 200, view.text
    assert view.json()["gap"] is None


async def test_spec031_ac6_your_part_counts_items_left_blockers_and_effort(
    world: World,
) -> None:
    first = await world.seed.item(world.site, "Bank statements", assignee=world.contributor)
    second = await world.seed.item(world.site, "Loan agreement", assignee=world.contributor)
    await _guided(world, first, effort="small", blocks_fieldwork=True)
    await _guided(world, second, effort="large", blocks_fieldwork=False)
    response = await world.net.call(
        "GET", f"{world.base}/request-items/your-part", world.contributor
    )
    assert response.status_code == 200, response.text
    part = response.json()
    assert part == {"items_left": 2, "blocks_fieldwork": 1, "minutes": 15 + 120}


async def test_spec031_ac7_history_newest_first_with_send_back_reason_and_hidden_rejection_note(
    world: World,
) -> None:
    item = await world.seed.item(world.site, "Bank statements for December")
    first = await world.upload(item, letter_pdf(), name="first.pdf")
    first_id = first.json()["evidence_version_id"]
    back = await world.net.call(
        "POST",
        f"{world.base}/evidence-versions/{first_id}/decision/send-back",
        world.manager,
        body={"reason_code": await world.reason("send_back"), "note": "Page 2 is missing."},
    )
    assert back.status_code == 201, back.text
    second = await world.upload(item, letter_pdf() + b"\n%2", name="second.pdf")
    second_id = second.json()["evidence_version_id"]
    rejected = await world.net.call(
        "POST",
        f"{world.base}/evidence-versions/{second_id}/decision/reject",
        world.manager,
        body={"reason_code": await world.reason("reject"), "note": "Firm-only: wrong bank."},
    )
    assert rejected.status_code == 201, rejected.text
    view = await world.net.call(
        "GET", f"{world.base}/request-items/{item}/client-view", world.client
    )
    assert view.status_code == 200, view.text
    history = view.json()["history"]
    assert [h["evidence_version_id"] for h in history] == [second_id, first_id]
    assert history[0]["outcome"] == "not_accepted"
    assert history[0]["note"] is None
    assert "wrong bank" not in view.text
    assert history[1]["outcome"] == "sent_back"
    assert history[1]["reason_label"]
    assert history[1]["note"] == "Page 2 is missing."


async def test_q03t047_the_client_hub_returns_no_firm_status_code_and_no_agent_field(
    world: World,
) -> None:
    item = await world.seed.item(world.site, "Bank statements for December")
    await _guided(world, item)
    upload = await world.upload(item, letter_pdf())
    version = upload.json()["evidence_version_id"]
    await world.net.call(
        "POST",
        f"{world.base}/evidence-versions/{version}/decision/send-back",
        world.manager,
        body={"reason_code": await world.reason("send_back"), "note": "Please re-send."},
    )
    answers: list[object] = []
    for path in (
        f"{world.base}/request-items/{item}/client-view",
        f"{world.base}/request-items/your-part",
    ):
        response = await world.net.call("GET", path, world.client)
        assert response.status_code == 200, (path, response.text)
        answers.append(response.json())
    keys = _keys(answers)
    assert not keys & AGENT_KEYS, keys & AGENT_KEYS
    assert not {k for k in keys if k.startswith(("ai_", "agent_", "screening"))}
    assert not _strings(answers) & FIRM_CODES, _strings(answers) & FIRM_CODES
    outcomes = {h["outcome"] for h in cast(dict[str, Any], answers[0])["history"]}
    assert outcomes <= CLIENT_OUTCOMES
