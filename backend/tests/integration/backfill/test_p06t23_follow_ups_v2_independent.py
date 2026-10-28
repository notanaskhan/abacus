# ac-test-author: ayushkbhatia
"""SPEC-319 AC-16 to AC-20 (P-06-T14, TASK-1006) and the screening return (TASK-1252): follow-ups
v2, independent suite for P-06-T23 (TASK-1280).

What the ACs promise: drafting over binders or requests writes one follow-up per client contact
per engagement from the published Reminder template, listing each open client-visible request
once and never one already waiting in a draft to that contact, and sends nothing (AC-16); a
person's edit is sealed and fingerprinted and a sent follow-up can't be edited (AC-17); send is
scope-checked with nothing written on a refusal, held by an approval grant for the 10-s Undo
window, leaves once, Undo inside sends nothing and later answers 409, and the trail and the
message name the person (AC-18, INV-5); no code path lets the agent principal send (AC-19,
INV-1); partners, managers, seniors, staff and `client_service` draft and send, reviewers do
not (AC-20). Walls and other firms answer 404 (INV-3, DEC-43). The screening return (DEC-368)
sends back the files and returns the request with the send, posts the shared comment with the
email after the window, and its Undo puts everything back.

Boundary: `create_app()` over HTTP on the migrated Postgres (`net`, `seed`); business time frozen
on a synthetic firm; the outbox relayed with the kernel relay and `follow_up.sent` handed to the
agents module's own subscriber (`agents.api.SUBSCRIPTIONS`), as the worker does; the email
caught by the communications fake transport. Later decisions followed: DEC-220 (recipients,
template-composed drafts are `drafted_by_kind = agent`, the edit check, the open `system` actor
gap), DEC-368 (the comment and email at delivery, not at send; bulk send refuses a return).
The P-4 tick's draft-only path and the agent's `follow_up.send` refusal through its own task
scope are Q-03-T031's (`backfill/test_q03t031_engagement_agent.py`) and are not repeated here.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final, cast

import httpx
import pytest
from sqlalchemy.exc import DBAPIError

from abacus.kernel.clock import frozen
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import Target, uow
from abacus.kernel.uow.relay import InMemoryPublisher, relay_once
from abacus.modules.agents import api as agents_api
from abacus.modules.communications.api import FakeSesTransport, configure_transport
from abacus.modules.identity.authz.matrix import RULES

from .follow_up_template import import_reminder_template, import_return_template
from .support import Json, Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio

T0: Final = datetime.fromisoformat("2026-09-14T09:42:00-05:00")
DUE: Final = date(2026, 10, 1)


@pytest.fixture(autouse=True)
def mailbox(engines: None, tmp_path: Path) -> Iterator[Path]:
    """A mailbox per test, fresh flag values."""
    settings.cache_clear()
    forget_flags()
    box = tmp_path / "mailbox"
    configure_transport(FakeSesTransport(box))
    yield box
    configure_transport(None)
    forget_flags()


def _mails(box: Path) -> list[Path]:
    return [p for p in box.rglob("*") if p.is_file()] if box.exists() else []


@dataclass
class Firm:
    net: Net
    tenant_id: uuid.UUID
    admin: Person
    partner: Person
    manager: Person
    senior: Person
    staff: Person
    reviewer: Person
    client_service: Person
    site: Site
    other_client_name: str
    binder: uuid.UUID
    ada: Person  # a client admin of the engagement
    ben: Person  # another client admin of the engagement

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    async def call(
        self,
        who: Person,
        method: str,
        path: str,
        body: Json | None = None,
        *,
        at: datetime = T0,
        key: str | None = None,
    ) -> httpx.Response:
        headers = {**self.net.headers(who), "Idempotency-Key": key or uuid.uuid4().hex}
        with frozen(at):
            return await self.net.http.request(method, path, json=body, headers=headers)

    async def request(
        self,
        title: str,
        *,
        status: str = "requested",
        visible: bool = True,
        assignee: Person | None = None,
        binder: uuid.UUID | None = None,
    ) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO request_items (tenant_id, engagement_id, request_list_id, "
                "description, audit_area, created_by, client_visible, due_on, status, "
                "client_assignee_user_id) VALUES ($1, $2, $3, $4, 'Income', $5, $6, $7, $8, $9) "
                "RETURNING id",
                self.tenant_id,
                self.site.engagement_id,
                binder or self.binder,
                title,
                self.manager.user_id,
                visible,
                DUE,
                status,
                assignee.user_id if assignee else None,
            ),
        )

    async def draft(
        self, who: Person, body: Json, *, at: datetime = T0
    ) -> tuple[httpx.Response, list[Json]]:
        response = await self.call(who, "POST", "/v1/follow-ups/drafts", body, at=at)
        items = (
            cast(list[Json], cast(Json, response.json())["items"])
            if response.status_code == 201
            else []
        )
        return response, items

    async def draft_binder(self, who: Person | None = None) -> list[Json]:
        response, items = await self.draft(who or self.manager, {"binder_ids": [str(self.binder)]})
        assert response.status_code == 201, response.text
        return items

    async def count(self, sql: str, *args: object) -> int:
        return int(cast(int, await self.seed.value(sql, *args)))

    async def audits(self, action: str) -> list[tuple[str, str]]:
        rows = await self.seed.rows(
            "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 AND action = $2 "
            "ORDER BY seq",
            self.tenant_id,
            action,
        )
        return [(str(r["actor_kind"]), str(r["actor_id"])) for r in rows]

    async def outbox(self, event_type: str) -> int:
        return await self.count(
            "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = $2",
            self.tenant_id,
            event_type,
        )

    async def emails(self) -> list[tuple[uuid.UUID, uuid.UUID, str]]:
        rows = await self.seed.rows(
            "SELECT id, created_by, status FROM messages WHERE tenant_id = $1 "
            "AND channel = 'email' ORDER BY created_at",
            self.tenant_id,
        )
        return [(r["id"], r["created_by"], str(r["status"])) for r in rows]

    async def deliver(self, at: datetime) -> int:
        """One relay pass at `at`, `follow_up.sent` handed to the agents module's subscriber, as
        the worker does. Returns the follow-up events this firm had delivered."""
        # A pass inside the window leaves the held event to retry after a wall-clock backoff,
        # which the frozen business clock doesn't move: a later pass sees it again at once.
        await self.seed.run(
            "UPDATE outbox SET next_attempt_at = NULL WHERE tenant_id = $1 "
            "AND published_at IS NULL",
            self.tenant_id,
        )
        publisher = InMemoryPublisher()
        with frozen(at):
            # Until a pass claims nothing: the relay takes the worker database's oldest due
            # events first, and earlier tests' leftovers can fill a fixed number of passes. A held
            # event backs off on wall-clock time, so it is claimed once per call.
            for _ in range(200):
                result = await relay_once(publisher)
                if result.published + result.failed + result.deferred == 0:
                    break
        mine = [
            e
            for e in publisher.published
            if e.tenant_id == self.tenant_id and e.event_type == "follow_up.sent"
        ]
        for event in mine:
            with frozen(at):
                await agents_api.SUBSCRIPTIONS["follow_up.sent"](event)
        return len(mine)


async def _client_admin(seed: Seeder, site: Site, name: str) -> Person:
    who = await seed.client_contact(site)
    await seed.run("UPDATE users SET display_name = $2 WHERE id = $1", who.user_id, name)
    return who


async def _firm(net: Net, *, screening: bool = False) -> Firm:
    seed = net.seed
    tenant_id = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant_id)
    for flag in ("binders.engine", *(("screening.card",) if screening else ())):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'P-06-T23')",
            tenant_id,
            flag,
        )
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, "Feld")
    other = await seed.site(tenant_id, admin.user_id, "Harbor")
    team: dict[str, Person] = {}
    for role in ("engagement_partner", "manager", "senior", "staff", "reviewer"):
        team[role] = await seed.person(tenant_id)
        await seed.member(site, team[role], role)
    service = await seed.person(tenant_id)
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'client_service')",
        tenant_id,
        site.engagement_id,
        service.user_id,
    )
    await seed.run(
        "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status, "
        "statement_version, answered_at) VALUES ($1, $2, $3, 'confirmed', 'v1', "
        "clock_timestamp()) ON CONFLICT DO NOTHING",
        tenant_id,
        site.engagement_id,
        service.user_id,
    )
    ada = await _client_admin(seed, site, "Ada Feld")
    ben = await _client_admin(seed, site, "Ben Feld")
    await import_reminder_template()
    await import_return_template()
    work_item = await seed.value(
        "SELECT id FROM work_items WHERE engagement_id = $1", site.engagement_id
    )
    firm = Firm(
        net,
        tenant_id,
        admin,
        team["engagement_partner"],
        team["manager"],
        team["senior"],
        team["staff"],
        team["reviewer"],
        service,
        site,
        f"Client {other.marker}",
        uuid.uuid4(),
        ada,
        ben,
    )
    made = await firm.call(
        team["manager"],
        "POST",
        "/v1/binders",
        {"work_item_id": str(work_item), "kind": "intake", "name": "2025 Binder"},
        at=T0 - timedelta(hours=1),
    )
    assert made.status_code == 201, made.text
    firm.binder = uuid.UUID(cast(str, made.json()["id"]))
    return firm


async def _publish(firm: Firm, binder: uuid.UUID | None = None) -> None:
    published = await firm.call(
        firm.manager,
        "POST",
        f"/v1/binders/{binder or firm.binder}/publish",
        at=T0 - timedelta(minutes=30),
    )
    assert published.status_code == 200, published.text


@pytest.fixture
async def firm(net: Net) -> Firm:
    f = await _firm(net)
    await f.request("Brokerage statements")
    await f.request("Property tax bills")
    await _publish(f)
    return f


def _titles(follow_up: Json) -> list[str]:
    return [str(i["title"]) for i in cast(list[Json], follow_up["items"])]


def _by_recipient(items: list[Json]) -> dict[str, Json]:
    return {str(i["recipient_user_id"]): i for i in items}


# --- AC-16: composition -----------------------------------------------------------------------


async def test_ac16_one_draft_per_client_contact_listing_each_open_request_once(
    firm: Firm,
) -> None:
    items = await firm.draft_binder()
    drafts = _by_recipient(items)
    assert set(drafts) == {str(firm.ada.user_id), str(firm.ben.user_id)}
    for draft in drafts.values():
        assert sorted(_titles(draft)) == ["Brokerage statements", "Property tax bills"]
        assert draft["status"] == "drafted"
        assert draft["engagement_id"] == str(firm.site.engagement_id)
        assert draft["binder_id"] == str(firm.binder)
        assert draft["kind"] == "chase"
        assert draft["template_key"] == "notification.follow_up_sent"
        assert draft["sent_by"] is None and draft["sent_at"] is None
    assert {d["recipient_name"] for d in drafts.values()} == {"Ada Feld", "Ben Feld"}


async def test_ac16_drafting_sends_nothing(firm: Firm, mailbox: Path) -> None:
    await firm.draft_binder()
    assert await firm.outbox("follow_up.sent") == 0
    assert await firm.audits("follow_up.sent") == []
    assert len(await firm.audits("follow_up.drafted")) >= 1
    assert await firm.deliver(T0 + timedelta(minutes=5)) == 0
    assert await firm.emails() == [] and _mails(mailbox) == []


async def test_ac16_the_body_is_the_published_template_from_the_database(firm: Firm) -> None:
    """The subject and body follow the imported Reminder template's wording (test data,
    `follow_up_template.py`), with the request list one per line; no wording comes from code."""
    draft = (await firm.draft_binder())[0]
    firm_name = await firm.seed.value(
        "SELECT name FROM firms WHERE tenant_id = $1", firm.tenant_id
    )
    assert str(draft["subject"]).startswith(f"{firm_name} is still waiting on ")
    body = str(draft["body"])
    assert body.startswith("Hi ")
    assert f"{firm_name} is still waiting for the following:" in body
    assert "Brokerage statements" in body and "Property tax bills" in body
    assert "Open your list: " in body
    assert draft["edited"] is False


async def test_ac16_a_request_already_waiting_in_a_draft_to_that_contact_is_never_repeated(
    firm: Firm,
) -> None:
    await firm.draft_binder()
    third = await firm.request("Charitable receipts")
    response, _ = await firm.draft(firm.manager, {"request_item_ids": [str(third)]})
    assert response.status_code == 201, response.text
    await firm.draft_binder()  # the whole binder again
    for who in (firm.ada, firm.ben):
        waiting = await firm.seed.rows(
            "SELECT fi.request_item_id FROM follow_up_items fi JOIN follow_up_schedules fs "
            "ON fs.id = fi.follow_up_id AND fs.tenant_id = fi.tenant_id "
            "WHERE fs.tenant_id = $1 AND fs.recipient_user_id = $2 AND fs.status = 'drafted'",
            firm.tenant_id,
            who.user_id,
        )
        ids = [r["request_item_id"] for r in waiting]
        assert len(ids) == len(set(ids)) == 3, who
        drafts = await firm.count(
            "SELECT count(*) FROM follow_up_schedules WHERE tenant_id = $1 "
            "AND recipient_user_id = $2 AND status = 'drafted'",
            firm.tenant_id,
            who.user_id,
        )
        assert drafts == 1, who  # one waiting draft per contact per engagement


async def test_ac16_only_open_client_visible_requests_are_listed(firm: Firm) -> None:
    await firm.request("Internal tickmark note", visible=False)
    await firm.request("Already received", status="received")
    for draft in await firm.draft_binder():
        assert sorted(_titles(draft)) == ["Brokerage statements", "Property tax bills"]


async def test_ac16_a_request_with_a_client_assignee_goes_to_that_contact_only(
    firm: Firm,
) -> None:
    await firm.request("W-2 for Ada", assignee=firm.ada)
    drafts = _by_recipient(await firm.draft_binder())
    assert "W-2 for Ada" in _titles(drafts[str(firm.ada.user_id)])
    assert "W-2 for Ada" not in _titles(drafts[str(firm.ben.user_id)])


async def test_ac16_an_unpublished_binder_is_not_chased(net: Net) -> None:
    f = await _firm(net)
    await f.request("Brokerage statements")
    response, items = await f.draft(f.manager, {"binder_ids": [str(f.binder)]})
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "binder_not_published"
    assert items == []
    assert (
        await f.count("SELECT count(*) FROM follow_up_schedules WHERE tenant_id = $1", f.tenant_id)
        == 0
    )


# --- AC-17: the person's edit -----------------------------------------------------------------


async def test_ac17_an_edit_is_sealed_and_fingerprinted(firm: Firm) -> None:
    draft = (await firm.draft_binder())[0]
    text = "Hi Ada,\n\nCould you send the two statements this week?\n\nThanks"
    edited = await firm.call(
        firm.manager, "PATCH", f"/v1/follow-ups/{draft['id']}", {"body": text}
    )
    assert edited.status_code == 200, edited.text
    out = cast(Json, edited.json())
    assert out["body"] == text and out["edited"] is True
    row = (
        await firm.seed.rows(
            "SELECT body_sealed, edit_fingerprint, body_fingerprint FROM follow_up_schedules "
            "WHERE tenant_id = $1 AND id = $2",
            firm.tenant_id,
            uuid.UUID(str(draft["id"])),
        )
    )[0]
    assert row["body_sealed"] is not None
    assert text.encode() not in bytes(row["body_sealed"])  # sealed, not stored in the clear
    assert row["edit_fingerprint"] == hashlib.sha256(text.encode()).hexdigest()
    assert (
        row["body_fingerprint"] is not None and row["body_fingerprint"] != row["edit_fingerprint"]
    )
    assert len(await firm.audits("follow_up.edited")) == 1
    read = await firm.call(firm.manager, "GET", f"/v1/follow-ups/{draft['id']}")
    assert read.status_code == 200 and read.json()["body"] == text


async def test_ac17_a_sent_follow_up_cannot_be_edited(firm: Firm) -> None:
    draft = (await firm.draft_binder())[0]
    sent = await firm.call(firm.manager, "POST", f"/v1/follow-ups/{draft['id']}/send")
    assert sent.status_code == 200, sent.text
    refused = await firm.call(
        firm.manager,
        "PATCH",
        f"/v1/follow-ups/{draft['id']}",
        {"body": "Changed after sending"},
        at=T0 + timedelta(seconds=30),
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"] == "follow_up_already_sent"
    again = await firm.call(
        firm.manager, "POST", f"/v1/follow-ups/{draft['id']}/send", at=T0 + timedelta(seconds=31)
    )
    assert again.status_code == 409 and again.json()["detail"] == "follow_up_already_sent"


# --- AC-18: scope check, grant-held send, Undo, INV-5 -----------------------------------------


async def test_ac18_an_out_of_scope_title_refuses_the_send_and_writes_nothing(
    firm: Firm, mailbox: Path
) -> None:
    draft = (await firm.draft_binder())[0]
    # A title edited after drafting now names another client of the firm.
    await firm.seed.run(
        "UPDATE request_items SET description = $3 WHERE tenant_id = $1 AND engagement_id = $2 "
        "AND description = 'Brokerage statements'",
        firm.tenant_id,
        firm.site.engagement_id,
        f"Brokerage statements as {firm.other_client_name} sent",
    )
    response = await firm.call(firm.manager, "POST", f"/v1/follow-ups/{draft['id']}/send")
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "out_of_scope"
    assert firm.other_client_name not in response.text
    status = await firm.seed.value(
        "SELECT status FROM follow_up_schedules WHERE id = $1", uuid.UUID(str(draft["id"]))
    )
    assert status == "drafted"
    assert await firm.audits("follow_up.sent") == []
    assert await firm.outbox("follow_up.sent") == 0
    assert await firm.deliver(T0 + timedelta(seconds=30)) == 0
    assert _mails(mailbox) == []


async def test_ac18_an_out_of_scope_edit_never_leaves(firm: Firm, mailbox: Path) -> None:
    """DEC-220: the person's added text is checked at the edit and again at the send; either
    refusal is 409 `out_of_scope` and nothing is sent."""
    draft = (await firm.draft_binder())[0]
    edited = await firm.call(
        firm.manager,
        "PATCH",
        f"/v1/follow-ups/{draft['id']}",
        {"body": f"Hi, also send what {firm.other_client_name} gave us."},
    )
    if edited.status_code == 409:
        assert edited.json()["detail"] == "out_of_scope"
    else:
        assert edited.status_code == 200, edited.text
        sent = await firm.call(firm.manager, "POST", f"/v1/follow-ups/{draft['id']}/send")
        assert sent.status_code == 409, sent.text
        assert sent.json()["detail"] == "out_of_scope"
    assert await firm.audits("follow_up.sent") == []
    assert await firm.outbox("follow_up.sent") == 0
    assert await firm.deliver(T0 + timedelta(seconds=30)) == 0
    assert _mails(mailbox) == []


async def test_ac18_the_send_is_held_for_the_undo_window_and_leaves_once(
    firm: Firm, mailbox: Path
) -> None:
    draft = (await firm.draft_binder())[0]
    key = uuid.uuid4().hex
    sent = await firm.call(firm.staff, "POST", f"/v1/follow-ups/{draft['id']}/send", key=key)
    assert sent.status_code == 200, sent.text
    out = cast(Json, sent.json())
    assert out["status"] == "sent" and out["sent_by"] == str(firm.staff.user_id)
    assert out["undo_until"] is not None
    assert datetime.fromisoformat(str(out["undo_until"])) - datetime.fromisoformat(
        str(out["sent_at"])
    ) == timedelta(seconds=10)
    retry = await firm.call(
        firm.staff, "POST", f"/v1/follow-ups/{draft['id']}/send", key=key, at=T0.replace(second=44)
    )
    assert (retry.status_code, retry.json()) == (sent.status_code, sent.json())
    # Inside the window nothing leaves.
    assert await firm.deliver(T0 + timedelta(seconds=5)) == 0
    assert await firm.emails() == [] and _mails(mailbox) == []
    # After it, the email leaves once, even relayed again.
    assert await firm.deliver(T0 + timedelta(seconds=11)) == 1
    await firm.deliver(T0 + timedelta(seconds=20))
    emails = await firm.emails()
    assert len(emails) == 1
    assert emails[0][1] == firm.staff.user_id and emails[0][2] == "sent"  # INV-5
    assert len(_mails(mailbox)) == 1


async def test_ac18_inv5_the_trail_names_the_person_who_sent(firm: Firm) -> None:
    draft = (await firm.draft_binder())[0]
    sent = await firm.call(firm.senior, "POST", f"/v1/follow-ups/{draft['id']}/send")
    assert sent.status_code == 200, sent.text
    assert await firm.audits("follow_up.sent") == [("human", str(firm.senior.user_id))]
    sent_by = await firm.seed.value(
        "SELECT sent_by FROM follow_up_schedules WHERE id = $1", uuid.UUID(str(draft["id"]))
    )
    assert sent_by == firm.senior.user_id


async def test_ac18_undo_within_ten_seconds_sends_nothing(firm: Firm, mailbox: Path) -> None:
    draft = (await firm.draft_binder())[0]
    sent = await firm.call(firm.manager, "POST", f"/v1/follow-ups/{draft['id']}/send")
    assert sent.status_code == 200, sent.text
    undone = await firm.call(
        firm.manager, "POST", f"/v1/follow-ups/{draft['id']}/undo", at=T0 + timedelta(seconds=9)
    )
    assert undone.status_code == 200, undone.text
    assert undone.json()["status"] == "drafted"
    assert len(await firm.audits("follow_up.undone")) == 1
    assert await firm.deliver(T0 + timedelta(seconds=30)) == 0
    assert await firm.emails() == [] and _mails(mailbox) == []


async def test_ac18_undo_after_the_window_is_refused_and_the_email_leaves(
    firm: Firm, mailbox: Path
) -> None:
    draft = (await firm.draft_binder())[0]
    sent = await firm.call(firm.manager, "POST", f"/v1/follow-ups/{draft['id']}/send")
    assert sent.status_code == 200, sent.text
    late = await firm.call(
        firm.manager, "POST", f"/v1/follow-ups/{draft['id']}/undo", at=T0 + timedelta(seconds=10)
    )
    assert late.status_code == 409, late.text
    assert late.json()["detail"] in ("undo_window_closed", "effect_started")
    assert await firm.deliver(T0 + timedelta(seconds=11)) == 1
    after = await firm.call(
        firm.manager, "POST", f"/v1/follow-ups/{draft['id']}/undo", at=T0 + timedelta(seconds=12)
    )
    assert after.status_code == 409, after.text
    assert after.json()["detail"] in ("undo_window_closed", "effect_started")
    assert len(await firm.emails()) == 1


async def test_ac18_only_the_sender_may_undo(firm: Firm) -> None:
    draft = (await firm.draft_binder())[0]
    sent = await firm.call(firm.manager, "POST", f"/v1/follow-ups/{draft['id']}/send")
    assert sent.status_code == 200, sent.text
    other = await firm.call(
        firm.partner, "POST", f"/v1/follow-ups/{draft['id']}/undo", at=T0 + timedelta(seconds=3)
    )
    assert other.status_code in (403, 409), other.text
    status = await firm.seed.value(
        "SELECT status FROM follow_up_schedules WHERE id = $1", uuid.UUID(str(draft["id"]))
    )
    assert status == "sent"


async def test_ac18_send_several_holds_one_email_per_follow_up(firm: Firm) -> None:
    ids = [str(d["id"]) for d in await firm.draft_binder()]
    sent = await firm.call(firm.manager, "POST", "/v1/follow-ups/send", {"ids": ids})
    assert sent.status_code == 200, sent.text
    assert await firm.deliver(T0 + timedelta(seconds=11)) == 2
    emails = await firm.emails()
    assert len(emails) == 2 and {e[1] for e in emails} == {firm.manager.user_id}


async def test_ac18_a_dismissed_draft_is_never_sent(firm: Firm) -> None:
    draft = (await firm.draft_binder())[0]
    dismissed = await firm.call(firm.manager, "POST", f"/v1/follow-ups/{draft['id']}/dismiss")
    assert dismissed.status_code == 200, dismissed.text
    refused = await firm.call(firm.manager, "POST", f"/v1/follow-ups/{draft['id']}/send")
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"] == "follow_up_not_waiting"
    assert await firm.outbox("follow_up.sent") == 0


# --- AC-19: the agent never sends -------------------------------------------------------------


async def test_ac19_the_matrix_denies_the_agent_the_send_and_its_undo_and_dismiss() -> None:
    rule = RULES["follow_up.send"]
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("system", "deny") == "deny"
    # DEC-220: no agent cell is an autonomy-policy cell, so no autonomy level opens it.
    assert all("autonomy" not in str(v) for k, v in rule.decisions.items() if k == "agent")


async def _record_sent(firm: Firm, actor_kind: str) -> None:
    async with uow(TenantContext(firm.tenant_id, actor_kind, "p06t23-test")) as tx:  # type: ignore[arg-type]  # actor kind
        tx.record("follow_up.sent", target=Target("follow_up", uuid.uuid4()))


async def test_ac19_the_database_refuses_follow_up_sent_from_the_agent(firm: Firm) -> None:
    with pytest.raises(DBAPIError):
        await _record_sent(firm, "agent")
    assert await firm.audits("follow_up.sent") == []


async def test_ac19_the_database_refuses_follow_up_sent_from_the_system(firm: Firm) -> None:
    with pytest.raises(DBAPIError):
        await _record_sent(firm, "system")


async def test_ac19_the_human_only_register_lists_follow_up_sent() -> None:
    register = Path(__file__).resolve().parents[4] / "docs/architecture/human-only-actions.yaml"
    assert "follow_up.sent" in register.read_text()


# --- AC-20: who drafts and sends --------------------------------------------------------------


@pytest.mark.parametrize("role", ["partner", "manager", "senior", "staff", "client_service"])
async def test_ac20_these_roles_draft_and_send(net: Net, role: str) -> None:
    f = await _firm(net)
    await f.request("Brokerage statements")
    await _publish(f)
    who = cast(Person, getattr(f, role))
    drafts = await f.draft_binder(who)
    assert len(drafts) == 2
    sent = await f.call(who, "POST", f"/v1/follow-ups/{drafts[0]['id']}/send")
    assert sent.status_code == 200, sent.text
    assert await f.audits("follow_up.sent") == [("human", str(who.user_id))]


async def test_ac20_a_reviewer_may_not_send(firm: Firm) -> None:
    draft = (await firm.draft_binder())[0]
    refused = await firm.call(firm.reviewer, "POST", f"/v1/follow-ups/{draft['id']}/send")
    assert refused.status_code == 403, refused.text
    refused_many = await firm.call(
        firm.reviewer, "POST", "/v1/follow-ups/send", {"ids": [str(draft["id"])]}
    )
    assert refused_many.status_code == 403, refused_many.text
    assert await firm.outbox("follow_up.sent") == 0


async def test_ac20_a_reviewer_may_not_draft_either(firm: Firm) -> None:
    response, items = await firm.draft(firm.reviewer, {"binder_ids": [str(firm.binder)]})
    assert response.status_code == 403, response.text
    assert items == []


async def test_ac20_a_client_user_may_not_send(firm: Firm) -> None:
    draft = (await firm.draft_binder())[0]
    sent = await firm.call(firm.ada, "POST", f"/v1/follow-ups/{draft['id']}/send")
    assert sent.status_code in (403, 404), sent.text
    assert await firm.outbox("follow_up.sent") == 0


# --- INV-3, DEC-43: walls and other firms -----------------------------------------------------


async def test_inv3_a_walled_member_gets_404_on_the_follow_up_and_its_send(firm: Firm) -> None:
    draft = (await firm.draft_binder())[0]
    await firm.net.wall(firm.admin, firm.staff, firm.site)
    for method, path in (
        ("GET", f"/v1/follow-ups/{draft['id']}"),
        ("POST", f"/v1/follow-ups/{draft['id']}/send"),
        ("POST", f"/v1/follow-ups/{draft['id']}/dismiss"),
    ):
        response = await firm.call(firm.staff, method, path)
        assert response.status_code == 404, (path, response.text)
    assert await firm.outbox("follow_up.sent") == 0


async def test_dec43_another_firm_gets_404(net: Net, firm: Firm) -> None:
    draft = (await firm.draft_binder())[0]
    stranger = await _firm(net)
    for method, path in (
        ("GET", f"/v1/follow-ups/{draft['id']}"),
        ("PATCH", f"/v1/follow-ups/{draft['id']}"),
        ("POST", f"/v1/follow-ups/{draft['id']}/send"),
    ):
        body: Json | None = {"body": "Hello"} if method == "PATCH" else None
        response = await stranger.call(stranger.manager, method, path, body)
        assert response.status_code == 404, (path, response.text)


# --- ED-082: a selection with nothing to chase -------------------------------------------------

# POST /v1/follow-ups/drafts authorised only the engagements of the requests it found, so a
# selection with none (nothing open, a walled or another firm's binder, a client principal) never
# called authorise and the route guard answered 500 `authz.unchecked_route`. Fixed by Q-03-T038
# (TASK-1354): requests says which engagements the selection names (`selection_engagements`).


async def test_ac16_a_published_binder_with_nothing_open_drafts_nothing(net: Net) -> None:
    f = await _firm(net)
    await f.request("Already received", status="received")
    await _publish(f)
    response, items = await f.draft(f.manager, {"binder_ids": [str(f.binder)]})
    assert response.status_code == 201, response.text
    assert items == []
    assert await f.audits("follow_up.drafted") == []


async def test_inv3_a_walled_member_drafting_over_the_binder_gets_404(firm: Firm) -> None:
    await firm.net.wall(firm.admin, firm.staff, firm.site)
    response, items = await firm.draft(firm.staff, {"binder_ids": [str(firm.binder)]})
    assert response.status_code == 404, response.text
    assert items == []


async def test_dec43_another_firm_drafting_over_the_binder_gets_404(net: Net, firm: Firm) -> None:
    stranger = await _firm(net)
    response, items = await stranger.draft(stranger.manager, {"binder_ids": [str(firm.binder)]})
    assert response.status_code == 404, response.text
    assert items == []


async def test_ac20_a_client_user_may_not_draft(firm: Firm) -> None:
    response, items = await firm.draft(firm.ada, {"binder_ids": [str(firm.binder)]})
    assert response.status_code in (403, 404), response.text
    assert items == []


# --- DEC-368: the screening return ------------------------------------------------------------


async def _uploaded(f: Firm, item: uuid.UUID, label: str) -> uuid.UUID:
    """A client's file on the request: an evidence version fulfilling it, the request Uploaded."""
    evidence = await f.seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id) VALUES ($1, $2, $3, 'system', 'seed') RETURNING id",
        f.tenant_id,
        f.site.engagement_id,
        f"{label}.pdf",
    )
    fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    version = cast(
        uuid.UUID,
        await f.seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method) VALUES ($1, $2, $3, 1, $4, $5, 'v1', 10, 'application/pdf', "
            "'upload', 'uploaded') RETURNING id",
            f.tenant_id,
            f.site.engagement_id,
            evidence,
            fingerprint,
            f"tenants/{f.tenant_id}/sha256/{fingerprint}",
        ),
    )
    await f.seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id) "
        "VALUES ($1, $2, $3, $4, 'human', 'seed')",
        f.tenant_id,
        f.site.engagement_id,
        item,
        version,
    )
    await f.seed.run("UPDATE request_items SET status = 'uploaded' WHERE id = $1", item)
    return version


