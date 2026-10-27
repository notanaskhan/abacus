# ac-test-author: ayushkbhatia
"""SPEC-360 AC-1, AC-2, AC-3, AC-6 (P-04-T21, T22, T23, T26; TASK-1464): review notes, bulk
sign-off, decision cards and their notifications.

What the contract promises (`docs/contracts/review-grammar.md` parts 1 and 2, §5 to §7; ADR-005,
ADR-160 clauses 4, 6, 8, 12; DEC-500 to DEC-507, DEC-605):
- open notes on RA!C14 and RA!C22 block L2 with `open_review_notes` and count 2, and clearing
  both lets the same reviewer sign; bodies are sealed, lists carry none, a body read is an access
  event; only the raiser withdraws; the agent raises nothing; the assignee (else the preparers)
  is told once, walls re-checked at fan-out;
- six workpapers with three ineligible: three signed and three excluded with reasons; a replay
  with the same key returns the stored result, another body is 422 `idempotency_key_reused`;
  reviewers only, a fresh second factor, a preparer never reviews their own work, a hidden target
  is excluded like a missing one;
- only Margaret Okonkwo decides the Northwind card; 422 `rationale_required`; reassessment on
  $16,861,000 records No change with the $700 difference; MFA, staleness and second decides;
- the agent and the platform never decide, sign, clear or reassess, at the matrix and the data
  layer (INV-1); walls and other firms answer 404.

Boundary: `create_app()` over HTTP as each signed-in person; the card raised through
`review.api.raise_decision_card` by the agent on a recorded run; the reviewable and the decision
kind registered through review's public slots, as owners register theirs; the notification
fan-out through `notifications.api.SUBSCRIPTIONS` with the outbox rows the product wrote.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Final, cast

import pytest
from sqlalchemy import text

from abacus.kernel.uow import Target, uow
from abacus.modules.identity.api import (
    AgentContext,
    Forbidden,
    Resource,
    authorise,
    system_context_for_run,
)
from abacus.modules.notifications import api as notifications
from abacus.modules.review import api as review_api
from abacus.modules.review.api import raise_decision_card

from .p04t28_support import (
    MATERIALITY,
    PROBE,
    QUESTION,
    World,
    agent,
    audit_rows,
    deliver,
    hash_of,
    make_world,
    notified,
    probe,
    second_site,
)
from .support import Net, Person, Site

pytestmark = pytest.mark.asyncio
CARDS: Final = "/v1/decision-cards"
NOTES: Final = "/v1/review-notes"
SIGN: Final = "/v1/sign-offs"
REVIEWER_V1: Final = "reviewer-v1"
RAISE: Final = frozenset({"decision_card.raise"})


@pytest.fixture
async def world(net: Net) -> World:
    return await make_world(net)


@pytest.fixture(autouse=True)
async def no_email() -> AsyncIterator[None]:
    async def nothing(_given: object) -> None:
        return None

    notifications.configure_email_starter(nothing)
    yield
    notifications.configure_email_starter(None)


# --- Helpers ----------------------------------------------------------------------------------


async def _card(world: World, *, site: Site | None = None) -> uuid.UUID:
    """The agent raises Northwind's planning materiality card, reserved to Margaret."""
    where = site or world.site
    return await raise_decision_card(
        await agent(world, RAISE, site=where),
        engagement_id=where.engagement_id,
        kind=MATERIALITY,
        question_key=QUESTION,
        reserved_user_id=world["margaret"].user_id,
        recommended_option_key="pct_1_5",
    )


def _decide(
    seen: int = 1, *, rationale: str | None = "Consistent with PY2024."
) -> dict[str, object]:
    body: dict[str, object] = {
        "option_key": "pct_1_5",
        "factors": ["late_deposits"],
        "seen_version": seen,
    }
    if rationale is not None:
        body["rationale"] = rationale
    return body


async def _card_status(world: World, card: uuid.UUID) -> str:
    return str(await world.seed.value("SELECT status FROM decision_cards WHERE id = $1", card))


