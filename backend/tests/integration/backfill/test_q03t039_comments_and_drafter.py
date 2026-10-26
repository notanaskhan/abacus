# ac-test-author: ayushkbhatia
"""SPEC-032 AC-1 to AC-9 (TASK-062) and SPEC-035 AC-2, AC-3 and the drafter's declaration
(TASK-072): comments on requests and versions, and the guidance drafter's code checks.

Q-03-T039's line: "A shared comment passes the scope check and a redaction is a new row, never
an edit." Boundary: `create_app()` over HTTP with fake-identity tokens (`net`), seeding as the
superuser; the drafter's declaration is its spec file (`agents/specs/*.yaml`, the declared
contract ADR-047 names). Later decisions followed: TASK-062's decision table (`out_of_scope`
carries the code only; firm roles without an engagement role see internal notes; redaction is
under the item's comments route); errors from `docs/architecture/error-codes.yaml`.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest
import yaml
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.db import TenantContext, tenant_session

from .support import Json, Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio
SPECS = Path(__file__).resolve().parents[3] / "src" / "abacus" / "modules" / "agents" / "specs"


@dataclass(frozen=True)
class Thread:
    net: Net
    tenant_id: uuid.UUID
    admin: Person  # firm administrator
    priya: Person  # senior
    marcus: Person  # manager
    rachel: Person  # the client's admin
    carl: Person  # a client contributor, not assigned the item
    site: Site
    other: Site  # another client of the same firm

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    def path(self, version: bool = False) -> str:
        base = f"/v1/engagements/{self.site.engagement_id}/request-items/{self.site.item_id}"
        return (
            f"{base}/versions/{self.site.version_id}/comments" if version else f"{base}/comments"
        )

    async def post(self, who: Person, body: Json, *, version: bool = False) -> tuple[int, Json]:
        response = await self.net.call("POST", self.path(version), who, body=body)
        return response.status_code, cast(Json, response.json())

    async def read(self, who: Person, *, version: bool = False) -> tuple[int, list[Json]]:
        response = await self.net.call("GET", self.path(version), who)
        body = response.json()
        return response.status_code, cast(list[Json], body if isinstance(body, list) else [])


@pytest.fixture
async def thread(net: Net) -> Thread:
    seed = net.seed
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    priya = await seed.person(tenant)
    marcus = await seed.person(tenant)
    site = await seed.site(tenant, admin.user_id, "Harborline")
    other = await seed.site(tenant, admin.user_id, "Ridgeline")
    await seed.member(site, priya, "senior")
    await seed.member(site, marcus, "manager")
    # The site's version fulfils its item, so the version has a thread (SPEC-032 AC-1).
    await seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id) "
        "VALUES ($1, $2, $3, $4, 'rule', 'q03t039')",
        tenant,
        site.engagement_id,
        site.item_id,
        site.version_id,
    )
    rachel = await seed.client_contact(site, "client_admin")
    carl = await seed.client_contact(site, "client_contributor")
    return Thread(net, tenant, admin, priya, marcus, rachel, carl, site, other)


def _ids(comments: list[Json]) -> list[str]:
    return [cast(str, c["id"]) for c in comments]


# --- AC-1: one thread per item, one per version --------------------------------------------------


async def test_ac1_each_item_and_version_has_its_own_thread(thread: Thread) -> None:
    status, on_item = await thread.post(thread.priya, {"text": "Tie this to the TB."})
    assert status == 201, on_item
    status, on_version = await thread.post(
        thread.marcus, {"text": "Check the December page."}, version=True
    )
    assert status == 201, on_version
    assert on_item["evidence_version_id"] is None
    assert on_version["evidence_version_id"] == str(thread.site.version_id)
    _s, item_thread = await thread.read(thread.priya)
    _s, version_thread = await thread.read(thread.priya, version=True)
    assert _ids(item_thread) == [on_item["id"]]
    assert _ids(version_thread) == [on_version["id"]]


# --- AC-2 and AC-3: visibility -------------------------------------------------------------------


async def test_ac2_a_firm_note_is_internal_by_default_and_a_client_comment_always_shared(
    thread: Thread,
) -> None:
    status, note = await thread.post(thread.priya, {"text": "Ask about the CSV export."})
    assert (status, note["visibility"]) == (201, "internal")
    status, asked = await thread.post(
        thread.rachel, {"text": "Is a CSV export fine?", "share": False}
    )
    assert (status, asked["visibility"], asked["author_side"]) == (201, "shared", "client")


async def test_ac3_a_client_never_receives_internal_notes_or_items_they_cannot_see(
    thread: Thread,
) -> None:
    _s, note = await thread.post(thread.marcus, {"text": "Tie the payroll CSV first."})
    status, shared = await thread.post(
        thread.priya, {"text": "Yes, a CSV export is fine.", "share": True}
    )
    assert status == 201, shared
    status, seen = await thread.read(thread.rachel)
    assert status == 200
    assert _ids(seen) == [shared["id"]]
    assert str(note["id"]) not in json.dumps(seen)
    # A contributor not assigned the item reads nothing of it.
    status, _ = await thread.read(thread.carl)
    assert status in (403, 404)
    # Hidden from clients (SPEC-020): nobody on the client side reads its thread.
    await thread.seed.run(
        "UPDATE request_items SET client_visible = false WHERE id = $1", thread.site.item_id
    )
    status, _ = await thread.read(thread.rachel)
    assert status in (403, 404)
    status, firm_side = await thread.read(thread.marcus)
    assert status == 200 and {c["visibility"] for c in firm_side} == {"internal", "shared"}


# --- AC-4: append-only, corrections --------------------------------------------------------------


async def test_ac4_a_comment_is_never_edited_and_its_author_posts_a_correction(
    thread: Thread,
) -> None:
    _s, first = await thread.post(thread.priya, {"text": "The bank is Harbor First."})
    status, fix = await thread.post(
        thread.priya, {"text": "The bank is Harborline Trust.", "corrects": first["id"]}
    )
    assert status == 201, fix
    assert fix["corrects"] == first["id"]
    _s, comments = await thread.read(thread.priya)
    by_id = {c["id"]: c for c in comments}
    assert by_id[first["id"]]["corrected_by"] == [fix["id"]]
    assert by_id[first["id"]]["text"] == "The bank is Harbor First."  # the original stays
    status, refused = await thread.post(
        thread.marcus, {"text": "Someone else's fix.", "corrects": first["id"]}
    )
    assert (status, refused["detail"]) == (422, "correction_not_allowed")

    me = TenantContext(thread.tenant_id, "human", str(thread.priya.user_id))
    for statement in (
        "UPDATE comments SET visibility = 'shared'",
        "DELETE FROM comments",
        "DELETE FROM comment_redactions",
    ):
        with pytest.raises(DBAPIError, match=r"permission denied"):
            async with tenant_session(me) as session:
                await session.execute(text(statement))


# --- AC-5: mentions ------------------------------------------------------------------------------


async def test_ac5_only_readers_can_be_mentioned_and_each_is_notified_once(
    thread: Thread,
) -> None:
    status, refused = await thread.post(
        thread.priya, {"text": "@Rachel see this", "mentions": [str(thread.rachel.user_id)]}
    )
    assert (status, refused["detail"]) == (422, "mention_not_allowed")  # an internal note
    status, posted = await thread.post(
        thread.priya,
        {
            "text": "Yes, a CSV export is fine.",
            "share": True,
            "mentions": [str(thread.rachel.user_id), str(thread.marcus.user_id)],
        },
    )
    assert status == 201, posted
    assert sorted(cast(list[str], posted["mentions"])) == sorted(
        [str(thread.rachel.user_id), str(thread.marcus.user_id)]
    )
    events = await thread.seed.rows(
        "SELECT payload::text AS payload FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'comment.mentioned'",
        thread.tenant_id,
    )
    assert len(events) == 1
    payload = str(events[0]["payload"])
    for who in (thread.rachel, thread.marcus):
        assert payload.count(str(who.user_id)) == 1
    assert "CSV" not in payload  # identifiers only


# --- AC-6: redaction is a new row ----------------------------------------------------------------


async def test_ac6_only_a_firm_admin_redacts_and_the_redaction_is_a_new_row(
    thread: Thread,
) -> None:
    _s, posted = await thread.post(
        thread.rachel, {"text": "Our portal password is hunter2, log in to check."}
    )
    redact = f"{thread.path()}/{posted['id']}/redact"
    before = await thread.seed.value(
        "SELECT body_sealed FROM comments WHERE id = $1", uuid.UUID(cast(str, posted["id"]))
    )
    for who in (thread.marcus, thread.priya, thread.rachel):
        response = await thread.net.call("POST", redact, who, body={"reason": "Posted in error"})
        assert response.status_code in (403, 404), who
    response = await thread.net.call(
        "POST", redact, thread.admin, body={"reason": "A password, posted in error"}
    )
    assert response.status_code == 201, response.text
    again = await thread.net.call("POST", redact, thread.admin, body={"reason": "Again"})
    assert (again.status_code, again.json()["detail"]) == (409, "already_redacted")

    for reader in (thread.priya, thread.rachel):
        _s, comments = await thread.read(reader)
        stub = next(c for c in comments if c["id"] == posted["id"])
        assert stub["text"] is None
        redaction = cast(Json, stub["redaction"])
        assert "A password, posted in error" in json.dumps(redaction)
        assert "hunter2" not in json.dumps(comments)
    # Nothing was edited: the comment row is as it was, and the redaction is its own row.
    after = await thread.seed.value(
        "SELECT body_sealed FROM comments WHERE id = $1", uuid.UUID(cast(str, posted["id"]))
    )
    assert after == before
    rows = await thread.seed.value(
        "SELECT count(*) FROM comment_redactions WHERE comment_id = $1",
        uuid.UUID(cast(str, posted["id"])),
    )
    assert rows == 1
    assert "comment.redacted" in await thread.seed.actions(thread.tenant_id)


# --- AC-7: the scope check on sharing ------------------------------------------------------------


async def test_ac7_a_shared_comment_passes_the_scope_check_or_stays_unshared(
    thread: Thread,
) -> None:
    status, clean = await thread.post(
        thread.priya, {"text": "A CSV export of the payroll account is fine.", "share": True}
    )
    assert (status, clean["visibility"]) == (201, "shared")
    leak = f"Compare with Client {thread.other.marker}'s statements."
    count = "SELECT count(*) FROM comments WHERE tenant_id = $1"
    stored = await thread.seed.value(count, thread.tenant_id)
    status, refused = await thread.post(thread.priya, {"text": leak, "share": True})
    assert (status, refused["detail"]) == (409, "out_of_scope")
    assert await thread.seed.value(count, thread.tenant_id) == stored  # nothing stored
    status, kept = await thread.post(thread.priya, {"text": leak})
    assert (status, kept["visibility"]) == (201, "internal")


# --- AC-8: counts and unread ---------------------------------------------------------------------


async def _item_row(thread: Thread, who: Person) -> Json:
    response = await thread.net.call(
        "GET", f"/v1/engagements/{thread.site.engagement_id}/request-items", who
    )
    assert response.status_code == 200, response.text
    body = response.json()
    rows = cast(list[Json], body["items"] if isinstance(body, dict) else body)
    return next(r for r in rows if r["id"] == str(thread.site.item_id))


async def test_ac8_each_item_counts_its_comments_and_marks_unread_per_reader(
    thread: Thread,
) -> None:
    await thread.post(thread.rachel, {"text": "Is a CSV export fine?"})
    await thread.post(thread.marcus, {"text": "Check the version."}, version=True)
    row = await _item_row(thread, thread.priya)
    assert (row["comment_count"], row["unread_comments"]) == (2, True)
    for version in (False, True):
        body: Json = {"evidence_version_id": str(thread.site.version_id) if version else None}
        response = await thread.net.call("POST", f"{thread.path()}/read", thread.priya, body=body)
        assert response.status_code == 200, response.text
    row = await _item_row(thread, thread.priya)
    assert (row["comment_count"], row["unread_comments"]) == (2, False)
    client_row = await _item_row(thread, thread.rachel)
    assert client_row["comment_count"] == 1  # the internal version note is not the client's


# --- AC-9: sealed text, identifier-only audit ----------------------------------------------------


async def test_ac9_the_text_is_sealed_and_the_audit_carries_identifiers_only(
    thread: Thread,
) -> None:
    secret = f"Payroll account ending 9{uuid.uuid4().int % 1000:03d}"
    status, posted = await thread.post(thread.priya, {"text": secret})
    assert status == 201
    sealed = cast(
        bytes,
        await thread.seed.value(
            "SELECT body_sealed FROM comments WHERE id = $1", uuid.UUID(cast(str, posted["id"]))
        ),
    )
    assert secret.encode() not in sealed
    audits = await thread.seed.rows(
        "SELECT action, row_to_json(a)::text AS row FROM audit_events a WHERE tenant_id = $1",
        thread.tenant_id,
    )
    assert "comment.posted" in {r["action"] for r in audits}
    assert all(secret not in str(r["row"]) for r in audits)


# --- TASK-072: the drafter's declaration and its code checks -------------------------------------


def test_tsk072_the_drafter_is_declared_small_proposing_and_scoped() -> None:
    spec = cast(Json, yaml.safe_load((SPECS / "requests.guidance_drafter.yaml").read_text()))
    assert spec["id"] == "requests.guidance_drafter"
    assert (spec["shape"], spec["tier"], spec["autonomy"]) == ("single_call", "small", "propose")
    assert {"request_item.read", "guidance_draft.run"} <= set(cast(list[str], spec["task_scope"]))
    assert spec["evaluation_suite"] == "evals/guidance_drafting"
    assert spec["essential"] is False


async def _drafter_run(thread: Thread) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await thread.seed.value(
            "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
            "initiator_user_id, task_scope, status, finished_at) VALUES ($1, "
            "'requests.guidance_drafter', 2, $2, $3, "
            "ARRAY['request_item.read', 'guidance_draft.run'], 'completed', now()) RETURNING id",
            thread.tenant_id,
            thread.site.engagement_id,
            thread.priya.user_id,
        ),
    )


async def _draft(thread: Thread, *, passed: bool, why: str) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await thread.seed.value(
            "INSERT INTO guidance_drafts (tenant_id, engagement_id, request_item_id, "
            "agent_run_id, prompt_ref, why, good_looks_like, passed_checks, check_reasons) "
            "VALUES ($1, $2, $3, $4, 'requests.guidance_draft@v1', $5, "
            "'A statement for every account at the year end.', $6, $7) RETURNING id",
            thread.tenant_id,
            thread.site.engagement_id,
            thread.site.item_id,
            await _drafter_run(thread),
            why,
            passed,
            [] if passed else ["url"],
        ),
    )


async def test_ac3_a_draft_that_fails_the_checks_is_recorded_but_never_shown(
    thread: Thread,
) -> None:
    shown = await _draft(thread, passed=True, why="We confirm the cash balance with the bank.")
    hidden = await _draft(thread, passed=False, why="See https://example.test for details.")
    response = await thread.net.call(
        "GET", f"/v1/engagements/{thread.site.engagement_id}/guidance-drafts", thread.priya
    )
    assert response.status_code == 200, response.text
    listed = {d["id"] for d in cast(list[Json], response.json())}
    assert str(shown) in listed and str(hidden) not in listed
    assert "example.test" not in response.text
    assert (
        await thread.seed.value("SELECT count(*) FROM guidance_drafts WHERE id = $1", hidden) == 1
    )  # recorded


@pytest.mark.parametrize(
    "edited",
    [
        "Read https://example.test before you upload.",  # a URL
        "Email the controller at controller@example.test.",  # an email address
        "Call us on 555-201-4477 with questions.",  # a phone number
        "We need the $12,500.00 transfer on the statement.",  # an amount
        "As an AI, I suggest uploading the statements.",  # first-person model talk
    ],
)
async def test_ac3_an_edited_draft_faces_the_same_code_checks(thread: Thread, edited: str) -> None:
    draft = await _draft(thread, passed=True, why="We confirm the cash balance with the bank.")
    response = await thread.net.call(
        "POST",
        f"/v1/engagements/{thread.site.engagement_id}/guidance-drafts/approve",
        thread.priya,
        body={"approvals": [{"draft_id": str(draft), "why": edited}], "confirmed_read": True},
    )
    assert (response.status_code, response.json()["detail"]) == (422, "edited_draft_refused")
    source = await thread.seed.value(
        "SELECT guidance_source FROM request_items WHERE id = $1", thread.site.item_id
    )
    assert source != "drafted"  # nothing applied


async def test_ac2_a_real_firm_gets_no_draft_and_is_told_drafting_is_unavailable(
    thread: Thread,
) -> None:
    runs = "SELECT count(*) FROM agent_runs WHERE tenant_id = $1"
    before = await thread.seed.value(runs, thread.tenant_id)
    response = await thread.net.call(
        "POST",
        f"/v1/engagements/{thread.site.engagement_id}/request-items/draft-guidance",
        thread.priya,
        body={"item_ids": [str(thread.site.item_id)]},
    )
    assert (response.status_code, response.json()["detail"]) == (409, "ai_drafting_unavailable")
    assert await thread.seed.value(runs, thread.tenant_id) == before
    assert (
        await thread.seed.value(
            "SELECT count(*) FROM guidance_drafts WHERE tenant_id = $1", thread.tenant_id
        )
        == 0
    )
