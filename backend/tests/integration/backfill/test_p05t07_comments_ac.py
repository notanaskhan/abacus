"""P-05-T07 (ac-test-author; SPEC-650 §3.1–3.5, §3.11; ADR-236): comments v2, from the SPEC and the
P-05-T03 501 stubs, before the service (P-05-T05). Against the stubs every test fails (501).

Until P-05-T09 registers the `workpaper` provider, the one registered anchor kind is P-05-T06's
`todo`, so AC-1's thread is opened on a to-do; the workpaper locator half is P-05-T09's suite.
AC-8 (fan-out re-check) and AC-15 (never blocks a sign-off) are P-05-T08's consumer suites.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.identity.api import RULES

from .p05_support import Collab, collab
from .support import Net

pytestmark = pytest.mark.asyncio

NOTE = "@Hannah Leclerc this cutoff item drives AJE-1 — show it as factual on the SUM."
V2_ACTIONS = ("comment.resolve", "todo.read", "todo.create", "todo.update", "todo.complete")


@pytest.fixture
async def w(net: Net) -> Collab:
    return await collab(net)


async def _anchor(w: Collab) -> str:
    return str((await w.todo())["id"])


async def test_ac1_a_thread_is_sealed_and_audited_in_the_authors_name(w: Collab) -> None:
    anchor = await _anchor(w)
    response = await w.thread_on(anchor, body=NOTE, mention_user_ids=[str(w.hannah.user_id)])
    assert response.status_code == 201, response.text
    posted = response.json()
    thread = posted["thread"]
    assert thread["anchor"]["anchor_kind"] == "todo"
    assert thread["anchor"]["anchor_id"] == anchor
    assert thread["status"] == "open"
    assert thread["visibility"] == "internal"
    assert thread["comment_count"] == 1
    assert thread["comments"][0]["body"] == NOTE
    assert thread["comments"][0]["author"]["name"] == "Margaret Okonkwo"
    row = (
        await w.net.seed.rows(
            "SELECT body_sealed, body_fingerprint FROM thread_comments WHERE id = $1",
            uuid.UUID(posted["comment_id"]),
        )
    )[0]
    assert NOTE.encode() not in bytes(row["body_sealed"])  # sealed, never stored in the clear
    assert row["body_fingerprint"] == hashlib.sha256(NOTE.encode()).hexdigest()
    actions = await w.audit_actions(thread["id"])
    assert ("comment_thread.opened", str(w.margaret.user_id)) in actions
    assert ("comment.posted", str(w.margaret.user_id)) in actions
    logged = await w.net.seed.rows(
        "SELECT after_ref::text AS ref FROM audit_events WHERE tenant_id = $1", w.tenant_id
    )
    assert not any("AJE-1" in (r["ref"] or "") for r in logged)  # bodies never in refs


@pytest.mark.parametrize("kind", ["request_item", "evidence_version", "sheet_row", "workpaperx"])
async def test_ac2_an_unregistered_anchor_kind_is_refused_and_writes_nothing(
    w: Collab, kind: str
) -> None:
    response = await w.call(
        "POST",
        "/v1/comment-threads",
        w.margaret,
        {"anchor": {"anchor_kind": kind, "anchor_id": str(uuid.uuid4())}, "body": "Hello."},
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "anchor_kind_not_registered"
    count = await w.net.seed.value(
        "SELECT count(*) FROM comment_threads WHERE tenant_id = $1", w.tenant_id
    )
    assert count == 0


async def test_ac3_an_anchor_with_no_threads_lists_none(w: Collab) -> None:
    anchor = await _anchor(w)
    response = await w.call(
        "GET", f"/v1/comment-threads?anchor_kind=todo&anchor_id={anchor}", w.margaret
    )
    assert response.status_code == 200, response.text
    page = response.json()
    assert page["items"] == []
    assert page["counts"] == {"open": 0, "resolved": 0}


@pytest.mark.parametrize(
    ("body", "code"), [("   \n\t ", "empty_comment"), ("x" * 4001, "comment_too_long")]
)
async def test_ac4_empty_and_over_long_comments_are_refused(
    w: Collab, body: str, code: str
) -> None:
    response = await w.thread_on(await _anchor(w), body=body)
    assert response.status_code == 422, response.text
    assert response.json()["code"] == code


async def test_ac4_four_thousand_characters_are_accepted(w: Collab) -> None:
    response = await w.thread_on(await _anchor(w), body="y" * 4000)
    assert response.status_code == 201, response.text


async def test_ac5_mention_candidates_are_the_engagement_team_and_never_the_agent(
    w: Collab,
) -> None:
    path = f"/v1/engagements/{w.site.engagement_id}/mention-candidates"
    found = await w.call("GET", f"{path}?q=Ha", w.margaret)
    assert found.status_code == 200, found.text
    names = [m["name"] for m in found.json()["members"]]
    assert names == ["Hannah Leclerc"]
    everyone = (await w.call("GET", path, w.margaret)).json()
    assert everyone["team"]["member_count"] == 5
    members = {m["name"]: m for m in everyone["members"]}
    assert set(members) == {
        "Margaret Okonkwo", "Hannah Leclerc", "Marcus Delaney", "Alicia Chen", "Tom Whitaker",
    }  # fmt: skip
    assert members["Margaret Okonkwo"]["is_self"] is True
    assert not any("Agent" in n for n in members)


async def test_ac6_a_non_member_is_greyed_a_walled_person_is_absent(w: Collab) -> None:
    path = f"/v1/engagements/{w.site.engagement_id}/mention-candidates"
    simone = (await w.call("GET", f"{path}?q=Si", w.margaret)).json()
    assert simone["members"] == []
    greyed = simone["not_on_engagement"]
    assert [p["name"] for p in greyed] == ["Simone Baptiste"]
    assert greyed[0]["selectable"] is False
    assert greyed[0]["reason"] == "not_on_engagement"
    victor = (await w.call("GET", f"{path}?q=Vi", w.margaret)).json()
    assert victor["members"] == [] and victor["not_on_engagement"] == []  # DEC-43: no trace


@pytest.mark.parametrize("who", ["simone", "victor"])
async def test_ac6_a_crafted_mention_of_a_non_member_posts_nothing(w: Collab, who: str) -> None:
    anchor = await _anchor(w)
    target = getattr(w, who)
    response = await w.thread_on(anchor, mention_user_ids=[str(target.user_id)])
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "mention_not_allowed"
    assert await w.net.seed.value(
        "SELECT count(*) FROM thread_comments WHERE tenant_id = $1", w.tenant_id
    ) == 0


async def test_ac7_one_mention_event_per_person_and_no_body_anywhere(w: Collab) -> None:
    anchor = await _anchor(w)
    response = await w.thread_on(anchor, body=NOTE, mention_user_ids=[str(w.hannah.user_id)])
    assert response.status_code == 201, response.text
    posted = response.json()
    assert [p["name"] for p in posted["notified"]] == ["Hannah Leclerc"]
    events = await w.net.seed.rows(
        "SELECT payload::text AS payload FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'mention.created'",
        w.tenant_id,
    )
    assert len(events) == 1
    assert str(w.hannah.user_id) in events[0]["payload"]
    assert "AJE-1" not in events[0]["payload"]


async def test_ac7_a_team_mention_expands_to_the_members_without_the_author(w: Collab) -> None:
    anchor = await _anchor(w)
    response = await w.thread_on(anchor, body="Team, please read.", mention_team=True)
    assert response.status_code == 201, response.text
    mentioned = await w.net.seed.rows(
        "SELECT user_id, via_team FROM thread_comment_mentions WHERE tenant_id = $1", w.tenant_id
    )
    assert {r["user_id"] for r in mentioned} == {
        w.hannah.user_id, w.marcus.user_id, w.alicia.user_id, w.tom.user_id,
    }  # fmt: skip
    assert all(r["via_team"] for r in mentioned)


async def _thread(w: Collab) -> dict[str, object]:
    response = await w.thread_on(await _anchor(w), body=NOTE)
    assert response.status_code == 201, response.text
    return cast(dict[str, object], response.json()["thread"])


async def test_ac9_resolve_is_an_event_in_the_resolvers_name(w: Collab) -> None:
    thread = await _thread(w)
    response = await w.call("POST", f"/v1/comment-threads/{thread['id']}/resolve", w.hannah)
    assert response.status_code == 200, response.text
    resolved = response.json()
    assert resolved["status"] == "resolved"
    assert resolved["events"][-1]["kind"] == "resolved"
    assert resolved["events"][-1]["actor"]["name"] == "Hannah Leclerc"
    again = await w.call("POST", f"/v1/comment-threads/{thread['id']}/resolve", w.hannah)
    assert again.status_code == 409
    assert again.json()["code"] == "thread_already_resolved"
    kinds = await w.net.seed.rows(
        "SELECT kind, actor_kind FROM comment_thread_events WHERE thread_id = $1 ORDER BY "
        "created_at",
        uuid.UUID(str(thread["id"])),
    )
    assert [(r["kind"], r["actor_kind"]) for r in kinds] == [
        ("opened", "human"), ("resolved", "human"),
    ]  # fmt: skip


async def test_ac10_reopen_writes_an_event_and_moves_the_projection_back(w: Collab) -> None:
    thread = await _thread(w)
    await w.call("POST", f"/v1/comment-threads/{thread['id']}/resolve", w.hannah)
    response = await w.call("POST", f"/v1/comment-threads/{thread['id']}/reopen", w.marcus)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "open"
    assert response.json()["events"][-1]["kind"] == "reopened"
    listed = await w.call(
        "GET",
        f"/v1/comment-threads?anchor_kind=todo&anchor_id={thread['anchor']['anchor_id']}",  # type: ignore[index] -- JSON
        w.margaret,
    )
    assert listed.json()["counts"] == {"open": 1, "resolved": 0}


async def test_ac11_the_author_corrects_and_nobody_else_may(w: Collab) -> None:
    thread = await _thread(w)
    first = cast(list[dict[str, object]], thread["comments"])[0]["id"]
    path = f"/v1/comment-threads/{thread['id']}/comments"
    fixed = await w.call(
        "POST", path, w.margaret, {"body": "Show it as factual.", "corrects_comment_id": first}
    )
    assert fixed.status_code == 201, fixed.text
    comments = fixed.json()["thread"]["comments"]
    assert comments[0]["corrected_by_comment_id"] == comments[1]["id"]
    assert comments[1]["corrects_comment_id"] == first
    other = await w.call(
        "POST", path, w.hannah, {"body": "My version.", "corrects_comment_id": first}
    )
    assert other.status_code == 422
    assert other.json()["code"] == "correction_not_allowed"


async def test_ac11_a_firm_admin_redacts_with_fresh_mfa_and_the_body_never_returns(
    w: Collab,
) -> None:
    thread = await _thread(w)
    comment = cast(list[dict[str, object]], thread["comments"])[0]["id"]
    path = f"/v1/thread-comments/{comment}/redact"
    denied = await w.call("POST", path, w.hannah, {"reason": "Posted in error."})
    assert denied.status_code == 403
    stale = await w.call("POST", path, w.grace, {"reason": "Posted in error."}, mfa=False)
    assert stale.status_code in (401, 403)
    done = await w.call("POST", path, w.grace, {"reason": "Posted in error."})
    assert done.status_code == 200, done.text
    assert done.json()["body"] is None
    assert done.json()["redaction"]["redacted_by"]["name"] == "Grace Holloway"
    assert done.json()["redaction"]["reason"] == "Posted in error."
    again = await w.call("POST", path, w.grace, {"reason": "Twice."})
    assert again.status_code == 409 and again.json()["code"] == "already_redacted"
    read = await w.call(
        "GET",
        f"/v1/comment-threads?anchor_kind=todo&anchor_id={thread['anchor']['anchor_id']}",  # type: ignore[index] -- JSON
        w.marcus,
    )
    assert NOTE not in read.text
    assert await w.net.seed.value(
        "SELECT count(*) FROM thread_comments WHERE id = $1", uuid.UUID(str(comment))
    ) == 1  # kept, sealed


async def test_ac12_a_muted_thread_adds_no_unread_dot(w: Collab) -> None:
    thread = await _thread(w)
    muted = await w.call(
        "POST", f"/v1/comment-threads/{thread['id']}/mute", w.hannah, {"muted": True}
    )
    assert muted.status_code == 200, muted.text
    assert muted.json()["muted"] is True
    await w.call(
        "POST", f"/v1/comment-threads/{thread['id']}/comments", w.margaret, {"body": "More."}
    )
    counts = await w.call(
        "POST",
        "/v1/comment-threads/counts",
        w.hannah,
        {"anchors": [thread["anchor"]]},
    )
    assert counts.status_code == 200, counts.text
    assert counts.json()["items"][0]["unread"] == 0
    assert counts.json()["items"][0]["open"] == 1


@pytest.mark.parametrize(
    "table",
    ["thread_comments", "thread_comment_mentions", "thread_comment_redactions",
     "comment_thread_events"],
)  # fmt: skip
async def test_ac13_the_app_role_cannot_update_or_delete_append_only_rows(
    w: Collab, table: str
) -> None:
    tenant = TenantContext(w.tenant_id, "human", str(w.margaret.user_id))
    for statement in (f"UPDATE {table} SET tenant_id = tenant_id", f"DELETE FROM {table}"):
        with pytest.raises(DBAPIError):
            async with tenant_session(tenant) as session:
                await session.execute(text(statement))
                await session.commit()


async def test_ac16_sharing_an_internal_anchor_is_refused(w: Collab) -> None:
    thread = await _thread(w)
    response = await w.call(
        "POST",
        f"/v1/comment-threads/{thread['id']}/share",
        w.margaret,
        {"scope_kind": "engagement", "scope_id": str(w.site.engagement_id)},
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "anchor_not_shareable"


async def test_inv4_a_client_principal_never_reaches_a_thread(w: Collab) -> None:
    thread = await _thread(w)
    anchor = thread["anchor"]["anchor_id"]  # type: ignore[index] -- JSON
    listed = await w.call(
        "GET", f"/v1/comment-threads?anchor_kind=todo&anchor_id={anchor}", w.client
    )
    assert listed.status_code == 404
    assert NOTE not in listed.text


async def test_inv3_a_walled_person_reads_nothing(w: Collab) -> None:
    thread = await _thread(w)
    anchor = thread["anchor"]["anchor_id"]  # type: ignore[index] -- JSON
    listed = await w.call(
        "GET", f"/v1/comment-threads?anchor_kind=todo&anchor_id={anchor}", w.victor
    )
    assert listed.status_code in (403, 404)
    assert NOTE not in listed.text


def test_inv1_the_agent_holds_no_collaboration_action() -> None:
    for action in (*V2_ACTIONS, "comment.create", "comment.redact", "comment.share"):
        assert RULES[action].decisions.get("agent", "deny") == "deny", action


async def test_ac39_flag_off_every_route_answers_not_found(w: Collab) -> None:
    anchor = await _anchor(w)
    await w.flag(False)
    listed = await w.call(
        "GET", f"/v1/comment-threads?anchor_kind=todo&anchor_id={anchor}", w.margaret
    )
    assert listed.status_code == 404
    opened = await w.thread_on(anchor)
    assert opened.status_code == 404