async def _decisions_of(world: World, card: uuid.UUID) -> int:
    return cast(
        int,
        await world.seed.value(
            "SELECT count(*) FROM decisions WHERE tenant_id = $1 AND to_jsonb(decisions)::text "
            "LIKE '%' || $2 || '%'",
            world.tenant_id,
            str(card),
        ),
    )


async def _sign(world: World, who: str, target: uuid.UUID, level: str, **over: str) -> str:
    """One sign-off's status and detail, for readable assertions ("201", "409 segregation")."""
    response = await world.call(
        "POST",
        SIGN,
        who,
        {
            "target_type": PROBE,
            "target_id": str(target),
            "level": level,
            "seen_hash": over.get("seen_hash", hash_of(target)),
            "statement_version": REVIEWER_V1,
        },
    )
    if response.status_code < 400:
        return str(response.status_code)
    return f"{response.status_code} {response.json().get('detail')}"


async def _raise(
    world: World, who: str, target: uuid.UUID, ref: str, body: str, assignee: Person | None = None
) -> uuid.UUID:
    payload: dict[str, object] = {
        "target_type": PROBE,
        "target_id": str(target),
        "anchor": {"kind": "cell", "ref": ref},
        "body": body,
    }
    if assignee is not None:
        payload["assignee_user_id"] = str(assignee.user_id)
    raised = await world.call("POST", NOTES, who, payload)
    assert raised.status_code == 201, raised.text
    return uuid.UUID(raised.json()["note"]["id"])


# --- AC-3: decision cards ----------------------------------------------------------------------


async def test_ac3_only_margaret_okonkwo_can_decide_the_northwind_card(world: World) -> None:
    card = await _card(world)
    path = f"{CARDS}/{card}"
    hannah_view = await world.call("GET", path, "hannah")
    assert hannah_view.status_code == 200, hannah_view.text
    body = hannah_view.json()
    assert body["card"]["status"] == "awaiting_role" and body["card"]["version_no"] == 1
    assert body["card"]["reserved_role"] == "engagement_partner"
    assert body["card"]["reserved_user_name"] == "Margaret Okonkwo"
    assert "decision.decide" not in body["card"]["allowed_actions"]
    figures = {o["key"]: o["figures"] for o in body["options"]}
    assert figures["pct_1_0"]["materiality"] == "168100"
    assert figures["pct_1_5"] == {
        "rate": "0.015",
        "materiality": "252200",
        "performance_materiality": "189150",
        "clearly_trivial": "12610",
    }
    # The agent's recommendation is a tag on one option, never a decision (DEC-502).
    assert {o["key"]: o["recommended"] for o in body["options"]} == {
        "pct_1_0": False,
        "pct_1_5": True,
    }
    assert body["decision"] is None
    assert body["history"][0]["actor_kind"] == "agent"
    assert body["history"][0]["event"] == "proposed"

    for who in ("hannah", "priya", "samuel", "kevin"):
        refused = await world.call("POST", f"{path}/decide", who, _decide())
        assert refused.status_code == 403, (who, refused.text)
    assert await _card_status(world, card) == "awaiting_role"

    margaret_view = (await world.call("GET", path, "margaret")).json()
    assert "decision.decide" in margaret_view["card"]["allowed_actions"]
    decided = await world.call("POST", f"{path}/decide", "margaret", _decide())
    assert decided.status_code == 200, decided.text
    out = decided.json()
    assert out["card"]["status"] == "decided" and out["card"]["version_no"] == 2
    assert out["decision"]["option_key"] == "pct_1_5"
    assert out["decision"]["decided_by_name"] == "Margaret Okonkwo"
    assert out["decision"]["seen_card_version"] == 1
    assert await audit_rows(world, "decision.decided") == [
        ("human", str(world["margaret"].user_id))
    ]

    again = await world.call("POST", f"{path}/decide", "margaret", _decide(2))
    assert again.status_code == 409 and again.json()["detail"] == "decision_card_state"
    assert len(await audit_rows(world, "decision.decided")) == 1


