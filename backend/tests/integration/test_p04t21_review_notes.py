"""P-04-T21 acceptance (TASK-1400; ADR-160 clause 6; SHL-09, SHL-12 b): the review notes service.

"Open notes on RA!C14 and RA!C22 block L2 with open_review_notes and count 2, and clearing both
lets the same reviewer sign." Plus: bodies are sealed and their reads are access events, lists
carry no body, only the raiser withdraws, the agent raises nothing, and the assignee is told.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_connection
from abacus.modules.identity.api import agent_context_for_run

from .conftest import MigratedDatabase
from .review_support import PROBE, Cast, as_, make_cast

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()


@pytest.fixture
async def team(migrated_db: MigratedDatabase) -> Cast:
    return await make_cast(migrated_db.superuser_dsn)


async def _raise(
    team: Cast, who: str, target: uuid.UUID, ref: str, **extra: object
) -> dict[str, object]:
    found = await team.call(who)(
        "POST",
        "/v1/review-notes",
        json={
            "target_type": PROBE,
            "target_id": str(target),
            "anchor": {"kind": "cell", "ref": ref},
            "body": f"Tie {ref} to the confirmation.",
            **extra,
        },
    )
    assert found.status_code == 201, found.text
    return cast(dict[str, object], found.json())


def _note_id(detail: dict[str, object]) -> str:
    return str(cast(dict[str, object], detail["note"])["id"])


async def test_ac_open_notes_on_c14_and_c22_block_l2_and_clearing_both_lets_hannah_sign(
    team: Cast,
) -> None:
    target = team.probe()
    assert (await team.sign("ana", target, "L1_preparer")).status_code == 201
    notes = [await _raise(team, "hannah", target, ref) for ref in ("RA!C14", "RA!C22")]
    anchors = [cast(dict[str, object], n["note"])["anchor"] for n in notes]
    assert anchors == [{"kind": "cell", "ref": "RA!C14"}, {"kind": "cell", "ref": "RA!C22"}]

    blocked = await team.sign("hannah", target, "L2_reviewer")
    assert blocked.status_code == 409
    assert blocked.json() == {"detail": "open_review_notes", "facts": {"count": 2}}

    for note in notes:
        cleared = await team.call("hannah")(
            "POST", f"/v1/review-notes/{_note_id(note)}/clear", json={}
        )
        assert cleared.status_code == 200, cleared.text
        assert cast(dict[str, object], cleared.json()["note"])["status"] == "cleared"

    signed = await team.sign("hannah", target, "L2_reviewer")
    assert signed.status_code == 201, signed.text
    assert signed.json()["initials"] == "HL"


async def test_bodies_are_sealed_lists_carry_none_and_a_read_is_an_access_event(
    team: Cast,
) -> None:
    target = team.probe()
    note = await _raise(team, "hannah", target, "RA!C14")
    assert note["body"] == "Tie RA!C14 to the confirmation."
    note_id = uuid.UUID(_note_id(note))
    row = await team.seed.rows(
        "SELECT body, body_sealed FROM reviewable_notes WHERE id = $1", note_id
    )
    assert row[0]["body"] is None and row[0]["body_sealed"] is not None
    assert b"confirmation" not in bytes(row[0]["body_sealed"])
    events = await team.seed.rows(
        "SELECT kind, body, body_sealed FROM reviewable_note_events WHERE note_id = $1", note_id
    )
    assert [(e["kind"], e["body"]) for e in events] == [("raised", None)]
    assert events[0]["body_sealed"] is not None

    listed = await team.call("ana")(
        "GET", "/v1/review-notes", params={"target_type": PROBE, "target_id": str(target)}
    )
    assert listed.status_code == 200, listed.text
    page = listed.json()
    assert [i["id"] for i in page["items"]] == [str(note_id)]
    assert "body" not in page["items"][0]
    assert page["counts"] == {"open": 1}
    assert page["items"][0]["allowed_actions"] == ["review_note.respond"]

    before = await team.value(
        "SELECT count(*) FROM access_events WHERE tenant_id = $1 AND kind = 'review_content.read'",
        team.tenant,
    )
    detail = await team.call("ana")("GET", f"/v1/review-notes/{note_id}")
    assert detail.status_code == 200 and detail.json()["body"].startswith("Tie RA!C14")
    after = await team.value(
        "SELECT count(*) FROM access_events WHERE tenant_id = $1 AND kind = 'review_content.read'",
        team.tenant,
    )
    assert cast(int, after) == cast(int, before) + 1


async def test_respond_keeps_blocking_withdraw_is_the_raisers_and_stops_blocking(
    team: Cast,
) -> None:
    target = team.probe()
    assert (await team.sign("ana", target, "L1_preparer")).status_code == 201
    note_id = _note_id(await _raise(team, "hannah", target, "RA!C14"))

    answered = await team.call("ana")(
        "POST", f"/v1/review-notes/{note_id}/respond", json={"body": "Tied to the SOC 1."}
    )
    assert answered.status_code == 200, answered.text
    assert answered.json()["events"][-1]["event"] == "responded"
    assert answered.json()["events"][-1]["body"] == "Tied to the SOC 1."
    blocked = await team.sign("hannah", target, "L2_reviewer")
    assert blocked.json() == {"detail": "open_review_notes", "facts": {"count": 1}}

    # Only the raiser withdraws: a manager or partner who didn't raise it is refused.
    for who in ("marcus", "margaret"):
        refused = await team.call(who)("POST", f"/v1/review-notes/{note_id}/withdraw", json={})
        assert (refused.status_code, refused.json()["detail"]) == (409, "not_the_raiser"), who
    # Staff may not clear at all; a senior who didn't raise it is not the raiser.
    staff = await team.call("ana")("POST", f"/v1/review-notes/{note_id}/clear", json={})
    assert staff.status_code == 403
    senior = await team.call("marcus")("POST", f"/v1/review-notes/{note_id}/clear", json={})
    assert (senior.status_code, senior.json()["detail"]) == (409, "not_the_raiser")

    withdrawn = await team.call("hannah")("POST", f"/v1/review-notes/{note_id}/withdraw", json={})
    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["note"]["status"] == "withdrawn"
    again = await team.call("hannah")("POST", f"/v1/review-notes/{note_id}/withdraw", json={})
    assert (again.status_code, again.json()["detail"]) == (409, "review_note_state")
    assert (await team.sign("hannah", target, "L2_reviewer")).status_code == 201

    actions = await team.seed.rows(
        "SELECT action, target_type FROM audit_events WHERE tenant_id = $1 "
        "AND action LIKE 'review_note.%' ORDER BY seq",
        team.tenant,
    )
    assert [(a["action"], a["target_type"]) for a in actions] == [
        ("review_note.raised", "reviewable_note"),
        ("review_note.responded", "reviewable_note"),
        ("review_note.withdrawn", "reviewable_note"),
    ]


async def test_the_assignee_is_told_and_must_be_on_the_team(team: Cast) -> None:
    target = team.probe(preparers=frozenset({team["ana"].user_id}))
    note = await _raise(
        team, "hannah", target, "RA!C14", assignee_user_id=str(team["marcus"].user_id)
    )
    assert cast(dict[str, object], note["note"])["assignee_user_id"] == str(team["marcus"].user_id)
    payloads = await team.seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = 'review_note.raised'",
        team.tenant,
    )
    assert len(payloads) == 1
    payload = payloads[0]["payload"]
    text = payload if isinstance(payload, str) else str(payload)
    assert str(team["marcus"].user_id) in text and "confirmation" not in text

    # With no assignee the target's preparers are told; never the raiser.
    second = _note_id(await _raise(team, "hannah", target, "RA!C22"))
    rows = await team.seed.rows(
        "SELECT payload->'recipient_user_ids' AS told FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'review_note.raised' AND payload->>'note_id' = $2",
        team.tenant,
        second,
    )
    told = str(rows[0]["told"])
    assert str(team["ana"].user_id) in told and str(team["hannah"].user_id) not in told

    stranger = await team.seed.person(team.tenant)
    refused = await team.call("hannah")(
        "POST",
        "/v1/review-notes",
        json={
            "target_type": PROBE,
            "target_id": str(target),
            "body": "Who?",
            "assignee_user_id": str(stranger.user_id),
        },
    )
    assert (refused.status_code, refused.json()["detail"]) == (422, "review_note_invalid")


async def test_the_agent_and_staff_raise_nothing_and_unknown_targets_are_refused(
    team: Cast,
) -> None:
    target = team.probe()
    agent = await agent_context_for_run(
        tenant_id=team.tenant,
        run_id=uuid.uuid4(),
        agent_id="evidence.screener",
        engagement_id=team.engagement,
        task_scope=frozenset({"review_note.raise"}),
        initiator_user_id=team["margaret"].user_id,
    )
    body = {"target_type": PROBE, "target_id": str(target), "body": "Agent note."}
    assert (await as_(agent)("POST", "/v1/review-notes", json=body)).status_code == 403
    staff = await team.call("ana")("POST", "/v1/review-notes", json=body)
    assert staff.status_code == 403
    missing = await team.call("hannah")(
        "POST", "/v1/review-notes", json={**body, "target_id": str(uuid.uuid4())}
    )
    assert missing.status_code == 404
    unknown = await team.call("hannah")(
        "POST", "/v1/review-notes", json={**body, "target_type": "no_such_type"}
    )
    assert (unknown.status_code, unknown.json()["detail"]) == (422, "unregistered_kind")
    assert (
        await team.value("SELECT count(*) FROM reviewable_notes WHERE tenant_id = $1", team.tenant)
        == 0
    )


async def test_another_firm_reads_and_writes_nothing(
    team: Cast, migrated_db: MigratedDatabase
) -> None:
    target = team.probe()
    note_id = _note_id(await _raise(team, "hannah", target, "RA!C14"))
    other = await make_cast(migrated_db.superuser_dsn)
    for method, path in (
        ("GET", f"/v1/review-notes/{note_id}"),
        ("POST", f"/v1/review-notes/{note_id}/respond"),
    ):
        found = await other.call("hannah")(method, path, json={"body": "x"})
        assert found.status_code == 404, (method, path)
    listed = await other.call("hannah")("GET", "/v1/review-notes")
    assert listed.json()["items"] == []


async def test_the_data_layer_holds_the_note_transitions(team: Cast) -> None:
    """Security review M4 (0213): a note's status only moves forward, only a person moves it,
    only the raiser withdraws it, and a withdrawn event is a person's."""
    target = team.probe()
    note_id = uuid.UUID(_note_id(await _raise(team, "hannah", target, "RA!C14")))
    hannah = ("human", str(team["hannah"].user_id))
    await _refused_update(team, ("agent", "agent:evidence.screener:run"), "cleared", note_id)
    await _refused_update(team, ("human", str(team["marcus"].user_id)), "withdrawn", note_id)
    # Re-review L3: the raiser setting the status alone, with no event written now, is refused.
    await _refused_update(team, hannah, "cleared", note_id)
    await _refused_update(team, hannah, "withdrawn", note_id)
    withdrawn = await team.call("hannah")("POST", f"/v1/review-notes/{note_id}/withdraw", json={})
    assert withdrawn.status_code == 200, withdrawn.text
    await _refused_update(team, hannah, "open", note_id)  # withdrawn is final
    await _refused_update(team, hannah, "responded", note_id)
    with pytest.raises(DBAPIError):
        async with tenant_connection(TenantContext(team.tenant, "agent", "agent:x:y")) as conn:
            await conn.execute(
                text(
                    "INSERT INTO reviewable_note_events (tenant_id, note_id, kind, by_user) "
                    "VALUES (:t, :n, 'withdrawn', :u)"
                ),
                {"t": team.tenant, "n": note_id, "u": team["hannah"].user_id},
            )  # refused at the statement: nothing to commit, and the connection rolls back


async def _refused_update(
    team: Cast, actor: tuple[str, str], status: str, note_id: uuid.UUID
) -> None:
    """The guard refuses at the statement; the connection rolls back on leaving."""
    tenant = TenantContext(team.tenant, actor[0], actor[1])  # type: ignore[arg-type]  # the actor kind under test
    with pytest.raises(DBAPIError):
        async with tenant_connection(tenant) as conn:
            await conn.execute(
                text("UPDATE reviewable_notes SET status = :s WHERE id = :id"),
                {"s": status, "id": note_id},
            )