@dataclass(frozen=True)
class Return:
    firm: Firm
    item: uuid.UUID
    version: uuid.UUID

    @property
    def path(self) -> str:
        return (
            f"/v1/engagements/{self.firm.site.engagement_id}/request-items/{self.item}/follow-ups"
        )

    async def draft(self, who: Person | None = None) -> httpx.Response:
        return await self.firm.call(
            who or self.firm.manager,
            "POST",
            self.path,
            {"kind": "screening_return", "returning": [str(self.version)]},
        )

    async def send_backs(self) -> int:
        return await self.firm.count(
            "SELECT count(*) FROM review_decisions WHERE tenant_id = $1 "
            "AND evidence_version_id = $2 AND decision = 'send_back'",
            self.firm.tenant_id,
            self.version,
        )

    async def item_status(self) -> str:
        return str(
            await self.firm.seed.value("SELECT status FROM request_items WHERE id = $1", self.item)
        )

    async def shared_comments(self) -> list[uuid.UUID]:
        rows = await self.firm.seed.rows(
            "SELECT author_user_id FROM comments WHERE tenant_id = $1 AND request_item_id = $2 "
            "AND visibility = 'shared'",
            self.firm.tenant_id,
            self.item,
        )
        return [r["author_user_id"] for r in rows]


