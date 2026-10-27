"""R-01-T24 security review H1, M1, M2, L1, L2 (TASK-1421; DEC-566, DEC-568, DEC-569).

The system's scheduled Reminder, through the P-4 tick and through communications' own
`send_scheduled_reminder`: it names only requests a client may be written to about (never an
internal request, or one in a binder that is closed, unpublished or not yet
published), it goes only from a version that passes the lint, it is recorded as the system's
(`drafted_by_kind = 'system'`, 0222), and a policy that does not send sends nothing. The limit
notification is raised once per binder, recipient and last reminder. Probe strings only."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import pytest

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext
from abacus.modules.agents import follow_ups
from abacus.modules.agents.follow_ups import chase_overdue, today_in
from abacus.modules.communications import template_send, template_service
from abacus.modules.communications.api import (
    FollowUpPolicy,
    save_follow_up_policy,
    send_scheduled_reminder,
)
from abacus.modules.communications.lint import LintFinding
from abacus.modules.communications.render import Block, TemplateContent
from abacus.modules.communications.transport import configure_transport
from abacus.modules.identity.api import AuthContext

from .follow_up_template import import_reminder_template
from .support import Person, Seeder, Site

ZONE = "America/Chicago"
REMINDER = TemplateContent(
    subject="Still needed for your {work_item}",
    preheader="",
    blocks=(
        Block("h1", "heading", "Hi {client_first_name}"),
        Block("p1", "paragraph", "{firm_name} still needs these for {work_item} by {due_date}:"),
        Block("l1", "item_list", "{open_items}"),
        Block("n1", "note", "Questions? Message {staff_name} in your portal."),
    ),
    cta_label="Open your portal",
    cta_target="documents",
)


@dataclass
class Mailbox:
    sent: list[dict[str, object]] = field(default_factory=lambda: list[dict[str, object]]())

    def send(self, **kwargs: object) -> None:
        self.sent.append(kwargs)


@pytest.fixture(autouse=True)
async def reminder_template(engines: None) -> None:
    await import_reminder_template()


@pytest.fixture(autouse=True)
def mailbox() -> Iterator[Mailbox]:
    box = Mailbox()
    configure_transport(box)
    yield box
    configure_transport(None)


def _ctx(who: Person) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(who.tenant_id, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role="firm_admin",
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


@dataclass(frozen=True)
class Firm:
    tenant: uuid.UUID
    site: Site
    contact: Person

    @property
    def system(self) -> TenantContext:
        return TenantContext(self.tenant, "system", "agents.engagement_agent")


async def _firm(seed: Seeder) -> Firm:
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "scheduled")
    await seed.member(site, admin, "engagement_partner")
    contact = await seed.client_contact(site)
    await seed.run("UPDATE firms SET time_zone = $2 WHERE tenant_id = $1", tenant, ZONE)
    for flag in ("portal.settings_editor", "follow_ups.scheduled_send"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'r01t24', 'TASK-1421')",
            tenant,
            flag,
        )
    ctx = _ctx(admin)
    await template_service.save_draft(ctx, "reminder", REMINDER, 0)
    await template_service.publish(ctx, "reminder")
    await save_follow_up_policy(ctx, FollowUpPolicy(mode="send_on_schedule"), 0)
    await _binder(seed, site, "published")
    return Firm(tenant, site, contact)


async def _binder(seed: Seeder, site: Site, status: str) -> None:
    await seed.run(
        "UPDATE request_lists SET status = $2, published_at = coalesce(published_at, now()), "
        "closed_at = CASE WHEN $2 = 'closed' THEN now() ELSE NULL END WHERE engagement_id = $1",
        site.engagement_id,
        status,
    )


def _due() -> date:
    return today_in(ZONE, system_now()) - timedelta(days=10)


async def test_h1_the_tick_names_only_what_a_client_may_be_written_to_about(
    seed: Seeder, mailbox: Mailbox
) -> None:
    firm = await _firm(seed)
    await seed.item(firm.site, "Bank statement", due_on=_due())
    internal = await seed.item(firm.site, "Internal memo", due_on=_due())
    await seed.run("UPDATE request_items SET client_visible = false WHERE id = $1", internal)
    # (A deleted request is never Requested: the database deletes unsent drafts only, and the
    # filter's `deleted_at` test is the second line.)
    outcome = await chase_overdue(
        firm.system, firm.site.engagement_id, ZONE, uuid.uuid4(), policy_v1=True
    )
    assert outcome.sent == 1 and outcome.drafted == 0
    assert len(mailbox.sent) == 1
    body = str(mailbox.sent[0]["body"])
    assert "Bank statement" in body
    assert "Internal memo" not in body
    rows = await seed.rows(
        "SELECT s.drafted_by_kind, s.status, array_agg(i.request_item_id) AS items "
        "FROM follow_up_schedules s JOIN follow_up_items i ON i.follow_up_id = s.id "
        "WHERE s.engagement_id = $1 GROUP BY s.id",
        firm.site.engagement_id,
    )
    assert [(r["drafted_by_kind"], r["status"], len(r["items"])) for r in rows] == [
        ("system", "sent", 1)  # L1: the system's, never a person's
    ]
    assert "follow_up.scheduled_sent" in await seed.actions(firm.tenant)


@pytest.mark.parametrize("status", ["closed", "unpublished", "draft"])
async def test_h1_nothing_goes_for_a_binder_that_is_not_open_and_published(
    seed: Seeder, mailbox: Mailbox, status: str
) -> None:
    firm = await _firm(seed)
    item = await seed.item(firm.site, "Bank statement", due_on=_due())
    await _binder(seed, firm.site, status)
    sent = await send_scheduled_reminder(
        firm.tenant, firm.site.engagement_id, firm.contact.user_id, [(item, _due(), 1)]
    )
    assert sent is None and mailbox.sent == []
    outcome = await chase_overdue(
        firm.system, firm.site.engagement_id, ZONE, uuid.uuid4(), policy_v1=True
    )
    assert outcome.sent == 0 and outcome.drafted == 0 and mailbox.sent == []


async def test_m2_communications_decides_whom_and_what(seed: Seeder, mailbox: Mailbox) -> None:
    firm = await _firm(seed)
    item = await seed.item(firm.site, "Bank statement", due_on=_due())
    stranger = await seed.person(firm.tenant)
    # Not a client admin of the engagement, nor the request's assignee: nothing.
    assert (
        await send_scheduled_reminder(
            firm.tenant, firm.site.engagement_id, stranger.user_id, [(item, _due(), 1)]
        )
        is None
    )
    # A due date the request no longer has: nothing.
    assert (
        await send_scheduled_reminder(
            firm.tenant,
            firm.site.engagement_id,
            firm.contact.user_id,
            [(item, _due() - timedelta(days=1), 1)],
        )
        is None
    )
    # The policy drafts for a person: nothing goes by itself.
    await seed.run(
        "UPDATE follow_up_policies SET mode = 'draft_for_person' WHERE tenant_id = $1", firm.tenant
    )
    assert (
        await send_scheduled_reminder(
            firm.tenant, firm.site.engagement_id, firm.contact.user_id, [(item, _due(), 1)]
        )
        is None
    )
    assert mailbox.sent == []


async def test_m1_a_version_the_lint_now_refuses_is_recorded_blocked_and_never_sent(
    seed: Seeder, mailbox: Mailbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    firm = await _firm(seed)
    item = await seed.item(firm.site, "Bank statement", due_on=_due())

    def refused(*_: object) -> list[LintFinding]:
        return [LintFinding("banned_word", "p1")]

    monkeypatch.setattr(template_send, "lint_template", refused)
    sent = await send_scheduled_reminder(
        firm.tenant, firm.site.engagement_id, firm.contact.user_id, [(item, _due(), 1)]
    )
    assert sent is not None
    assert (sent.outcome.status, sent.outcome.blocked_reason) == (
        "blocked",
        "template_lint_failed",
    )
    assert mailbox.sent == []
    assert "message.blocked" in await seed.actions(firm.tenant)


async def test_l2_the_limit_is_raised_once_for_the_same_binder_recipient_and_last_send(
    seed: Seeder,
) -> None:
    firm = await _firm(seed)
    binder = await seed.value(
        "SELECT id FROM request_lists WHERE engagement_id = $1 LIMIT 1", firm.site.engagement_id
    )
    assert isinstance(binder, uuid.UUID)
    last = date(2026, 9, 14)
    for _ in range(2):  # a retried tick
        await follow_ups._limit_reached(  # pyright: ignore[reportPrivateUsage] -- the dedupe
            firm.system, firm.site.engagement_id, binder, firm.contact.user_id, last
        )
    actions = await seed.actions(firm.tenant)
    assert actions.count("follow_up.limit_reached") == 1
