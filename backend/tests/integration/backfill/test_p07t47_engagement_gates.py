"""P-07-T47 (TASK-1446; P-07 §4.8; C13, C16; DEC-539, DEC-540): "Daniel Reyes's HOME-02 row
appears once Thornbury is sent to the partner and disappears when the decision is recorded."

Thornbury's acceptance runs over HTTP (`create_app()`, as P-07-T38's suite drives it); the C13
projector is driven as the worker drives it: every outbox event of the fixed C13 set the product
wrote, in order, through `review.api.SUBSCRIPTIONS`. The gate list is `GET /v1/human-gates`
behind `review.grammar_api`. Notifications are checked through the catalogue's fan-out rows."""

from __future__ import annotations

import json
import uuid
from typing import cast

import pytest

from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.notifications.api import CATALOGUE
from abacus.modules.notifications.api import SUBSCRIPTIONS as NOTIFY
from abacus.modules.notifications.kinds import kind_of
from abacus.modules.review.api import C13_EVENTS
from abacus.modules.review.api import SUBSCRIPTIONS as GATES
from abacus.modules.review.engagement_gates import SOURCES

from . import test_p07t38_acceptance_independent as t38
from .support import Net, Person, Seeder

pytestmark = pytest.mark.asyncio
Json = dict[str, object]
_seen: set[uuid.UUID] = set()


async def _replay(seed: Seeder, tenant: uuid.UUID, kinds: frozenset[str]) -> None:
    """The firm's outbox events of `kinds` not delivered yet, in order, as the worker does."""
    rows = await seed.rows(
        "SELECT id, event_type, payload FROM outbox WHERE tenant_id = $1 "
        "AND event_type = ANY($2::text[]) ORDER BY seq",
        tenant,
        sorted(kinds),
    )
    for row in rows:
        if row["id"] in _seen:
            continue
        _seen.add(row["id"])
        payload = row["payload"]
        event = OutboxEvent(
            row["id"],
            tenant,
            str(row["event_type"]),
            cast(Json, json.loads(payload) if isinstance(payload, str) else payload),
        )
        if event.event_type in GATES:
            await GATES[event.event_type](event)
        if event.event_type in CATALOGUE:
            await NOTIFY[event.event_type](event)


async def _gates(tb: t38.Thornbury, who: Person) -> list[Json]:
    response = await tb.call("GET", "/v1/human-gates", who)
    assert response.status_code == 200, response.text
    return cast(list[Json], response.json()["items"])


async def _flag(seed: Seeder, tenant: uuid.UUID) -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'review.grammar_api', 'true', 'test-seed', 'P-07-T47')",
        tenant,
    )


async def test_ac_daniels_row_appears_when_sent_and_goes_when_decided(net: Net) -> None:
    tb = await t38._world(net)  # pyright: ignore[reportPrivateUsage] -- P-07-T38's Thornbury
    await _flag(tb.seed, tb.tenant)
    await tb.start()
    for code, _ in t38.SECTIONS:
        await tb.answer(code)
    await _replay(tb.seed, tb.tenant, C13_EVENTS)
    assert await _gates(tb, tb.daniel) == []  # still a draft: nothing waits on Daniel
    sent = await tb.send()
    assert sent.status_code == 200, sent.text
    await _replay(tb.seed, tb.tenant, C13_EVENTS | frozenset(CATALOGUE))
    rows = await _gates(tb, tb.daniel)
    assert [(r["kind"], r["subject_type"]) for r in rows] == [
        ("decision", "acceptance_decision_due")
    ]
    assert rows[0]["engagement_id"] == str(tb.engagement_id)
    assert rows[0]["assignee_user_id"] == str(tb.daniel.user_id)
    # The row is Daniel's: Samuel, who prepared it, has nothing waiting; Kira neither.
    assert await _gates(tb, tb.samuel) == []
    assert await _gates(tb, tb.kira) == []
    # C16: Daniel was told, by identifiers only (no text is stored on a notification).
    told = await tb.seed.rows(
        "SELECT recipient_user_id, kind, subject_type FROM notifications "
        "WHERE tenant_id = $1 AND kind = 'acceptance_awaiting_partner'",
        tb.tenant,
    )
    assert [(r["recipient_user_id"], r["subject_type"]) for r in told] == [
        (tb.daniel.user_id, "acceptance_record")
    ]
    decided = await tb.decide("accept")
    assert decided.status_code == 200, decided.text
    await _replay(tb.seed, tb.tenant, C13_EVENTS)
    assert await _gates(tb, tb.daniel) == []
    state = await tb.seed.value(
        "SELECT state FROM human_gates WHERE tenant_id = $1 "
        "AND subject_ref->>'type' = 'acceptance_decision_due'",
        tb.tenant,
    )
    assert state == "done"


def test_the_four_gate_kinds_are_registered_and_no_agent_can_act_through_them() -> None:
    assert {s.subject_type: s.kind for s in SOURCES} == {
        "acceptance_decision_due": "decision",
        "independence_conclusion_due": "decision",
        "independence_confirmation_due": "sign_off_request",
        "eqr_eligibility_due": "decision",
    }
    # A gate only says that something waits; its read actions are reads.
    assert {s.read_action for s in SOURCES} == {
        "acceptance.read",
        "independence.read",
        "eqr.approve_eligibility",
    }
    for source in SOURCES:
        assert source.events <= C13_EVENTS


def test_the_c16_kinds_are_registered_without_inline_actions() -> None:
    for code in (
        "acceptance_awaiting_partner",
        "risk_partner_review_requested",
        "independence_reminder",
        "independence_conclusion_due",
        "team_change_awaiting_approval",
        "invitation_expiring",
    ):
        kind = kind_of(code)
        assert kind is not None, code
        assert kind.inline_actions == ()
    reminder = kind_of("independence_reminder")
    assert reminder is not None and reminder.email_default


async def test_the_risk_review_tells_the_named_partner_only(net: Net) -> None:
    tb = await t38._world(net)  # pyright: ignore[reportPrivateUsage] -- P-07-T38's Thornbury
    await tb.start()
    asked = await tb.call(
        "POST",
        f"{tb.acc}/risk-partner-review",
        tb.daniel,
        {"partner_id": str(tb.rita.user_id)},
    )
    assert asked.status_code in (200, 201), asked.text
    await _replay(tb.seed, tb.tenant, frozenset(CATALOGUE))
    told = await tb.seed.rows(
        "SELECT recipient_user_id FROM notifications WHERE tenant_id = $1 "
        "AND kind = 'risk_partner_review_requested'",
        tb.tenant,
    )
    assert [r["recipient_user_id"] for r in told] == [tb.rita.user_id]
