"""P-05-T07 (ac-test-author; SPEC-650 §3.6 to 3.8, §3.11): to-dos, from the SPEC and the
P-05-T03 501 stubs, before the service (P-05-T06). Against the stubs every test fails (501).

Dates are relative to the server's business date in the firm's zone (no demo clock over HTTP);
AC-29's Sep 14 golden counts are the bucketing unit test in P-05-T06's suite.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pytest

from abacus.kernel import clock

from .p05_support import Collab, collab
from .support import Net

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def w(net: Net) -> Collab:
    return await collab(net)


async def _today() -> date:
    return await clock.today(zone=ZoneInfo("America/Chicago"))


async def test_ac17_assignee_candidates_are_the_engagement_team_only(w: Collab) -> None:
    response = await w.call(
        "GET", f"/v1/engagements/{w.site.engagement_id}/assignee-candidates", w.margaret
    )
    assert response.status_code == 200, response.text
    names = {p["name"] for p in response.json()["items"]}
    assert names == {
        "Margaret Okonkwo", "Hannah Leclerc", "Marcus Delaney", "Alicia Chen", "Tom Whitaker",
    }  # fmt: skip


async def test_ac18_a_new_to_do_is_open_assigned_audited_and_notified(w: Collab) -> None:
    due = (await _today() + timedelta(days=2)).isoformat()
    todo = await w.todo(due_on=due)
    assert todo["status"] == "open"
    assert todo["due_on"] == due
    assert todo["assignee"]["name"] == "Marcus Delaney"  # type: ignore[index] -- JSON
    assert todo["created_by"]["name"] == "Margaret Okonkwo"  # type: ignore[index] -- JSON
    assert todo["version"] == 1
    actions = [a for a, _ in await w.audit_actions(todo["id"])]
    assert "todo.created" in actions and "todo.assigned" in actions
    events = await w.net.seed.rows(
        "SELECT event_type, payload::text AS payload FROM outbox WHERE tenant_id = $1 "
        "AND event_type LIKE 'todo.%'",
        w.tenant_id,
    )
    assert {e["event_type"] for e in events} >= {"todo.created", "todo.assigned"}
    assert not any("cutoff" in e["payload"] for e in events)  # identifiers only


@pytest.mark.parametrize("who", ["simone", "victor"])
async def test_ac19_a_non_member_or_walled_assignee_is_refused(w: Collab, who: str) -> None:
    response = await w.call(
        "POST",
        "/v1/todos",
        w.margaret,
        {
            "engagement_id": str(w.site.engagement_id),
            "title": "Look at row 6",
            "assignee_user_id": str(getattr(w, who).user_id),
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "assignee_not_allowed"


async def test_ac20_a_stale_if_match_is_refused(w: Collab) -> None:
    todo = await w.todo()
    path = f"/v1/todos/{todo['id']}"
    first = await w.net.http.patch(
        path,
        json={"title": "Tie the cutoff item"},
        headers={**w.net.headers(w.margaret), "If-Match": "1"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["version"] == 2
    stale = await w.net.http.patch(
        path,
        json={"title": "Another title"},
        headers={**w.net.headers(w.hannah), "If-Match": "1"},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"] == "stale_version"


async def test_ac21_the_assignee_opens_it_and_the_unread_dot_clears(w: Collab) -> None:
    todo = await w.todo()
    mine = await w.call("GET", "/v1/todos?assignee=me", w.marcus)
    assert [t["unread"] for t in mine.json()["items"]] == [True]
    seen = await w.call("POST", f"/v1/todos/{todo['id']}/seen", w.marcus)
    assert seen.status_code == 200, seen.text
    assert seen.json()["unread"] is False
    assert "todo.complete" in seen.json()["allowed_actions"]
    assert "todo.assign" in seen.json()["allowed_actions"]


async def test_ac22_a_checklist_holds_eight_items(w: Collab) -> None:
    todo = await w.todo(checklist=[f"Step {n}" for n in range(1, 8)])
    path = f"/v1/todos/{todo['id']}/checklist-items"
    eighth = await w.call("POST", path, w.margaret, {"text": "Step 8"})
    assert eighth.status_code == 201, eighth.text
    items = eighth.json()["checklist"]
    assert [i["position"] for i in items] == list(range(1, 9))
    ninth = await w.call("POST", path, w.margaret, {"text": "Step 9"})
    assert ninth.status_code == 422
    assert ninth.json()["detail"] == "checklist_full"
    toggled = await w.call("PATCH", f"{path}/{items[0]['id']}", w.marcus, {"done": True})
    assert toggled.status_code == 200, toggled.text
    assert toggled.json()["checklist"][0]["done"] is True
    assert "todo.checklist_changed" in [a for a, _ in await w.audit_actions(todo["id"])]


async def test_ac23_overdue_is_derived_and_never_stored(w: Collab) -> None:
    yesterday = (await _today() - timedelta(days=1)).isoformat()
    todo = await w.todo(due_on=yesterday)
    read = (await w.call("GET", f"/v1/todos/{todo['id']}", w.marcus)).json()
    assert read["overdue"] is True and read["bucket"] == "overdue"
    assert read["status"] == "open"
    stored = await w.net.seed.value(
        "SELECT status FROM todos WHERE id = $1", uuid.UUID(str(todo["id"]))
    )
    assert stored == "open"


async def test_ac24_ac25_complete_and_undo_are_audited(w: Collab) -> None:
    todo = await w.todo()
    done = await w.call("POST", f"/v1/todos/{todo['id']}/complete", w.marcus)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "done"
    assert done.json()["done_by"]["name"] == "Marcus Delaney"
    undone = await w.call("POST", f"/v1/todos/{todo['id']}/reopen", w.marcus)
    assert undone.status_code == 200, undone.text
    assert undone.json()["status"] == "open" and undone.json()["done_by"] is None
    actions = [a for a, _ in await w.audit_actions(todo["id"])]
    assert "todo.completed" in actions and "todo.reopened" in actions


async def test_ac26_delete_is_soft_and_only_for_creator_assignee_or_manager(w: Collab) -> None:
    todo = await w.todo()
    tom = await w.call("DELETE", f"/v1/todos/{todo['id']}", w.tom)
    assert tom.status_code == 403
    gone = await w.call("DELETE", f"/v1/todos/{todo['id']}", w.marcus)
    assert gone.status_code == 200, gone.text
    mine = await w.call("GET", "/v1/todos?assignee=me", w.marcus)
    assert mine.json()["items"] == []
    kept = await w.net.seed.value(
        "SELECT deleted_by FROM todos WHERE id = $1", uuid.UUID(str(todo["id"]))
    )
    assert kept == w.marcus.user_id
    assert "todo.deleted" in [a for a, _ in await w.audit_actions(todo["id"])]


async def test_ac27_a_move_stays_inside_the_engagement(w: Collab) -> None:
    todo = await w.todo()
    elsewhere = await w.todo(engagement=w.other, title="On Granite")
    here = await w.todo(title="Another on Northwind")
    away = await w.call(
        "POST",
        f"/v1/todos/{todo['id']}/move",
        w.margaret,
        {"anchor": {"anchor_kind": "todo", "anchor_id": elsewhere["id"]}},
    )
    assert away.status_code == 422
    assert away.json()["detail"] == "anchor_scope_mismatch"
    moved = await w.call(
        "POST",
        f"/v1/todos/{todo['id']}/move",
        w.margaret,
        {"anchor": {"anchor_kind": "todo", "anchor_id": here["id"]}},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["anchor"]["anchor_id"] == here["id"]
    assert "todo.moved" in [a for a, _ in await w.audit_actions(todo["id"])]


async def test_ac28_a_firm_scope_to_do_is_for_its_creator_and_assignee(w: Collab) -> None:
    response = await w.call(
        "POST",
        "/v1/todos",
        w.margaret,
        {
            "scope_kind": "firm",
            "title": "Update skill BH-SK-410",
            "assignee_user_id": str(w.hannah.user_id),
        },
    )
    assert response.status_code == 201, response.text
    todo_id = response.json()["id"]
    for who, status in ((w.margaret, 200), (w.hannah, 200), (w.tom, 404)):
        read = await w.call("GET", f"/v1/todos/{todo_id}", who)
        assert read.status_code == status, (who, read.text)


async def test_ac29_my_to_dos_counts_foot_to_the_open_total(w: Collab) -> None:
    today = await _today()
    for offset in (-3, 0, 1, None):
        due = None if offset is None else (today + timedelta(days=offset)).isoformat()
        await w.todo(due_on=due, title=f"Item {offset}")
    page = (await w.call("GET", "/v1/todos?assignee=me&status=open", w.marcus)).json()
    counts = page["counts"]
    assert counts["overdue"] == 1 and counts["today"] == 1 and counts["no_date"] == 1
    assert counts["this_week"] + counts["later"] == 1
    buckets = ("overdue", "today", "this_week", "later", "no_date")
    assert sum(counts[b] for b in buckets) == counts["open"] == 4


async def test_ac30_to_dos_never_enter_the_human_gate_projection(w: Collab) -> None:
    await w.todo()
    assert (
        await w.net.seed.value(
            "SELECT count(*) FROM human_gates WHERE tenant_id = $1", w.tenant_id
        )
        == 0
    )


async def test_ac39_flag_off_the_to_do_routes_answer_not_found(w: Collab) -> None:
    await w.flag(False)
    response = await w.call("GET", "/v1/todos?assignee=me", w.marcus)
    assert response.status_code == 404
