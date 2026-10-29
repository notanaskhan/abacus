"""SPEC-027 AC-3, AC-4, AC-5, AC-8, AC-9 (TASK-051): due dates, overdue reminders, the team digest.

Against a real Postgres: the real overdue query, cadence history, contact lookup, draft and
settle writes; HTTP through `create_app()` for what people do. The email transport is a recorder,
so "nothing is sent" is a count of zero. Per DEC-74 (TASK-104) the agent only drafts, at every
autonomy level, and a person sends: AC-3's "at Routine its contacts get the email" reads that
way here, and is listed as a question. Expectations come from the spec.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import cast

import pytest

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.agents.engagement_agent import TICK, handle
from abacus.modules.agents.follow_up_drafts import on_follow_up_sent
from abacus.modules.agents.follow_ups import (
    MAX_PER_ITEM,
    Outcome,
    chase_overdue,
    draft_now,
    today_in,
)
from abacus.modules.agents.workflow_types import HandleInput
from abacus.modules.communications.transport import configure_transport

from .follow_up_template import import_reminder_template
from .support import Net, Person, Role, Seeder, Site

ZONE = "America/Chicago"
FORBIDDEN = {"detail": "forbidden"}


@dataclass
class Mailbox:
    sent: list[dict[str, str | None]] = field(default_factory=list[dict[str, str | None]])

    def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        sender_name: str | None = None,
        reply_to: str | None = None,
        tenant_id: uuid.UUID | None = None,
        message_id: uuid.UUID | None = None,
        from_address: str | None = None,
    ) -> None:
        # Q-01-T09: the transport protocol also carries the Reply-To and the IDs SES tags use.
        self.sent.append({"to": to, "subject": subject, "body": body, "sender_name": sender_name})


@pytest.fixture(autouse=True)
async def reminder_template(engines: None) -> None:
    """P-06-T14: the email is the published Reminder template (in the database, never code)."""
    await import_reminder_template()


@pytest.fixture(autouse=True)
def mailbox() -> Iterator[Mailbox]:
    box = Mailbox()
    configure_transport(box)
    yield box
    configure_transport(None)


@dataclass(frozen=True)
class Engagement:
    net: Net
    tenant_id: uuid.UUID
    site: Site
    admin: Person
    team: dict[str, Person]
    client_admins: tuple[Person, Person]
    contributor: Person

    @property
    def base(self) -> str:
        return f"/v1/engagements/{self.site.engagement_id}"

    @property
    def system(self) -> TenantContext:
        return TenantContext(self.tenant_id, "system", "agents.engagement_agent")

    def days_ago(self, days: int) -> date:
        return today_in(ZONE, system_now()) - timedelta(days=days)

    async def tick(self) -> Outcome:
        return await chase_overdue(self.system, self.site.engagement_id, ZONE, uuid.uuid4())

    async def follow_ups(
        self, status: str | None = None
    ) -> list[tuple[uuid.UUID, str, list[str]]]:
        """(recipient, status, item descriptions) of the engagement's reminders."""
        rows = await self.net.seed.rows(
            "SELECT r.recipient_user_id, r.status, array_agg(i.description ORDER BY i.description)"
            " AS items FROM follow_up_schedules r "
            "JOIN follow_up_items ri ON ri.follow_up_id = r.id "
            "JOIN request_items i ON i.id = ri.request_item_id WHERE r.engagement_id = $1 "
            "AND ($2::text IS NULL OR r.status = $2) GROUP BY r.id ORDER BY 1, 2",
            self.site.engagement_id,
            status,
        )
        return [(r["recipient_user_id"], str(r["status"]), list(r["items"])) for r in rows]


async def _engagement(net: Net, seed: Seeder, *, opened: bool = True) -> Engagement:
    tenant_id = await seed.firm()
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, "chase", opened=opened)
    team: dict[str, Person] = {}
    roles: tuple[Role, ...] = ("engagement_partner", "manager", "senior", "staff", "reviewer")
    for role in roles:
        team[role] = await seed.person(tenant_id)
        await seed.member(site, team[role], role)
    first, second = await seed.client_contact(site), await seed.client_contact(site)
    contributor = await seed.client_contact(site, "client_contributor")
    await seed.run("UPDATE firms SET time_zone = $2 WHERE tenant_id = $1", tenant_id, ZONE)
    # R-01-T24 review M-b: reminders name only requests in a Published binder (as BND-02's do).
    await seed.run(
        "UPDATE request_lists SET status = 'published', published_at = now() "
        "WHERE engagement_id = $1",
        site.engagement_id,
    )
    return Engagement(net, tenant_id, site, admin, team, (first, second), contributor)