@pytest.fixture
async def ret(net: Net) -> Return:
    f = await _firm(net, screening=True)
    item = await f.request("Brokerage statements", status="requested")
    await _publish(f)
    version = await _uploaded(f, item, "wrong-file")
    return Return(f, item, version)


async def test_dec368_the_return_draft_sends_nothing_and_decides_nothing(
    ret: Return, mailbox: Path
) -> None:
    drafted = await ret.draft()
    assert drafted.status_code == 201, drafted.text
    out = cast(Json, drafted.json())
    assert out["kind"] == "screening_return" and out["status"] == "drafted"
    assert out["template_key"] == "notification.follow_up_sent.screening_return"
    assert out["returning"] == [
        {"evidence_version_id": str(ret.version), "reason_code": "wrong_document"}
    ]
    assert await ret.send_backs() == 0
    assert await ret.item_status() == "uploaded"
    assert await ret.shared_comments() == []
    assert await ret.firm.outbox("follow_up.sent") == 0 and _mails(mailbox) == []


async def test_dec368_the_send_returns_the_files_and_the_request_with_the_person_named(
    ret: Return, mailbox: Path
) -> None:
    draft = cast(Json, (await ret.draft()).json())
    sent = await ret.firm.call(ret.firm.manager, "POST", f"/v1/follow-ups/{draft['id']}/send")
    assert sent.status_code == 200, sent.text
    assert await ret.send_backs() == 1
    actor = await ret.firm.seed.value(
        "SELECT actor_id FROM review_decisions WHERE tenant_id = $1 AND evidence_version_id = $2",
        ret.firm.tenant_id,
        ret.version,
    )
    assert actor == str(ret.firm.manager.user_id)
    assert await ret.item_status() == "returned"
    # Nothing the client reads exists while the send can be undone.
    assert await ret.shared_comments() == []
    assert await ret.firm.deliver(T0 + timedelta(seconds=5)) == 0
    assert _mails(mailbox) == []
    # After the window: the email and the shared comment, by the sender, once.
    assert await ret.firm.deliver(T0 + timedelta(seconds=11)) == 1
    await ret.firm.deliver(T0 + timedelta(seconds=20))
    assert await ret.shared_comments() == [ret.firm.manager.user_id]
    emails = await ret.firm.emails()
    assert len(emails) == 1 and emails[0][1] == ret.firm.manager.user_id
    assert len(_mails(mailbox)) == 1