async def test_ac3_a_decide_without_a_rationale_returns_422_rationale_required(
    world: World,
) -> None:
    card = await _card(world)
    for rationale in (None, ""):
        refused = await world.call(
            "POST", f"{CARDS}/{card}/decide", "margaret", _decide(rationale=rationale)
        )
        assert refused.status_code == 422, refused.text
        if rationale is None:
            assert refused.json() == {"detail": "rationale_required"}
    unknown = await world.call(
        "POST", f"{CARDS}/{card}/decide", "margaret", {**_decide(), "option_key": "pct_9_9"}
    )
    assert unknown.status_code == 422 and unknown.json()["detail"] == "decision_invalid"
    assert await _card_status(world, card) == "awaiting_role"
    assert await audit_rows(world, "decision.decided") == []


async def test_ac3_a_stale_second_factor_or_card_version_decides_nothing(world: World) -> None:
    card = await _card(world)
    path = f"{CARDS}/{card}"
    stale_mfa = await world.stale_mfa("POST", f"{path}/decide", "margaret", _decide())
    assert stale_mfa.status_code == 403, stale_mfa.text
    assert stale_mfa.json() == {"detail": "mfa_required", "facts": {"max_age_s": 900}}

    # Hannah reassesses the awaiting card: no change is a new version (v2), so v1 is stale.
    reassessed = await world.call("POST", f"{path}/reassess", "hannah")
    assert reassessed.status_code == 200, reassessed.text
    assert reassessed.json()["card"]["version_no"] == 2
    stale = await world.call("POST", f"{path}/decide", "margaret", _decide(1))
    assert stale.status_code == 409 and stale.json()["detail"] == "recommendation_changed"
    assert await _card_status(world, card) == "awaiting_role"
    fresh = await world.call("POST", f"{path}/decide", "margaret", _decide(2))
    assert fresh.status_code == 200, fresh.text


async def test_ac3_reassessment_on_16861000_records_no_change_with_the_700_difference(
    world: World,
) -> None:
    card = await _card(world)
    path = f"{CARDS}/{card}"
    assert (await world.call("POST", f"{path}/decide", "margaret", _decide())).status_code == 200
    # On a decided card the reassessment may supersede a decision: the reserved person's act.
    hannah = await world.call("POST", f"{path}/reassess", "hannah")
    assert hannah.status_code == 403, hannah.text
    staff = await world.call("POST", f"{path}/reassess", "ana")
    assert staff.status_code == 403
    reassessed = await world.call("POST", f"{path}/reassess", "margaret")
    assert reassessed.status_code == 200, reassessed.text
    body = reassessed.json()
    assert body["card"]["status"] == "decided" and body["card"]["version_no"] == 3
    v3 = body["history"][-1]
    assert (v3["version_no"], v3["event"], v3["changed"]) == (3, "reassessed", False)
    assert v3["figures"] == {"benchmark": "16861000", "materiality": "252900", "difference": "700"}
    assert v3["actor_kind"] == "human"
    assert await audit_rows(world, "decision.reassessed") == [
        ("human", str(world["margaret"].user_id))
    ]


async def test_ac3_the_agent_raises_only_through_its_task_on_its_own_engagement(
    world: World,
) -> None:
    other = await second_site(world, "Copperleaf")
    acting = await agent(world, RAISE)  # a run on Northwind
    with pytest.raises(Forbidden):
        await raise_decision_card(
            acting,
            engagement_id=other.engagement_id,
            kind=MATERIALITY,
            question_key=QUESTION,
            reserved_user_id=world["margaret"].user_id,
        )
    unscoped = await agent(world, frozenset({"proposal.create"}))  # not in its task
    with pytest.raises(Forbidden):
        await raise_decision_card(
            unscoped,
            engagement_id=world.site.engagement_id,
            kind=MATERIALITY,
            question_key=QUESTION,
            reserved_user_id=world["margaret"].user_id,
        )
    count = await world.seed.value(
        "SELECT count(*) FROM decision_cards WHERE tenant_id = $1", world.tenant_id
    )
    assert count == 0