@pytest.fixture
async def chase(net: Net, seed: Seeder) -> Engagement:
    return await _engagement(net, seed)


# --- AC-3: who is chased for what, and how often -------------------------------------------------


async def test_ac3_each_contact_gets_one_draft_listing_their_overdue_items(
    chase: Engagement, seed: Seeder, mailbox: Mailbox
) -> None:
    site = chase.site
    first = await seed.item(site, "Bank statement", due_on=chase.days_ago(10))
    second = await seed.item(site, "Debt schedule", status="returned", due_on=chase.days_ago(3))
    mine = await seed.item(
        site, "Payroll register", due_on=chase.days_ago(5), assignee=chase.contributor
    )
    not_due = await seed.item(
        site, "Lease", due_on=today_in(ZONE, system_now()) + timedelta(days=9)
    )
    assert {first, second, mine, not_due}
    # The seeded item (no due date) is not overdue; the four above: three overdue, one not due.
    outcome = await chase.tick()
    assert (outcome.overdue, outcome.drafted, outcome.sent) == (3, 3, 0)
    found = await chase.follow_ups()
    by_recipient = {recipient: items for recipient, _, items in found}
    admins = chase.client_admins
    assert by_recipient[admins[0].user_id] == ["Bank statement", "Debt schedule"]
    assert by_recipient[admins[1].user_id] == ["Bank statement", "Debt schedule"]
    assert by_recipient[chase.contributor.user_id] == ["Payroll register"]  # the assignee, alone
    assert {status for _, status, _ in found} == {"drafted"}
    assert mailbox.sent == []  # nothing goes out by itself


@pytest.mark.parametrize("status", ["uploaded", "received"])  # v2: ready_for_review -> uploaded
async def test_ac3_an_item_that_is_not_open_or_sent_back_is_never_chased(
    chase: Engagement, seed: Seeder, status: str
) -> None:
    await seed.item(chase.site, "Settled item", status=status, due_on=chase.days_ago(20))
    outcome = await chase.tick()
    assert outcome.overdue == 0
    assert await chase.follow_ups() == []


async def test_ac3_an_item_reminded_today_is_not_reminded_again_today(
    chase: Engagement, seed: Seeder
) -> None:
    await seed.item(chase.site, "Bank statement", due_on=chase.days_ago(4))
    first = await chase.tick()
    again = await chase.tick()
    assert first.drafted == 2
    assert (again.drafted, again.reason) == (0, "not_due")
    assert len(await chase.follow_ups()) == 2


async def test_ac3_an_item_is_chased_at_most_the_capped_number_of_times(
    chase: Engagement, seed: Seeder
) -> None:
    due = chase.days_ago(60)
    item = await seed.item(chase.site, "Bank statement", due_on=due)
    admin = chase.client_admins[0]
    for sequence in range(1, MAX_PER_ITEM + 1):  # sent long ago, a month apart
        follow_up_id = await seed.value(
            "INSERT INTO follow_up_schedules "
            "(tenant_id, engagement_id, recipient_user_id, status, "
            "created_at) VALUES ($1, $2, $3, 'sent', now() - make_interval(days => $4)) "
            "RETURNING id",
            chase.tenant_id,
            chase.site.engagement_id,
            admin.user_id,
            50 - sequence * 10,
        )
        await seed.run(
            "INSERT INTO follow_up_items (tenant_id, follow_up_id, request_item_id, due_on, "
            "sequence) VALUES ($1, $2, $3, $4, $5)",
            chase.tenant_id,
            follow_up_id,
            item,
            due,
            sequence,
        )
    outcome = await chase.tick()
    assert outcome.drafted == 0
    assert len(await chase.follow_ups()) == MAX_PER_ITEM  # no new draft beyond the three