async def test_dec368_undo_puts_the_files_and_the_request_back_and_sends_nothing(
    ret: Return, mailbox: Path
) -> None:
    draft = cast(Json, (await ret.draft()).json())
    sent = await ret.firm.call(ret.firm.manager, "POST", f"/v1/follow-ups/{draft['id']}/send")
    assert sent.status_code == 200, sent.text
    undone = await ret.firm.call(
        ret.firm.manager,
        "POST",
        f"/v1/follow-ups/{draft['id']}/undo",
        at=T0 + timedelta(seconds=8),
    )
    assert undone.status_code == 200, undone.text
    assert await ret.item_status() == "uploaded"
    assert await ret.firm.deliver(T0 + timedelta(seconds=30)) == 0
    assert await ret.shared_comments() == []
    assert await ret.firm.emails() == [] and _mails(mailbox) == []
    # The file is undecided again: a person may accept it.
    accepted = await ret.firm.call(
        ret.firm.partner,
        "POST",
        f"/v1/engagements/{ret.firm.site.engagement_id}/evidence-versions/{ret.version}"
        "/decision/accept",
        {},
        at=T0 + timedelta(minutes=1),
    )
    assert accepted.status_code in (200, 201), accepted.text


async def test_dec368_a_return_is_sent_on_its_own(ret: Return) -> None:
    draft = cast(Json, (await ret.draft()).json())
    refused = await ret.firm.call(
        ret.firm.manager, "POST", "/v1/follow-ups/send", {"ids": [str(draft["id"])]}
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"] == "follow_up_send_alone"
    assert await ret.send_backs() == 0 and await ret.item_status() == "uploaded"


async def test_dec368_a_sender_who_may_not_reject_evidence_returns_nothing(ret: Return) -> None:
    """`client_service` may send follow-ups (AC-20) but holds no `evidence.reject`: its return
    is refused and leaves the files and the request as they were."""
    draft = cast(Json, (await ret.draft()).json())
    refused = await ret.firm.call(
        ret.firm.client_service, "POST", f"/v1/follow-ups/{draft['id']}/send"
    )
    assert refused.status_code in (403, 404, 409), refused.text
    assert await ret.send_backs() == 0 and await ret.item_status() == "uploaded"
    assert await ret.firm.outbox("follow_up.sent") == 0


async def test_dec368_a_reviewer_may_not_draft_a_return(ret: Return) -> None:
    refused = await ret.draft(ret.firm.reviewer)
    assert refused.status_code == 403, refused.text


async def test_dec368_screening_card_off_the_return_route_answers_404(net: Net) -> None:
    f = await _firm(net, screening=False)
    item = await f.request("Brokerage statements")
    await _publish(f)
    version = await _uploaded(f, item, "wrong-file")
    response = await Return(f, item, version).draft()
    assert response.status_code == 404, response.text