async def test_ac3_walls_need_to_know_and_other_firms_see_and_decide_nothing(
    world: World, net: Net
) -> None:
    card = await _card(world)
    path = f"{CARDS}/{card}"
    outsider = await world.seed.person(world.tenant_id)  # same firm, not on the engagement
    elsewhere = await make_world(net, "Northwind elsewhere")
    await world.net.wall(world.admin, world["margaret"], world.site)
    assert (await world.call("GET", path, "margaret")).status_code == 404
    walled = await world.call("POST", f"{path}/decide", "margaret", _decide())
    assert walled.status_code == 404, walled.text
    for who, tenant in (
        (outsider, None),
        (elsewhere["margaret"], None),
        (elsewhere["margaret"], world.tenant_id),
    ):
        read = await world.call("GET", path, who, tenant=tenant)
        assert read.status_code in (403, 404), read.text
        assert "252200" not in read.text
        decide = await world.call("POST", f"{path}/decide", who, _decide(), tenant=tenant)
        assert decide.status_code in (403, 404)
    for tenant in (None, world.tenant_id):  # another firm: 404, never 403 (DEC-43)
        assert (
            await world.call("GET", path, elsewhere["margaret"], tenant=tenant)
        ).status_code == 404
    assert await _card_status(world, card) == "awaiting_role"


async def test_ac6_decision_assigned_reaches_the_reserved_person_once(world: World) -> None:
    await _card(world)
    assert await deliver(world, "decision_card.raised") == 1
    assert await notified(world, "decision_assigned") == [world["margaret"].user_id]


# --- AC-1: review notes ------------------------------------------------------------------------