async def test_ac3_a_changed_due_date_starts_the_sequence_again(
    chase: Engagement, seed: Seeder, net: Net
) -> None:
    item = await seed.item(chase.site, "Bank statement", due_on=chase.days_ago(4))
    assert (await chase.tick()).drafted == 2
    moved = await net.call(
        "PUT",
        f"{chase.base}/request-items/due-dates",
        chase.team["manager"],
        body={"item_ids": [str(item)], "due_on": chase.days_ago(2).isoformat()},
    )
    assert moved.status_code == 200, moved.text
    assert (await chase.tick()).drafted == 2


# --- AC-4: drafts, for a person to send, edit or dismiss -----------------------------------------


async def _drafted(chase: Engagement, seed: Seeder) -> uuid.UUID:
    await seed.item(chase.site, "Bank statement", due_on=chase.days_ago(6))
    await chase.tick()
    [(follow_up_id,)] = [
        (r["id"],)
        for r in await seed.rows(
            "SELECT id FROM follow_up_schedules "
            "WHERE engagement_id = $1 AND recipient_user_id = $2",
            chase.site.engagement_id,
            chase.client_admins[0].user_id,
        )
    ]
    return cast(uuid.UUID, follow_up_id)


@pytest.mark.parametrize("role", ["engagement_partner", "manager", "senior", "staff"])
async def test_ac4_the_team_sees_the_drafts_waiting_for_them(
    chase: Engagement, seed: Seeder, net: Net, role: str
) -> None:
    await _drafted(chase, seed)
    response = await net.call("GET", f"{chase.base}/follow-ups", chase.team[role])
    assert response.status_code == 200, response.text
    assert len(response.json()) == 2


# P-06-T14 (P-06 §4.4): staff may send follow-ups too.
@pytest.mark.parametrize("role", ["engagement_partner", "manager", "senior", "staff"])
async def test_ac4_a_person_sends_a_draft_with_their_note_and_it_goes_out_once(
    chase: Engagement, seed: Seeder, net: Net, mailbox: Mailbox, role: str
) -> None:
    follow_up_id = await _drafted(chase, seed)
    assert mailbox.sent == []
    sent = await net.call(
        "POST",
        f"{chase.base}/follow-ups/{follow_up_id}/send",
        chase.team[role],
        body={"note": "Could you send these by Friday?"},
    )
    assert sent.status_code == 200, sent.text
    # P-06-T14 review: the email is held for the 10-s Undo window, then delivered once.
    assert mailbox.sent == []
    held = await seed.rows(
        "SELECT not_before, grant_id FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'follow_up.sent'",
        chase.tenant_id,
    )
    assert len(held) == 1 and held[0]["grant_id"] is not None and held[0]["not_before"]
    await _deliver(seed, chase.tenant_id)
    [message] = mailbox.sent
    assert message["to"] == f"{await _subject(seed, chase.client_admins[0])}@example.test"
    assert "Bank statement" in str(message["body"])
    assert "Could you send these by Friday?" in str(message["body"])
    row = (
        await seed.rows(
            "SELECT status, decided_by, note FROM follow_up_schedules WHERE id = $1", follow_up_id
        )
    )[0]
    assert (row["status"], row["decided_by"], row["note"]) == (
        "sent",
        chase.team[role].user_id,
        "Could you send these by Friday?",
    )
    assert {"follow_up.sent", "message.sent"} <= set(await seed.actions(chase.tenant_id))
    again = await net.call(
        "POST", f"{chase.base}/follow-ups/{follow_up_id}/send", chase.team[role], body={}
    )
    assert again.status_code == 409  # it is settled: it cannot go out twice
    assert len(mailbox.sent) == 1


async def _deliver(seed: Seeder, tenant_id: uuid.UUID) -> None:
    """What the relay does once each held send's grant is consumed after the Undo window: the
    subscriber sends the frozen email (the grant gate is `test_follow_ups_v2.py`'s)."""
    for row in await seed.rows(
        "SELECT id, payload FROM outbox WHERE tenant_id = $1 AND event_type = 'follow_up.sent' "
        "ORDER BY seq",
        tenant_id,
    ):
        payload = row["payload"]
        loaded = json.loads(payload) if isinstance(payload, str) else payload
        await on_follow_up_sent(OutboxEvent(row["id"], tenant_id, "follow_up.sent", loaded))


