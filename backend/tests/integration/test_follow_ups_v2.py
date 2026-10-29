"""P-06-T14 against Postgres (SPEC-319 AC-16 to AC-20; P-06 Story 2.2; DEC-74, DEC-24): the
platform drafts one follow-up per client contact from the published Reminder template, a person
edits and sends it, the email leaves only after the 10-s Undo window, and nothing lets the agent
send.

The services run as the app role; seed rows go through the superuser. The firm is synthetic and
its clock frozen, so the Undo window, the grant and the relay read the same time. Delivery is
driven by hand: each relay pass's published `follow_up.sent` events go to the subscriber.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from datetime import timedelta

import asyncpg
import pytest

from abacus.kernel import clock
from abacus.kernel._human_only_actions import HUMAN_ONLY_ACTIONS
from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, configure_relay_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.agents import follow_up_drafts as follow_ups
from abacus.modules.agents.follow_up_drafts import (
    FollowUpAlreadySent,
    FollowUpEffectStarted,
    FollowUpNotWaiting,
    FollowUpOutOfScope,
    FollowUpUndoClosed,
)
from abacus.modules.communications.transport import configure_transport
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.requests import binders
from abacus.modules.requests.binders import BinderNotPublished

from .agent_tests.support import Seeder
from .backfill.follow_up_template import import_reminder_template
from .conftest import MigratedDatabase
from .test_binder_lifecycle import T0, World, make_world
from .test_binder_lifecycle import drain as _drain
from .test_binder_lifecycle import relay as _relay
from .test_human_only_guard import AUDIT


@dataclass
class Mailbox:
    sent: list[dict[str, str]] = field(default_factory=list[dict[str, str]])

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
        self.sent.append({"to": to, "subject": subject, "body": body, "id": str(message_id)})


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    configure_relay_engine(migrated_db.relay_url)
    await import_reminder_template()
    yield
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


@pytest.fixture(autouse=True)
def mailbox() -> Iterator[Mailbox]:
    box = Mailbox()
    configure_transport(box)
    yield box
    configure_transport(None)


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@dataclass(frozen=True)
class Chase:
    world: World
    binder: uuid.UUID
    items: tuple[uuid.UUID, uuid.UUID]
    claire: AuthContext  # the client admin

    @property
    def partner(self) -> AuthContext:
        return self.world.partner


async def _publish(seed: Seeder, world: World, binder: uuid.UUID) -> None:
    await seed.run(
        "UPDATE request_lists SET status = 'published', published_at = $2, published_by = $3 "
        "WHERE id = $1",
        binder,
        T0 - timedelta(days=7),
        world.partner.user_id,
    )


async def _chase(seed: Seeder) -> Chase:
    world = await make_world(seed)
    binder = await world.binder()
    await _publish(seed, world, binder)  # only a Published binder is chased
    first = await world.item(binder, description="Brokerage statements", status="requested")
    second = await world.item(
        binder, description="Mortgage interest statement", status="requested"
    )
    await world.item(binder, description="Never sent", visible=False)  # a Draft: never chased
    await world.item(binder, description="Already in", status="received")
    claire = await world.client_user("owner")
    return Chase(world, binder, (first, second), claire)


async def _deliver(events: list[OutboxEvent]) -> int:
    sent = [e for e in events if e.event_type == "follow_up.sent"]
    for event in sent:
        await follow_ups.on_follow_up_sent(event)
    return len(sent)


async def _sent_and_relayed(chase: Chase) -> follow_ups.FollowUpView:
    with clock.frozen(T0):
        [draft] = await follow_ups.draft_for(chase.partner, [chase.binder], [])
    await _drain()
    with clock.frozen(T0 + timedelta(seconds=1)):
        return await follow_ups.send(chase.partner, draft.id)


# --- AC-16: one draft per contact, each request once, from the database template ---


async def test_ac16_one_draft_per_contact_listing_each_open_request_once(seed: Seeder) -> None:
    chase = await _chase(seed)
    with clock.frozen(T0):
        drafts = await follow_ups.draft_for(chase.partner, [chase.binder], [])
    [draft] = drafts
    assert draft.recipient_user_id == chase.claire.user_id
    assert [i.request_item_id for i in draft.items] == list(chase.items)
    assert [i.overdue for i in draft.items] == [False, False]  # due Oct 1, read on Sep 14
    assert draft.status == "drafted" and draft.kind == "chase"
    assert draft.drafted_by_kind == "agent"  # the C-31 marker: composed by the Request Chaser
    assert draft.binder_id == chase.binder
    assert "- Brokerage statements\n- Mortgage interest statement\n" in draft.body
    assert "Never sent" not in draft.body and "Already in" not in draft.body
    assert (
        draft.subject.startswith("Firm ")
        and " is still waiting on Seeded client · " in draft.subject
    )
    assert "Accrued" not in draft.subject + draft.body  # L7
    # Asking again drafts nothing: both requests already wait in Claire's draft.
    with clock.frozen(T0):
        assert await follow_ups.draft_for(chase.partner, [], list(chase.items)) == []
    assert await chase.world.actions(draft.id) == ["follow_up.drafted"]


async def test_ac16_a_walled_or_unreadable_binder_drafts_nothing(seed: Seeder) -> None:
    chase = await _chase(seed)
    outsider = await seed.person(chase.world.tenant)
    with clock.frozen(T0):
        assert await follow_ups.draft_for(outsider.context(), [chase.binder], []) == []
    assert (
        await seed.value(
            "SELECT count(*) FROM follow_up_schedules WHERE engagement_id = $1",
            chase.world.engagement,
        )
        == 0
    )


# --- AC-17: edit before sending ---


async def test_ac17_a_person_edits_the_body_and_the_edit_is_sealed(seed: Seeder) -> None:
    chase = await _chase(seed)
    with clock.frozen(T0):
        [draft] = await follow_ups.draft_for(chase.partner, [chase.binder], [])
        edited = await follow_ups.edit(chase.partner, draft.id, "Claire, two items left. Thanks!")
    assert edited.edited and edited.body == "Claire, two items left. Thanks!"
    stored = await seed.rows(
        "SELECT body_sealed, edit_fingerprint, body_fingerprint FROM follow_up_schedules "
        "WHERE id = $1",
        draft.id,
    )
    assert b"two items left" not in bytes(stored[0]["body_sealed"])  # sealed, not plain text
    assert stored[0]["edit_fingerprint"] != stored[0]["body_fingerprint"]
    assert await chase.world.actions(draft.id) == ["follow_up.drafted", "follow_up.edited"]


# --- AC-18: a person sends; the email leaves after the Undo window; Undo sends nothing ---


async def test_ac18_send_holds_the_email_until_the_window_ends_and_grace_is_the_sender(
    seed: Seeder, mailbox: Mailbox
) -> None:
    chase = await _chase(seed)
    with clock.frozen(T0):
        [draft] = await follow_ups.draft_for(chase.partner, [chase.binder], [])
        await follow_ups.edit(chase.partner, draft.id, "Two items left: see your list.")
    await _drain()
    with clock.frozen(T0 + timedelta(seconds=1)):
        sent = await follow_ups.send(chase.partner, draft.id)
    assert sent.status == "sent" and sent.sent_by == chase.partner.user_id
    assert sent.undo_until == T0 + timedelta(seconds=11)
    assert await _deliver(await _relay(T0 + timedelta(seconds=5))) == 0
    assert mailbox.sent == []
    await seed.run(
        "UPDATE outbox SET next_attempt_at = NULL WHERE tenant_id = $1", chase.world.tenant
    )
    assert await _deliver(await _relay(T0 + timedelta(seconds=12))) == 1
    [email] = mailbox.sent
    assert email["body"] == "Two items left: see your list."
    assert email["id"] == str(draft.id)
    # INV-5: the audit trail reads the person as sender; the message is created by them.
    actor = await seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE target_id = $1 "
        "AND action = 'follow_up.sent'",
        str(draft.id),
    )
    assert [(r["actor_kind"], r["actor_id"]) for r in actor] == [
        ("human", str(chase.partner.user_id))
    ]
    assert (
        await seed.value("SELECT created_by FROM messages WHERE id = $1", draft.id)
        == chase.partner.user_id
    )
    # A redelivery sends nothing twice.
    await follow_ups.on_follow_up_sent(
        OutboxEvent(
            uuid.uuid4(), chase.world.tenant, "follow_up.sent", {"follow_up_id": str(draft.id)}
        )
    )
    assert len(mailbox.sent) == 1
    with clock.frozen(T0 + timedelta(seconds=13)), pytest.raises(FollowUpAlreadySent):
        await follow_ups.send(chase.partner, draft.id)


async def test_ac18_undo_within_ten_seconds_sends_nothing_and_puts_the_draft_back(
    seed: Seeder, mailbox: Mailbox
) -> None:
    chase = await _chase(seed)
    await _sent_and_relayed(chase)
    [draft_id] = [
        r["id"]
        for r in await seed.rows(
            "SELECT id FROM follow_up_schedules WHERE engagement_id = $1", chase.world.engagement
        )
    ]
    with clock.frozen(T0 + timedelta(seconds=6)):
        back = await follow_ups.undo(chase.partner, draft_id)
    assert back.status == "drafted" and back.sent_by is None and back.undo_until is None
    assert await _deliver(await _relay(T0 + timedelta(seconds=12))) == 0
    assert mailbox.sent == []
    assert "follow_up.undone" in await chase.world.actions(draft_id)


async def test_ac18_undo_after_the_window_or_after_delivery_is_refused(seed: Seeder) -> None:
    chase = await _chase(seed)
    sent = await _sent_and_relayed(chase)
    with clock.frozen(T0 + timedelta(seconds=11)), pytest.raises(FollowUpUndoClosed):
        await follow_ups.undo(chase.partner, sent.id)
    assert await _deliver(await _relay(T0 + timedelta(seconds=12))) == 1
    # The window read by a skewed stamp would be open again: the consumed grant still refuses.
    await seed.run(
        "UPDATE follow_up_schedules SET not_before = $2 WHERE id = $1",
        sent.id,
        T0 + timedelta(minutes=5),
    )
    with clock.frozen(T0 + timedelta(seconds=13)), pytest.raises(FollowUpEffectStarted):
        await follow_ups.undo(chase.partner, sent.id)


async def test_ac18_an_out_of_scope_body_is_refused_and_nothing_is_written(
    seed: Seeder, mailbox: Mailbox
) -> None:
    chase = await _chase(seed)
    await seed.entity(chase.world.tenant, "Granite Peak Holdings")
    with clock.frozen(T0):
        [draft] = await follow_ups.draft_for(chase.partner, [chase.binder], [])
        await follow_ups.edit(chase.partner, draft.id, "Also send Granite Peak Holdings files.")
        with pytest.raises(FollowUpOutOfScope):
            await follow_ups.send(chase.partner, draft.id)
    again = await follow_ups.read(chase.partner, draft.id)
    assert again.status == "drafted" and again.sent_by is None
    assert "follow_up.sent" not in await chase.world.actions(draft.id)


async def test_ac18_dismiss_closes_the_draft_and_sends_nothing(
    seed: Seeder, mailbox: Mailbox
) -> None:
    chase = await _chase(seed)
    with clock.frozen(T0):
        [draft] = await follow_ups.draft_for(chase.partner, [chase.binder], [])
        closed = await follow_ups.dismiss(chase.partner, draft.id)
    assert closed.status == "dismissed"
    # Dismissed requests may be chased again.
    with clock.frozen(T0):
        assert len(await follow_ups.draft_for(chase.partner, [chase.binder], [])) == 1


# --- AC-19 / AC-20: who may send ---


async def test_ac20_staff_may_now_send_and_a_reviewer_may_not(seed: Seeder) -> None:
    chase = await _chase(seed)
    staff, reviewer = await seed.person(chase.world.tenant), await seed.person(chase.world.tenant)
    await seed.member(chase.world.engagement, staff, "staff")
    await seed.member(chase.world.engagement, reviewer, "reviewer")
    with clock.frozen(T0):
        [draft] = await follow_ups.draft_for(staff.context(), [chase.binder], [])
        with pytest.raises(Forbidden):
            await follow_ups.send(reviewer.context(), draft.id)
        sent = await follow_ups.send(staff.context(), draft.id)
    assert sent.sent_by == staff.user_id


async def test_a_retried_send_is_authorised_again_before_its_stored_answer(seed: Seeder) -> None:
    """ED-023's shape on the follow-up send routes: the route checks `follow_up.send` before the
    idempotency lookup, so a replay reaches only someone who may send now."""
    chase = await _chase(seed)
    reviewer = await seed.person(chase.world.tenant)
    await seed.member(chase.world.engagement, reviewer, "reviewer")
    with clock.frozen(T0):
        [draft] = await follow_ups.draft_for(chase.partner, [chase.binder], [])
        await follow_ups.check_send(chase.partner, [draft.id])  # the first send's check passes
        await follow_ups.send(chase.partner, draft.id)
        await follow_ups.check_send(chase.partner, [draft.id])  # a replay is checked the same
        with pytest.raises(Forbidden):
            await follow_ups.check_send(reviewer.context(), [draft.id])
        with pytest.raises(NotFound):
            await follow_ups.check_send(chase.partner, [draft.id, uuid.uuid4()])


async def test_ac19_the_database_refuses_follow_up_sent_from_an_agent(seed: Seeder) -> None:
    tenant = await seed.firm()
    agent = ("agent", "agent:engagement.agent:run")
    assert "follow_up.sent" in HUMAN_ONLY_ACTIONS
    with pytest.raises(asyncpg.InsufficientPrivilegeError, match="human_only_action"):
        await seed.as_actor(
            tenant, agent, AUDIT, tenant, *agent, "follow_up.sent", str(uuid.uuid4()), None, None
        )


# --- Security review (P-06-T14 review, 2026-10-24) ---


@pytest.mark.parametrize("status", ["draft", "unpublished", "complete", "closed"])
async def test_review1_a_binder_that_is_not_published_is_never_chased(
    seed: Seeder, status: str
) -> None:
    chase = await _chase(seed)
    await seed.run("UPDATE request_lists SET status = $2 WHERE id = $1", chase.binder, status)
    with clock.frozen(T0), pytest.raises(BinderNotPublished):
        await follow_ups.draft_for(chase.partner, [chase.binder], [])
    # Asked for by request id, its requests are left out: nothing is drafted.
    with clock.frozen(T0):
        assert await follow_ups.draft_for(chase.partner, [], list(chase.items)) == []
    count = await seed.value(
        "SELECT count(*) FROM follow_up_schedules WHERE engagement_id = $1",
        chase.world.engagement,
    )
    assert count == 0


async def test_review2_a_request_title_naming_another_client_is_refused_at_draft(
    seed: Seeder,
) -> None:
    chase = await _chase(seed)
    await seed.entity(chase.world.tenant, "Granite Peak Holdings")
    await seed.run(
        "UPDATE request_items SET title = 'Granite Peak Holdings statements' WHERE id = $1",
        chase.items[0],
    )
    with clock.frozen(T0), pytest.raises(FollowUpOutOfScope):
        await follow_ups.draft_for(chase.partner, [chase.binder], [])
    count = await seed.value(
        "SELECT count(*) FROM follow_up_schedules WHERE engagement_id = $1",
        chase.world.engagement,
    )
    assert count == 0


async def test_review2_an_unedited_follow_up_is_checked_again_at_send(seed: Seeder) -> None:
    chase = await _chase(seed)
    with clock.frozen(T0):
        [draft] = await follow_ups.draft_for(chase.partner, [chase.binder], [])
    # The title changes after drafting (request_item.update) to name another client.
    await seed.entity(chase.world.tenant, "Granite Peak Holdings")
    await seed.run(
        "UPDATE request_items SET title = 'Granite Peak Holdings statements' WHERE id = $1",
        chase.items[0],
    )
    with clock.frozen(T0 + timedelta(seconds=1)), pytest.raises(FollowUpOutOfScope):
        await follow_ups.send(chase.partner, draft.id)
    assert (await follow_ups.read(chase.partner, draft.id)).status == "drafted"


async def test_review4_concurrent_drafts_for_a_contact_make_one_draft(seed: Seeder) -> None:
    chase = await _chase(seed)
    with clock.frozen(T0):
        results = await asyncio.gather(
            follow_ups.draft_for(chase.partner, [chase.binder], []),
            follow_ups.draft_for(chase.partner, [chase.binder], []),
            follow_ups.draft_for(chase.partner, [], list(chase.items)),
        )
    assert sum(len(r) for r in results) >= 1
    drafts = await seed.rows(
        "SELECT id FROM follow_up_schedules WHERE engagement_id = $1 AND status = 'drafted'",
        chase.world.engagement,
    )
    assert len(drafts) == 1
    items = await seed.rows(
        "SELECT request_item_id FROM follow_up_items WHERE follow_up_id = $1", drafts[0]["id"]
    )
    assert sorted(r["request_item_id"] for r in items) == sorted(chase.items)


async def test_review5_allowed_actions_follow_the_state_and_the_sender(seed: Seeder) -> None:
    chase = await _chase(seed)
    manager = await seed.person(chase.world.tenant)
    await seed.member(chase.world.engagement, manager, "manager")
    with clock.frozen(T0):
        [draft] = await follow_ups.draft_for(chase.partner, [chase.binder], [])
    assert draft.allowed_actions == ["follow_up.draft", "follow_up.send"]
    with clock.frozen(T0 + timedelta(seconds=1)):
        sent = await follow_ups.send(chase.partner, draft.id)
        assert sent.allowed_actions == ["follow_up.send"]  # its sender may Undo
        other = await follow_ups.read(manager.context(), draft.id)
        assert other.allowed_actions == []  # no one else may
    with clock.frozen(T0 + timedelta(seconds=11)):
        assert (await follow_ups.read(chase.partner, draft.id)).allowed_actions == []
    with clock.frozen(T0 + timedelta(seconds=12)), pytest.raises(FollowUpAlreadySent):
        await follow_ups.dismiss(chase.partner, draft.id)


async def test_review5_a_dismissed_follow_up_offers_nothing(seed: Seeder) -> None:
    chase = await _chase(seed)
    with clock.frozen(T0):
        [draft] = await follow_ups.draft_for(chase.partner, [chase.binder], [])
        closed = await follow_ups.dismiss(chase.partner, draft.id)
    assert closed.allowed_actions == []
    with clock.frozen(T0), pytest.raises(FollowUpNotWaiting):
        await follow_ups.send(chase.partner, draft.id)


async def test_review5_an_unconfirmed_staff_member_may_read_but_not_send(seed: Seeder) -> None:
    """A draft is not client data (SPEC-027 AC-8), so reading it needs no independence
    confirmation; sending it to the client does (DEC-220). G2 v2 (SPEC-332 AC-13, AC-14;
    P-07-T24): the send is gated on an attest client's engagement, which this one is made."""
    chase = await _chase(seed)
    await seed.run(  # the derived flag (DEC-128), set as the trigger would for an active audit
        "UPDATE clients SET is_attest_client = true "
        "WHERE id = (SELECT client_id FROM engagements WHERE id = $1)",
        chase.world.engagement,
    )
    with clock.frozen(T0):
        [draft] = await follow_ups.draft_for(chase.partner, [chase.binder], [])
    staff = await seed.person(chase.world.tenant)
    await seed.run(  # a member who has not confirmed independence
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'staff')",
        chase.world.tenant,
        chase.world.engagement,
        staff.user_id,
    )
    with clock.frozen(T0):
        assert (await follow_ups.read(staff.context(), draft.id)).id == draft.id
    with clock.frozen(T0), pytest.raises(Forbidden):
        await follow_ups.send(staff.context(), draft.id)


async def test_review5_only_a_published_binder_offers_follow_ups(seed: Seeder) -> None:
    chase = await _chase(seed)
    with clock.frozen(T0):
        published = await binders.read_binder(chase.partner, chase.binder)
    assert {"follow_up.draft", "follow_up.send"} <= set(published.allowed_actions)
    for status in ("draft", "unpublished", "complete", "closed"):
        await seed.run("UPDATE request_lists SET status = $2 WHERE id = $1", chase.binder, status)
        with clock.frozen(T0):
            record = await binders.read_binder(chase.partner, chase.binder)
        assert not {"follow_up.draft", "follow_up.send"} & set(record.allowed_actions), status