async def test_ac1_two_open_notes_block_l2_and_clearing_both_lets_the_same_reviewer_sign(
    world: World,
) -> None:
    target = probe(world.site, (world["ana"],))
    assert await _sign(world, "ana", target, "L1_preparer") == "201"
    c14 = await _raise(world, "hannah", target, "RA!C14", "Tie RA!C14 to the trustee statement.")
    c22 = await _raise(world, "hannah", target, "RA!C22", "Explain the RA!C22 variance.")
    blocked = await world.call(
        "POST",
        SIGN,
        "hannah",
        {
            "target_type": PROBE,
            "target_id": str(target),
            "level": "L2_reviewer",
            "seen_hash": hash_of(target),
            "statement_version": REVIEWER_V1,
        },
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json() == {"detail": "open_review_notes", "facts": {"count": 2}}
    # A response alone does not unblock (answered notes still block).
    responded = await world.call("POST", f"{NOTES}/{c14}/respond", "ana", {"body": "Tied."})
    assert responded.status_code == 200, responded.text
    assert await _sign(world, "hannah", target, "L2_reviewer") == "409 open_review_notes"
    for note in (c14, c22):
        cleared = await world.call("POST", f"{NOTES}/{note}/clear", "hannah", {})
        assert cleared.status_code == 200, cleared.text
    assert await _sign(world, "hannah", target, "L2_reviewer") == "201"
    assert [a for a, _ in await audit_rows(world, "review_note.cleared")] == ["human", "human"]


async def test_ac1_bodies_are_sealed_lists_carry_none_and_a_body_read_is_an_access_event(
    world: World,
) -> None:
    target = probe(world.site, (world["ana"],))
    marker = f"Contribution remittance gap {uuid.uuid4().hex[:10]}"
    note = await _raise(world, "hannah", target, "RA!C14", marker)
    listed = await world.call("GET", f"{NOTES}?target_type={PROBE}&target_id={target}", "ana")
    assert listed.status_code == 200, listed.text
    assert marker not in listed.text
    assert all("body" not in item for item in listed.json()["items"])
    assert [item["id"] for item in listed.json()["items"]] == [str(note)]
    plain = await world.seed.value(
        "SELECT (SELECT count(*) FROM review_notes n WHERE to_jsonb(n)::text "
        "LIKE '%' || $1 || '%') + (SELECT count(*) FROM review_note_events e "
        "WHERE to_jsonb(e)::text LIKE '%' || $1 || '%')",
        marker,
    )
    assert plain == 0  # sealed at rest
    # Raising answers the detail (with the body), so the raiser's read may be recorded; what
    # matters is that the list reads none and Ana's detail read is one access event.
    reads_sql = (
        "SELECT kind, actor_kind, actor_id FROM access_events WHERE tenant_id = $1 "
        "AND subject_id = $2 AND actor_id = $3"
    )
    assert await world.seed.rows(reads_sql, world.tenant_id, note, world["ana"].user_id) == []
    detail = await world.call("GET", f"{NOTES}/{note}", "ana")
    assert detail.status_code == 200, detail.text
    assert detail.json()["body"] == marker
    reads = await world.seed.rows(reads_sql, world.tenant_id, note, world["ana"].user_id)
    assert [(r["kind"], r["actor_kind"], r["actor_id"]) for r in reads] == [
        ("review_content.read", "human", world["ana"].user_id)
    ]


async def test_ac1_only_the_raiser_withdraws_and_a_withdrawn_note_takes_nothing_more(
    world: World,
) -> None:
    target = probe(world.site, (world["ana"],))
    note = await _raise(world, "hannah", target, "RA!C14", "Please re-perform.")
    for who in ("margaret", "samuel"):
        refused = await world.call("POST", f"{NOTES}/{note}/withdraw", who, {})
        assert refused.status_code == 409, (who, refused.text)
        assert refused.json()["detail"] == "not_the_raiser"
    staff = await world.call("POST", f"{NOTES}/{note}/withdraw", "ana", {})
    assert staff.status_code == 403  # review_note.withdraw holds no staff cell
    withdrawn = await world.call("POST", f"{NOTES}/{note}/withdraw", "hannah", {})
    assert withdrawn.status_code == 200, withdrawn.text
    for verb, who in (("respond", "ana"), ("clear", "hannah"), ("withdraw", "hannah")):
        late = await world.call(
            "POST", f"{NOTES}/{note}/{verb}", who, {"body": "x"} if verb == "respond" else {}
        )
        assert late.status_code == 409 and late.json()["detail"] == "review_note_state"


async def test_ac1_raising_needs_a_registered_reviewable_and_a_role_that_raises(
    world: World,
) -> None:
    target = probe(world.site, (world["ana"],))
    for who in ("ana", "lena"):  # staff hold no review_note.raise cell
        staff = await world.call(
            "POST", NOTES, who, {"target_type": PROBE, "target_id": str(target), "body": "x"}
        )
        assert staff.status_code == 403
    unregistered = await world.call(
        "POST",
        NOTES,
        "hannah",
        {"target_type": "indep_nothing", "target_id": str(uuid.uuid4()), "body": "x"},
    )
    assert unregistered.status_code == 422 and unregistered.json()["detail"] == "unregistered_kind"
    unknown = await world.call(
        "POST",
        NOTES,
        "hannah",
        {"target_type": PROBE, "target_id": str(uuid.uuid4()), "body": "x"},
    )
    assert unknown.status_code == 404
    self_assigned = await world.call(
        "POST",
        NOTES,
        "hannah",
        {
            "target_type": PROBE,
            "target_id": str(target),
            "body": "x",
            "assignee_user_id": str(world["hannah"].user_id),
        },
    )
    assert self_assigned.status_code == 422
    assert self_assigned.json()["detail"] == "review_note_invalid"


async def test_ac1_review_note_raised_reaches_the_assignee_else_the_preparers_walls_rechecked(
    world: World,
) -> None:
    target = probe(world.site, (world["ana"],))
    await _raise(world, "hannah", target, "RA!C14", "For Lena.", assignee=world["lena"])
    await _raise(world, "hannah", target, "RA!C22", "For the preparer.")
    await world.net.wall(world.admin, world["lena"], world.site)  # after raising, before fan-out
    assert await deliver(world, "review_note.raised") == 2
    assert await notified(world, "review_note_raised") == [world["ana"].user_id]


async def test_ac1_walls_and_other_firms_read_no_note(world: World, net: Net) -> None:
    target = probe(world.site, (world["ana"],))
    note = await _raise(world, "hannah", target, "RA!C14", "Walled body text.")
    await world.net.wall(world.admin, world["samuel"], world.site)
    elsewhere = await make_world(net, "Northwind elsewhere")
    for who, tenant in (
        (world["samuel"], None),
        (elsewhere["hannah"], None),
        (elsewhere["hannah"], world.tenant_id),
    ):
        read = await world.call("GET", f"{NOTES}/{note}", who, tenant=tenant)
        assert read.status_code == 404, read.text
        clear = await world.call(
            "POST", f"{NOTES}/{note}/respond", who, {"body": "x"}, tenant=tenant
        )
        assert clear.status_code == 404
    reads = await world.seed.value(
        "SELECT count(*) FROM access_events WHERE subject_id = $1 AND actor_id <> $2",
        note,
        world["hannah"].user_id,
    )
    assert reads == 0  # nobody but the raiser read the body


# --- AC-2: bulk sign-off -----------------------------------------------------------------------


async def test_ac2_six_workpapers_three_ineligible_and_a_replay_returns_the_stored_result(
    world: World,
) -> None:
    targets = [probe(world.site, (world["ana"],), hash_text=f"wp{n}") for n in range(6)]
    no_l1, noted, moved = targets[3], targets[4], targets[5]
    for target in (*targets[:3], noted, moved):
        assert await _sign(world, "ana", target, "L1_preparer") == "201"
    await _raise(world, "hannah", noted, "RA!C14", "Open question.")
    body = {
        "level": "L2_reviewer",
        "statement_version": REVIEWER_V1,
        "targets": [
            {
                "target_type": PROBE,
                "target_id": str(t),
                "seen_hash": hash_of(t) if t != moved else "sha256:" + "0" * 64,
            }
            for t in targets
        ],
    }
    key = str(uuid.uuid4())
    first = await world.call_with("POST", f"{SIGN}:bulk", "hannah", body, {"Idempotency-Key": key})
    assert first.status_code == 200, first.text
    out = first.json()
    assert (out["signed"], out["excluded"]) == (3, 3)
    details = {r["target_id"]: (r["ok"], r["detail"]) for r in out["results"]}
    assert details == {
        **{str(t): (True, None) for t in targets[:3]},
        str(no_l1): (False, "not_prepared"),
        str(noted): (False, "open_review_notes"),
        str(moved): (False, "content_changed"),
    }
    assert all(r["sign_off_id"] for r in out["results"] if r["ok"])
    recorded = len(await audit_rows(world, "sign_off.recorded"))

    replay = await world.call_with(
        "POST", f"{SIGN}:bulk", "hannah", body, {"Idempotency-Key": key}
    )
    assert replay.status_code == 200, replay.text
    assert replay.json() == out
    assert len(await audit_rows(world, "sign_off.recorded")) == recorded  # nothing signed again

    other_body = {**body, "targets": body["targets"][:2]}
    reused = await world.call_with(
        "POST", f"{SIGN}:bulk", "hannah", other_body, {"Idempotency-Key": key}
    )
    assert reused.status_code == 422 and reused.json()["detail"] == "idempotency_key_reused"


async def test_ac2_reviewers_only_fresh_mfa_never_the_preparer_and_a_hidden_target_says_nothing(
    world: World, net: Net
) -> None:
    mine = probe(world.site, (world["ana"],))
    raj_prepared = probe(world.site, (world["raj"],))
    for target in (mine, raj_prepared):
        assert (
            await _sign(world, "ana" if target == mine else "raj", target, "L1_preparer") == "201"
        )
    elsewhere = await make_world(net, "Northwind elsewhere")
    hidden = probe(elsewhere.site, (elsewhere["ana"],))

    def bulk(*targets: uuid.UUID) -> dict[str, object]:
        return {
            "level": "L2_reviewer",
            "statement_version": REVIEWER_V1,
            "targets": [
                {"target_type": PROBE, "target_id": str(t), "seen_hash": hash_of(t)}
                for t in targets
            ],
        }

    def key() -> dict[str, str]:
        return {"Idempotency-Key": str(uuid.uuid4())}

    staff = await world.call_with("POST", f"{SIGN}:bulk", "ana", bulk(mine), key())
    assert staff.status_code == 403
    stale = await world.stale_mfa("POST", f"{SIGN}:bulk", "hannah", bulk(mine), **key())
    assert stale.status_code == 403, stale.text
    assert stale.json() == {"detail": "mfa_required", "facts": {"max_age_s": 900}}
    missing_key = await world.call("POST", f"{SIGN}:bulk", "hannah", bulk(mine))
    assert missing_key.status_code == 422
    twice = await world.call_with("POST", f"{SIGN}:bulk", "hannah", bulk(mine, mine), key())
    assert twice.status_code == 422 and twice.json()["detail"] == "sign_off_invalid"

    # Raj prepared one of them: he never reviews his own work (R-SO-3, self-approval).
    by_raj = await world.call_with("POST", f"{SIGN}:bulk", "raj", bulk(mine, raj_prepared), key())
    assert by_raj.status_code == 200, by_raj.text
    raj_details = {r["target_id"]: r["detail"] for r in by_raj.json()["results"]}
    assert raj_details == {str(mine): None, str(raj_prepared): "segregation"}

    unknown = uuid.uuid4()
    from_p04t28 = bulk(raj_prepared)
    cast(list[dict[str, str]], from_p04t28["targets"]).extend(
        [
            {"target_type": PROBE, "target_id": str(hidden), "seen_hash": hash_of(hidden)},
            {"target_type": PROBE, "target_id": str(unknown), "seen_hash": hash_of(mine)},
        ]
    )
    mixed = await world.call_with("POST", f"{SIGN}:bulk", "hannah", from_p04t28, key())
    assert mixed.status_code == 200, mixed.text
    by_target = {r["target_id"]: r for r in mixed.json()["results"]}
    assert by_target[str(hidden)]["detail"] == by_target[str(unknown)]["detail"]
    assert by_target[str(hidden)]["detail"] == "level_not_permitted"
    assert by_target[str(hidden)]["sign_off_id"] is None
    only_hidden = await world.call_with("POST", f"{SIGN}:bulk", "hannah", bulk(hidden), key())
    assert only_hidden.status_code == 403  # sign_off.bulk on none of the targets' engagements


# --- INV-1 at every layer ----------------------------------------------------------------------
HUMAN_ONLY: Final = (
    "decision.decide",
    "decision.reassess",
    "decision.notify",
    "decision.request_analysis",
    "review_note.raise",
    "review_note.respond",
    "review_note.clear",
    "review_note.withdraw",
    "sign_off.create",
    "sign_off.bulk",
    "sign_off.review",
)


async def test_inv1_the_matrix_refuses_the_agent_and_the_platform_every_human_act(
    world: World,
) -> None:
    resource = Resource.engagement(world.tenant_id, world.site.engagement_id, archived=False)
    acting: AgentContext = await agent(world, frozenset({*HUMAN_ONLY, *RAISE}))  # even in scope
    platform = system_context_for_run(
        tenant_id=world.tenant_id,
        run_id=uuid.uuid4(),
        engagement_id=world.site.engagement_id,
        on_behalf_of=world["margaret"].user_id,
    )
    for action in HUMAN_ONLY:
        for ctx in (acting, platform):
            with pytest.raises(Forbidden):
                await authorise(ctx, action, resource)


def test_inv1_the_review_api_offers_no_decide_or_sign_for_an_agent_to_call() -> None:
    exported = set(dir(review_api))
    for name in ("decide", "decide_card", "reassess", "clear_note", "sign_target", "bulk_sign"):
        assert name not in exported


async def test_inv1_the_data_layer_refuses_a_decision_written_as_the_agent_or_platform(
    world: World,
) -> None:
    card = await _card(world)
    acting = await agent(world)
    platform = system_context_for_run(
        tenant_id=world.tenant_id,
        run_id=uuid.uuid4(),
        engagement_id=world.site.engagement_id,
        on_behalf_of=world["margaret"].user_id,
    )
    for tenant in (acting.tenant, platform.tenant):
        with pytest.raises(Exception):  # noqa: B017 -- the guard's error class is the DB's
            async with uow(tenant) as tx:
                await tx.session.execute(
                    text("UPDATE decision_cards SET status = 'decided' WHERE id = :id"),
                    {"id": card},
                )
                tx.record("decision_card.probed", target=Target("decision_card", card))
    # The human-only audit list refuses the verdict written as the agent (0097, 0212).
    with pytest.raises(Exception):  # noqa: B017
        async with uow(acting.tenant) as tx:
            tx.record("decision.decided", target=Target("decision_card", card))
    assert await _card_status(world, card) == "awaiting_role"
    assert await audit_rows(world, "decision.decided") == []
    assert await _decisions_of(world, card) == 0