async def _subject(seed: Seeder, who: Person) -> str:
    return str(await seed.value("SELECT idp_subject FROM users WHERE id = $1", who.user_id))


async def test_ac4_the_preview_is_the_email_that_goes_out(
    chase: Engagement, seed: Seeder, net: Net, mailbox: Mailbox
) -> None:
    follow_up_id = await _drafted(chase, seed)
    preview = await net.call(
        "POST",
        f"{chase.base}/follow-ups/{follow_up_id}/preview",
        chase.team["manager"],
        body={"note": "Thanks."},
    )
    assert preview.status_code == 200, preview.text
    await net.call(
        "POST",
        f"{chase.base}/follow-ups/{follow_up_id}/send",
        chase.team["manager"],
        body={"note": "Thanks."},
    )
    await _deliver(seed, chase.tenant_id)
    [message] = mailbox.sent
    assert (message["subject"], message["body"]) == (
        preview.json()["subject"],
        preview.json()["body"],
    )


async def test_ac4_a_person_dismisses_a_draft_and_nothing_is_sent(
    chase: Engagement, seed: Seeder, net: Net, mailbox: Mailbox
) -> None:
    follow_up_id = await _drafted(chase, seed)
    dismissed = await net.call(
        "POST", f"{chase.base}/follow-ups/{follow_up_id}/dismiss", chase.team["manager"]
    )
    assert dismissed.status_code == 200, dismissed.text
    assert mailbox.sent == []
    assert (
        await seed.value("SELECT status FROM follow_up_schedules WHERE id = $1", follow_up_id)
        == "dismissed"
    )
    assert "follow_up.dismissed" in await seed.actions(chase.tenant_id)
    # While the other contact's draft waits, the item has been reminded once; dismiss it too and
    # a dismissed draft leaves the sequence where it was: the next tick drafts both again.
    other = await seed.value(
        "SELECT id FROM follow_up_schedules WHERE engagement_id = $1 AND status = 'drafted'",
        chase.site.engagement_id,
    )
    await net.call("POST", f"{chase.base}/follow-ups/{other}/dismiss", chase.team["manager"])
    assert (await chase.tick()).drafted == 2


async def test_ac4_when_nothing_in_a_draft_is_overdue_any_more_sending_dismisses_it(
    chase: Engagement, seed: Seeder, net: Net, mailbox: Mailbox
) -> None:
    follow_up_id = await _drafted(chase, seed)
    await seed.run(
        "UPDATE request_items SET status = 'received' WHERE engagement_id = $1 "
        "AND description = 'Bank statement'",
        chase.site.engagement_id,
    )
    sent = await net.call(
        "POST", f"{chase.base}/follow-ups/{follow_up_id}/send", chase.team["manager"], body={}
    )
    assert sent.status_code == 200, sent.text
    assert mailbox.sent == []
    assert (
        await seed.value("SELECT status FROM follow_up_schedules WHERE id = $1", follow_up_id)
        == "dismissed"
    )


# P-06-T14 (P-06 §4.4) added staff to the senders; the reviewer still may not.
@pytest.mark.parametrize("role", ["reviewer"])
async def test_ac4_a_reviewer_may_not_send_or_dismiss(
    chase: Engagement, seed: Seeder, net: Net, mailbox: Mailbox, role: str
) -> None:
    follow_up_id = await _drafted(chase, seed)
    for action in ("send", "dismiss"):
        response = await net.call(
            "POST", f"{chase.base}/follow-ups/{follow_up_id}/{action}", chase.team[role], body={}
        )
        assert response.status_code == 403, response.text
        assert response.json() == FORBIDDEN
    assert mailbox.sent == []
    assert (
        await seed.value("SELECT status FROM follow_up_schedules WHERE id = $1", follow_up_id)
        == "drafted"
    )


