# ac-test-author: ayushkbhatia
"""R-01-T15: independent acceptance tests (ADR-078) for R-01-T09, the portal drop and its code-rule
sort, written in AY's session from the plan and the contract, not from the implementing suite.

Sources: R-01 Stories 2.1 to 2.3 (`docs/plan/epics/R-01.md` §3.2), §4.2 (`00NN_portal_drop_sort`),
§4.3 (the drop, the poll and the void), §4.4 (the `portal_drop_sort` patched step and its replay);
`docs/contracts/portal-pbc.md` §2, §5 to §7; DEC-58 (a, c, g), ADR-005, ADR-090, INV-1, INV-4,
INV-5. The row: "drop scope (no link outside the dropper's visible items, drafts, delegated items
or closed binders), rule link only on a decisive match, agent denied fulfilment.confirm, void only
for unaccepted rule links, 50 MB and HEIC limits, duplicate flag, replay of the pre-change
upload_processing history".

HTTP through `create_app()` against the migrated Postgres and the compose S3 image, as the client
(the dropper) and the firm's manager; the sort runs the extraction and sort activity bodies the
`upload_processing` workflow schedules. "Decisive" is the plan's words: the top request matched on
kind plus a date or an account and scores at least twice the next. A statement for the account
ending 7302 for December 2025 (the engagement's year end) matches one request on all three.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Final, cast

import httpx
import pytest
from temporalio import workflow
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner
from types_boto3_s3 import S3Client

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import UPLOAD_INBOX, UploadInput, UploadProcessing
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus.modules.evidence.drops import sort_drop
from abacus.modules.identity.api import RULES
from abacus_tools.synthetic.documents import bank_statement_pdf

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio

BUCKET: Final = "r01t15-drops-independent"
MASTER: Final = b"r01t15-drops-independent-master-key-01234567"
MB: Final = 1024 * 1024
LAST4: Final = "7302"
TITLE: Final = f"Operating account ending {LAST4}: December 2025 statement"
STATEMENT: Final = bank_statement_pdf(
    start=date(2025, 12, 1), end=date(2025, 12, 31), last4=LAST4, holder="Feld Household"
)
HISTORIES: Final = Path(__file__).resolve().parents[2] / "workflows" / "histories"
Json = dict[str, object]


@pytest.fixture(scope="module")
def bucket(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture(autouse=True)
def stored(bucket: S3Client) -> Iterator[None]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(bucket, BUCKET)
    yield
    storage.reset_storage()
    reset_key_service()


@dataclass(frozen=True)
class Feld:
    net: Net
    tenant: uuid.UUID
    manager: Person
    claire: Person  # client admin: drops on the binder
    site: Site
    binder: uuid.UUID
    statement: uuid.UUID  # the one request the statement matches decisively
    other: uuid.UUID

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    async def drop(
        self,
        content: bytes,
        name: str,
        *,
        who: Person | None = None,
        binder: uuid.UUID | None = None,
        batch: uuid.UUID | None = None,
    ) -> httpx.Response:
        return await self.net.http.post(
            f"/v1/portal/binders/{binder or self.binder}/drops",
            params={"filename": name},
            content=content,
            headers={
                **self.net.headers(who or self.claire),
                "Content-Type": "application/octet-stream",
                "X-Drop-Batch": str(batch or uuid.uuid4()),
                "Idempotency-Key": uuid.uuid4().hex,
            },
        )

    async def dropped(self, content: bytes, name: str, *, who: Person | None = None) -> uuid.UUID:
        response = await self.drop(content, name, who=who)
        assert response.status_code == 202, response.text
        return uuid.UUID(cast(str, response.json()["file_id"]))

    async def sort(self, file_id: uuid.UUID) -> str:
        given = UploadInput(str(self.tenant), UPLOAD_INBOX, str(file_id))
        await extract_upload(given)
        return await sort_drop(given)

    async def links(self, item: uuid.UUID) -> list[Json]:
        rows = await self.seed.rows(
            "SELECT id, evidence_version_id, created_by_kind, voided_at FROM fulfilments "
            "WHERE request_item_id = $1 ORDER BY created_at",
            item,
        )
        return [dict(r) for r in rows]

    async def rule_links(self) -> int:
        return cast(
            int,
            await self.seed.value(
                "SELECT count(*) FROM fulfilments WHERE engagement_id = $1 "
                "AND created_by_kind = 'rule'",
                self.site.engagement_id,
            ),
        )

    async def inbox(self, file_id: uuid.UUID) -> Json:
        row = await self.seed.rows(
            "SELECT channel, sort_outcome, duplicate_of_version_id, status FROM inbox_files "
            "WHERE id = $1",
            file_id,
        )
        return dict(row[0])


async def _flag(seed: Seeder, tenant: uuid.UUID, flag: str) -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'R-01-T15')",
        tenant,
        flag,
    )


async def _statement_request(seed: Seeder, site: Site, title: str) -> uuid.UUID:
    item = await seed.item(site, title)
    await seed.run(
        "UPDATE request_items SET title = $2, document_kind = 'bank_statement', "
        "document_kind_source = 'override', client_visible = true WHERE id = $1",
        item,
        title,
    )
    return item


@pytest.fixture
async def feld(net: Net, seed: Seeder) -> Feld:
    tenant = await seed.firm()
    await _flag(seed, tenant, "portal.drop_sort")
    admin = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "Feld")
    manager = await seed.person(tenant)
    await seed.member(site, manager, "manager")
    claire = await seed.client_contact(site, "client_admin")
    binder = cast(
        uuid.UUID,
        await seed.value("SELECT request_list_id FROM request_items WHERE id = $1", site.item_id),
    )
    await seed.run(
        "UPDATE request_lists SET status = 'published', published_at = now() WHERE id = $1",
        binder,
    )
    statement = await _statement_request(seed, site, TITLE)
    other = await seed.item(site, "Form 1095-C From Mercer Hill Health")
    await seed.run("UPDATE request_items SET client_visible = true WHERE id = $1", other)
    return Feld(net, tenant, manager, claire, site, binder, statement, other)


# ================================================================================================
# A rule link only on a decisive match, by the platform for the dropper, awaiting a person
# ================================================================================================


async def test_story21_a_decisive_match_is_a_rule_link_awaiting_a_person(feld: Feld) -> None:
    file_id = await feld.dropped(STATEMENT, f"Statement_{LAST4}_2025-12.pdf")
    assert await feld.sort(file_id) == "rule_linked"
    [link] = await feld.links(feld.statement)
    assert link["created_by_kind"] == "rule" and link["voided_at"] is None
    status = await feld.seed.value(
        "SELECT status FROM request_items WHERE id = $1", feld.statement
    )
    assert status == "uploaded"  # Done to the client; needs review firm-side
    accepted = await feld.seed.rows(
        "SELECT 1 FROM review_decisions WHERE evidence_version_id = $1",
        link["evidence_version_id"],
    )
    assert accepted == []  # nobody accepted it: a person does (ADR-005)
    audit = await feld.seed.rows(
        "SELECT actor_kind, on_behalf_of_user_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'fulfilment.created' AND target_id = $2",
        feld.tenant,
        str(link["id"]),
    )
    assert [(a["actor_kind"], a["on_behalf_of_user_id"]) for a in audit] == [
        ("system", feld.claire.user_id)
    ]  # INV-5
    assert (await feld.inbox(file_id))["sort_outcome"] == "rule_linked"


async def test_story21_two_requests_matching_alike_is_not_decisive_and_waits(feld: Feld) -> None:
    await _statement_request(feld.seed, feld.site, f"Account {LAST4} bank statement Dec 2025")
    file_id = await feld.dropped(STATEMENT, f"Statement_{LAST4}_2025-12.pdf")
    assert await feld.sort(file_id) == "waiting"
    assert await feld.rule_links() == 0


async def test_story21_a_file_matching_nothing_waits_for_a_person(feld: Feld) -> None:
    file_id = await feld.dropped(b"%PDF-1.4\n%unreadable scan\n", "Scan_0914.pdf")
    assert await feld.sort(file_id) == "waiting"
    assert await feld.rule_links() == 0
    assert (await feld.inbox(file_id))["channel"] == "portal_drop"


async def test_story21_with_the_drop_sort_off_nothing_is_rule_linked(feld: Feld) -> None:
    file_id = await feld.dropped(STATEMENT, f"Statement_{LAST4}_2025-12.pdf")
    await feld.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 AND flag = $2",
        feld.tenant,
        "portal.drop_sort",
    )
    forget_flags()
    response = await feld.drop(STATEMENT, "Again.pdf")
    assert response.status_code == 404  # the contract: the drop route is off with its flag
    # Story 2.1: a file dropped before the switch takes the "will sort this" path, never a link.
    assert await feld.sort(file_id) == "waiting"
    assert await feld.rule_links() == 0


# ================================================================================================
# INV-4: never a link outside what the dropper can see
# ================================================================================================


async def _delegate(feld: Feld, item: uuid.UUID) -> None:
    contact = await feld.seed.value(
        "INSERT INTO contacts (tenant_id, client_id, display_name, email, organisation_name, "
        "contact_kind) VALUES ($1, $2, 'Sam Ortiz', $3, 'Keystone', 'third_party') RETURNING id",
        feld.tenant,
        feld.site.client_id,
        f"sam.{uuid.uuid4().hex[:6]}@example.test",
    )
    grant = await feld.seed.value(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id, "
        "contact_id, status) VALUES ($1, NULL, 'third_party', 'request_item', $2, $3, "
        "'pending') RETURNING id",
        feld.tenant,
        item,
        contact,
    )
    await feld.seed.run(
        "INSERT INTO request_delegations (tenant_id, request_item_id, contact_id, grant_id, "
        "granted_by) VALUES ($1, $2, $3, $4, $5)",
        feld.tenant,
        item,
        contact,
        grant,
        feld.manager.user_id,
    )


@pytest.mark.parametrize("hidden", ["internal_only", "draft", "delegated"])
async def test_inv4_the_only_match_out_of_the_droppers_sight_is_never_linked(
    feld: Feld, hidden: str
) -> None:
    if hidden == "internal_only":
        await feld.seed.run(
            "UPDATE request_items SET client_visible = false WHERE id = $1", feld.statement
        )
    elif hidden == "draft":
        await feld.seed.run(
            "UPDATE request_items SET client_visible = false, status = 'draft' WHERE id = $1",
            feld.statement,
        )
    else:
        await _delegate(feld, feld.statement)
    file_id = await feld.dropped(STATEMENT, f"Statement_{LAST4}_2025-12.pdf")
    assert await feld.sort(file_id) == "waiting"
    assert await feld.rule_links() == 0


async def test_inv4_a_contributor_never_links_to_a_request_not_assigned_to_them(
    feld: Feld,
) -> None:
    jonah = await feld.seed.client_contact(feld.site, "client_contributor")
    other = await feld.seed.item(feld.site, "Jonah's 1099 composite", assignee=jonah)
    await feld.seed.run("UPDATE request_items SET client_visible = true WHERE id = $1", other)
    response = await feld.drop(STATEMENT, f"Statement_{LAST4}_2025-12.pdf", who=jonah)
    assert response.status_code == 202, response.text
    file_id = uuid.UUID(cast(str, response.json()["file_id"]))
    assert await feld.sort(file_id) == "waiting"
    assert await feld.links(feld.statement) == []


@pytest.mark.parametrize("binder", ["closed", "draft", "forged", "other_client"])
async def test_inv4_a_closed_draft_forged_or_foreign_binder_answers_404(
    feld: Feld, binder: str
) -> None:
    target = feld.binder
    if binder == "closed":
        await feld.seed.run("UPDATE request_lists SET status = 'closed' WHERE id = $1", target)
    elif binder == "draft":
        await feld.seed.run(
            "UPDATE request_lists SET status = 'draft', published_at = NULL WHERE id = $1",
            target,
        )
    elif binder == "forged":
        target = uuid.uuid4()
    else:
        elsewhere = await feld.seed.site(feld.tenant, feld.manager.user_id, "Calloway")
        target = cast(
            uuid.UUID,
            await feld.seed.value(
                "SELECT request_list_id FROM request_items WHERE id = $1", elsewhere.item_id
            ),
        )
        await feld.seed.run(
            "UPDATE request_lists SET status = 'published', published_at = now() WHERE id = $1",
            target,
        )
    response = await feld.drop(STATEMENT, "Statement.pdf", binder=target)
    assert response.status_code == 404, response.text
    count = await feld.seed.value(
        "SELECT count(*) FROM inbox_files WHERE tenant_id = $1", feld.tenant
    )
    assert count == 0


# ================================================================================================
# INV-1: the agent never confirms; the void only undoes an unaccepted rule link
# ================================================================================================


def test_inv1_the_agent_is_denied_fulfilment_confirm_and_only_proposes_by_task_scope() -> None:
    assert RULES["fulfilment.confirm"].decisions.get("agent") == "deny"
    assert RULES["fulfilment.propose"].decisions.get("agent") == "task_scope"
    for role in ("client_admin", "client_contributor", "third_party"):
        assert RULES["fulfilment.confirm"].decisions.get(role) in (None, "deny")


async def _void(feld: Feld, fulfilment: object, who: Person | None = None) -> httpx.Response:
    return await feld.net.http.post(
        f"/v1/engagements/{feld.site.engagement_id}/fulfilments/{fulfilment}/void",
        json={"reason": "wrong_request"},
        headers={**feld.net.headers(who or feld.manager), "Idempotency-Key": uuid.uuid4().hex},
    )


async def test_story22_a_person_voids_an_unaccepted_rule_link_and_the_file_waits(
    feld: Feld,
) -> None:
    file_id = await feld.dropped(STATEMENT, f"Statement_{LAST4}_2025-12.pdf")
    assert await feld.sort(file_id) == "rule_linked"
    [link] = await feld.links(feld.statement)
    voided = await _void(feld, link["id"])
    assert voided.status_code == 200, voided.text
    assert voided.json()["request_status"] == "requested"  # nothing else fulfils it
    [after] = await feld.links(feld.statement)
    assert after["voided_at"] is not None
    assert (await feld.inbox(file_id))["status"] == "waiting"
    audit = await feld.seed.rows(
        "SELECT actor_kind FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'fulfilment.voided'",
        feld.tenant,
    )
    assert [a["actor_kind"] for a in audit] == ["human"]
    again = await _void(feld, link["id"])
    assert (again.status_code, again.json()["detail"]) == (409, "not_voidable")


async def test_story22_an_accepted_rule_link_is_not_voidable(feld: Feld) -> None:
    file_id = await feld.dropped(STATEMENT, f"Statement_{LAST4}_2025-12.pdf")
    assert await feld.sort(file_id) == "rule_linked"
    [link] = await feld.links(feld.statement)
    accepted = await feld.net.call(
        "POST",
        f"/v1/engagements/{feld.site.engagement_id}/evidence-versions/"
        f"{link['evidence_version_id']}/decision/accept",
        feld.manager,
        body={},
    )
    assert accepted.status_code == 201, accepted.text
    refused = await _void(feld, link["id"])
    assert (refused.status_code, refused.json()["detail"]) == (409, "not_voidable")


async def test_story22_a_human_link_is_not_voidable_and_the_client_cannot_void(
    feld: Feld,
) -> None:
    human = await feld.seed.value(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id) "
        "VALUES ($1, $2, $3, $4, 'human', $5) RETURNING id",
        feld.tenant,
        feld.site.engagement_id,
        feld.other,
        feld.site.version_id,
        str(feld.manager.user_id),
    )
    refused = await _void(feld, human)
    assert (refused.status_code, refused.json()["detail"]) == (409, "not_voidable")
    file_id = await feld.dropped(STATEMENT, f"Statement_{LAST4}_2025-12.pdf")
    assert await feld.sort(file_id) == "rule_linked"
    [link] = await feld.links(feld.statement)
    by_client = await _void(feld, link["id"], who=feld.claire)
    assert by_client.status_code in (403, 404)
    assert (await feld.links(feld.statement))[0]["voided_at"] is None


# ================================================================================================
# DEC-58 c and g: 50 MB, HEIC, and duplicates flagged for a person
# ================================================================================================


def _pdf_of(size: int) -> bytes:
    head = b"%PDF-1.4\n"
    tail = b"\n%%EOF\n"
    return head + b"%" + b"0" * (size - len(head) - len(tail) - 1) + tail


async def test_dec58c_48_mb_is_accepted_and_51_mb_is_413_file_too_large(feld: Feld) -> None:
    accepted = await feld.drop(_pdf_of(48 * MB), "Large_scan.pdf")
    assert accepted.status_code == 202, accepted.text[:200]
    refused = await feld.drop(_pdf_of(51 * MB), "Too_large_scan.pdf")
    assert refused.status_code == 413
    assert refused.json()["detail"] == "file_too_large"


def _heic() -> bytes:
    """An ISO-BMFF file whose `ftyp` box names the HEIC brand, as an iPhone writes it."""
    ftyp = b"ftypheic" + b"\x00\x00\x00\x00" + b"mif1heic"
    box = (len(ftyp) + 4).to_bytes(4, "big") + ftyp
    meta = b"meta" + b"\x00" * 64
    return box + (len(meta) + 4).to_bytes(4, "big") + meta


async def test_dec58c_an_iphone_heic_photo_is_accepted_and_a_zip_is_415(feld: Feld) -> None:
    heic = await feld.drop(_heic(), "IMG_0914.HEIC")
    assert heic.status_code == 202, heic.text
    zipped = await feld.drop(b"PK\x03\x04" + b"\x00" * 64, "documents.zip")
    assert zipped.status_code == 415
    assert zipped.json()["detail"] == "type_not_allowed"


async def test_dec58g_a_duplicate_is_accepted_flagged_and_waits_for_a_person(feld: Feld) -> None:
    first = await feld.dropped(STATEMENT, f"Statement_{LAST4}_2025-12.pdf")
    assert await feld.sort(first) == "rule_linked"
    [link] = await feld.links(feld.statement)
    second_batch = uuid.uuid4()
    again = await feld.drop(STATEMENT, f"Statement_{LAST4}_copy.pdf", batch=second_batch)
    assert again.status_code == 202, again.text  # accepted, never refused
    second = uuid.UUID(cast(str, again.json()["file_id"]))
    assert (await feld.inbox(second))["duplicate_of_version_id"] == link["evidence_version_id"]
    assert await feld.sort(second) == "waiting"  # a person decides
    assert await feld.rule_links() == 1
    poll = await feld.net.call("GET", f"/v1/portal/drops/{second_batch}", feld.claire)
    assert poll.status_code == 200, poll.text
    [row] = cast(list[Json], poll.json()["files"])
    assert row["outcome"] == "waiting"  # the client is never told what the firm holds
    assert "duplicate" not in json.dumps(poll.json())


# ================================================================================================
# ADR-090: the history recorded before the portal_drop_sort step still replays
# ================================================================================================


def _history(path: Path) -> WorkflowHistory:
    return WorkflowHistory.from_json("r01t15-upload-processing", path.read_text(encoding="utf-8"))


PRE_CHANGE = sorted(
    p
    for p in HISTORIES.glob("upload-processing-v*.json")
    if "portal_drop_sort" not in p.read_text(encoding="utf-8")
)


def test_adr090_pre_change_histories_exist_and_never_sort_a_drop() -> None:
    assert len(PRE_CHANGE) >= 1
    assert any(p.stem.startswith("upload-processing-v5") for p in PRE_CHANGE)


@pytest.mark.parametrize("path", PRE_CHANGE, ids=[p.stem for p in PRE_CHANGE])
async def test_adr090_a_pre_change_upload_processing_history_replays(path: Path) -> None:
    await Replayer(workflows=[UploadProcessing]).replay_workflow(_history(path))


@workflow.defn(name="upload_processing")
class _SortsEveryFile:
    """A change made without `workflow.patched`: the sort scheduled first, for every run."""

    @workflow.run
    async def run(self, given: UploadInput) -> str:
        return await workflow.execute_activity(
            "upload.portal_drop_sort",
            replace(given),
            result_type=str,
            start_to_close_timeout=timedelta(minutes=3),
        )


async def test_adr090_an_unpatched_sort_step_breaks_the_pre_change_replay() -> None:
    newest = PRE_CHANGE[-1]
    with pytest.raises(workflow.NondeterminismError):
        replayer = Replayer(
            workflows=[_SortsEveryFile], workflow_runner=UnsandboxedWorkflowRunner()
        )
        await replayer.replay_workflow(_history(newest))