async def test_ac4_a_person_can_ask_for_follow_ups_now_and_they_are_drafts_too(
    chase: Engagement, seed: Seeder, net: Net, mailbox: Mailbox
) -> None:
    await seed.item(chase.site, "Bank statement", due_on=chase.days_ago(1))
    asked = await net.call("POST", f"{chase.base}/follow-ups/draft", chase.team["senior"])
    assert asked.status_code == 201, asked.text
    assert asked.json() == {"drafted": 2}
    again = await net.call("POST", f"{chase.base}/follow-ups/draft", chase.team["senior"])
    assert again.json() == {"drafted": 0}  # already waiting for a person
    assert mailbox.sent == []


# --- AC-5: nothing client-facing unless the engagement is open and live --------------------------


async def test_ac5_before_the_engagement_opens_nothing_is_drafted_but_the_team_hears(
    net: Net, seed: Seeder, mailbox: Mailbox
) -> None:
    closed = await _engagement(net, seed, opened=False)
    await seed.item(closed.site, "Bank statement", due_on=closed.days_ago(8))
    outcome = await closed.tick()
    assert (outcome.drafted, outcome.sent, outcome.reason) == (0, 0, "not_open")
    assert await closed.follow_ups() == []
    assert mailbox.sent == []
    assert "agent.digest" in await seed.actions(closed.tenant_id)  # the in-app digest still goes
    refused = await net.call("POST", f"{closed.base}/follow-ups/draft", closed.team["manager"])
    assert refused.status_code == 409
    # F-03-T13: the code, and which gate is unmet (identifier-only facts, ADR-139).
    assert refused.json() == {"detail": "acceptance_missing", "facts": {"gate": "G1"}}


async def test_ac5_an_archived_engagement_neither_drafts_nor_sends(
    chase: Engagement, seed: Seeder, net: Net, mailbox: Mailbox
) -> None:
    follow_up_id = await _drafted(chase, seed)
    await seed.run(
        "UPDATE engagements SET status = 'archived' WHERE id = $1", chase.site.engagement_id
    )
    attempts: tuple[tuple[str, dict[str, str] | None], ...] = (
        (f"/follow-ups/{follow_up_id}/send", {}),
        (f"/follow-ups/{follow_up_id}/dismiss", None),
        ("/follow-ups/draft", None),
    )
    for path, body in attempts:
        response = await net.call("POST", chase.base + path, chase.team["manager"], body=body)
        assert response.status_code == 403, (path, response.text)
    assert mailbox.sent == []
    assert (
        await seed.value("SELECT status FROM follow_up_schedules WHERE id = $1", follow_up_id)
        == "drafted"
    )
    # and the agent's daily tick ends rather than acting
    ended = await handle(
        HandleInput(
            str(chase.tenant_id), str(chase.site.engagement_id), TICK, str(uuid.uuid4()), {}
        )
    )
    assert ended.end is True


# --- AC-5 / P-5: the digest ----------------------------------------------------------------------


async def test_p5_the_team_digest_is_one_event_per_tick_with_the_counts(
    chase: Engagement, seed: Seeder
) -> None:
    await seed.item(chase.site, "Bank statement", due_on=chase.days_ago(8))
    await chase.tick()
    rows = await seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = 'agent.digest'",
        chase.tenant_id,
    )
    assert len(rows) == 1
    assert '"overdue": 1' in str(rows[0]["payload"]) or '"overdue":1' in str(rows[0]["payload"])
    quiet = await _engagement(chase.net, seed)
    await quiet.tick()  # nothing overdue: no digest, no noise
    assert "agent.digest" not in await seed.actions(quiet.tenant_id)


# --- AC-8: the agent acts for its initiator, or pauses -------------------------------------------


async def _tick_event(chase: Engagement) -> list[tuple[str, str, str | None]]:
    await handle(
        HandleInput(
            str(chase.tenant_id), str(chase.site.engagement_id), TICK, str(uuid.uuid4()), {}
        )
    )
    rows = await chase.net.seed.rows(
        "SELECT action, outcome, reason FROM agent_activity WHERE engagement_id = $1 "
        "ORDER BY created_at",
        chase.site.engagement_id,
    )
    return [(str(r["action"]), str(r["outcome"]), r["reason"]) for r in rows]


async def test_ac8_with_no_active_partner_the_agent_pauses_itself_and_resumes_with_one(
    chase: Engagement, seed: Seeder
) -> None:
    await seed.item(chase.site, "Bank statement", due_on=chase.days_ago(8))
    await seed.run(
        "DELETE FROM engagement_members WHERE engagement_id = $1 AND role = 'engagement_partner'",
        chase.site.engagement_id,
    )
    feed = await _tick_event(chase)
    assert ("agent.self_paused", "done", "no_partner") in feed
    assert ("agent.tick", "skipped", "self_paused") in feed
    assert await chase.follow_ups() == []  # no policy acted
    assert "engagement_agent.self_paused" in await seed.actions(chase.tenant_id)
    partner = await seed.person(chase.tenant_id)
    await seed.member(chase.site, partner, "engagement_partner")
    after = await _tick_event(chase)
    assert ("agent.self_resumed", "done", None) in after
    assert len(await chase.follow_ups()) == 2  # and it works again
    assert "engagement_agent.self_resumed" in await seed.actions(chase.tenant_id)


# --- P-06-T14 security review: the engagement route has follow-ups v2's controls ---


async def test_review3_a_note_naming_another_client_is_refused_and_nothing_is_held(
    chase: Engagement, seed: Seeder, net: Net, mailbox: Mailbox
) -> None:
    follow_up_id = await _drafted(chase, seed)
    other = await seed.value(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Granite Peak Holdings') RETURNING id",
        chase.tenant_id,
    )
    assert other is not None
    refused = await net.call(
        "POST",
        f"{chase.base}/follow-ups/{follow_up_id}/send",
        chase.team["manager"],
        body={"note": "Granite Peak Holdings sent theirs already."},
    )
    assert refused.status_code == 409 and refused.json()["detail"] == "out_of_scope"
    assert (
        await seed.value("SELECT status FROM follow_up_schedules WHERE id = $1", follow_up_id)
        == "drafted"
    )
    held = await seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'follow_up.sent'",
        chase.tenant_id,
    )
    assert held == 0 and mailbox.sent == []


async def test_review3_a_binder_draft_is_refused_on_the_engagement_route(
    chase: Engagement, seed: Seeder, net: Net, mailbox: Mailbox
) -> None:
    follow_up_id = await _drafted(chase, seed)
    await seed.run("UPDATE follow_up_schedules SET kind = 'chase' WHERE id = $1", follow_up_id)
    for action in ("send", "dismiss"):
        refused = await net.call(
            "POST",
            f"{chase.base}/follow-ups/{follow_up_id}/{action}",
            chase.team["manager"],
            body={},
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["detail"] == "follow_up_v2_only"
    assert mailbox.sent == []


# --- R-01-T24 security review M-b: only what a client may be written to about ------------------


async def test_mb_internal_requests_and_unpublished_binders_are_never_drafted_or_sent(
    chase: Engagement, seed: Seeder, mailbox: Mailbox
) -> None:
    visible = await seed.item(chase.site, "Bank statement", due_on=chase.days_ago(10))
    internal = await seed.item(chase.site, "Internal memo", due_on=chase.days_ago(10))
    await seed.run("UPDATE request_items SET client_visible = false WHERE id = $1", internal)
    assert visible
    outcome = await chase.tick()  # the legacy plan (no policy marker)
    assert outcome.drafted == 2  # one per client admin, naming the visible request only
    assert {tuple(items) for _, _, items in await chase.follow_ups()} == {("Bank statement",)}
    # A person asking for drafts now, and the drafts a person sends, leave it out too.
    await seed.run(
        "UPDATE follow_up_schedules SET status = 'dismissed' WHERE engagement_id = $1",
        chase.site.engagement_id,
    )
    assert await draft_now(chase.system, chase.site.engagement_id, ZONE) == 2
    assert {tuple(items) for _, s, items in await chase.follow_ups() if s == "drafted"} == {
        ("Bank statement",)
    }
    for status in ("unpublished", "closed", "draft"):
        await seed.run(
            "UPDATE request_lists SET status = $2 WHERE engagement_id = $1",
            chase.site.engagement_id,
            status,
        )
        assert await draft_now(chase.system, chase.site.engagement_id, ZONE) == 0
    assert mailbox.sent == []
