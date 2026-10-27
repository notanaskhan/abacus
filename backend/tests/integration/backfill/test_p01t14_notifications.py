# ac-test-author: ayushkbhatia
"""P-01-T14 (ADR-078): independent AC tests for the notifications v2 work (P-01-T03 migration,
P-01-T06 catalogue and feed, P-01-T12 preferences and email), superseding TASK-028 (SPEC-013).

Written from SPEC-013 §5, P-01 §3.3, §3.4 and §3.6 (INV-1, INV-3, INV-4, INV-5) and C16
(`docs/contracts/notifications.md`), against the public surface only: the relay's handlers in
`notifications.api.SUBSCRIPTIONS`, the HTTP routes through `create_app()`, the module's public
workflow and activities on a real Temporal dev server, and the database through SQL.

Where SPEC-013 and P-01/C16 disagree, the later contract is tested and the drift is recorded in
work/tasks/TASK-993-notifications-binder-independent-tests.md.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Final, cast

import asyncpg
import pytest
from temporalio.client import Client
from temporalio.worker import Worker

from abacus.kernel.config import settings
from abacus.kernel.dispatch import queue_for
from abacus.kernel.flags import forget_flags
from abacus.kernel.temporal import configure_temporal_client, data_converter
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.communications.api import FakeSesTransport, configure_transport, on_sink
from abacus.modules.communications.templates import import_platform_version
from abacus.modules.notifications import api as notifications
from abacus_tools.harness.mailbox import LocalMailboxReader

from .support import Migrated, Net, Person, Seeder, Site

Json = dict[str, object]
FEED: Final = "/v1/notifications/feed"
PREFERENCES: Final = "/v1/me/notification-preferences"
NOT_FOUND: Final = {"detail": "not found"}
# Templates are platform-wide in the session's database: this suite imports only
# `notification.client_uploaded`, which no other suite uses (test_email_templates.py expects to
# be the first to import `notification.mention`).
SUBJECT: Final = "{{kind_sentence}}"
BODY: Final = (
    "Hi {{recipient_first_name}},\n\n{{kind_sentence}}\n\n"
    "Engagement: {{engagement_display_name}}\nOpen it: {{app_link}}\n"
)
VARIABLES: Final = ["recipient_first_name", "kind_sentence", "engagement_display_name", "app_link"]
QUEUE: Final = f"p01t14-{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def process(engines: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A mailbox per test, the module's own email starter, fresh flag values."""
    monkeypatch.setenv("ABACUS_TEMPORAL_TASK_QUEUE", QUEUE)
    settings.cache_clear()
    forget_flags()
    configure_transport(FakeSesTransport(tmp_path / "mailbox"))
    yield
    configure_transport(None)
    notifications.configure_email_starter(None)
    forget_flags()


@pytest.fixture
async def temporal(temporal_target: str) -> AsyncIterator[Client]:
    client = await Client.connect(temporal_target, data_converter=data_converter())
    configure_temporal_client(client)
    yield client
    configure_temporal_client(None)


@pytest.fixture
async def worker(temporal: Client) -> AsyncIterator[None]:
    async with Worker(
        temporal,
        task_queue=queue_for("time_sensitive"),
        workflows=list(notifications.WORKFLOWS),
        activities=list(notifications.ACTIVITIES),  # type: ignore[arg-type]  # activity defs
    ):
        yield


@pytest.fixture
def started() -> list[object]:
    """Emails the fan-out asked to start (tests that do not run Temporal)."""
    calls: list[object] = []

    async def record(given: object) -> None:
        calls.append(given)

    notifications.configure_email_starter(record)
    return calls


class World:
    """One firm with `notifications.v2` on: an administrator, one opened engagement (the site)
    with a partner, a manager and a senior, and a client contact with a grant on it."""

    def __init__(self, net: Net, site: Site, people: dict[str, Person]) -> None:
        self.net, self.seed, self.site = net, net.seed, site
        self.tenant = site.tenant_id
        self.admin, self.partner = people["admin"], people["partner"]
        self.manager, self.senior = people["manager"], people["senior"]
        self.client = people["client"]

    def event(
        self, event_type: str, event_id: uuid.UUID | None = None, **payload: object
    ) -> OutboxEvent:
        body: Json = {"engagement_id": str(self.site.engagement_id)}
        body.update({k: str(v) if isinstance(v, uuid.UUID) else v for k, v in payload.items()})
        return OutboxEvent(
            event_id=event_id or uuid.uuid4(),
            tenant_id=self.tenant,
            event_type=event_type,
            payload=body,
        )

    async def relay(self, event: OutboxEvent) -> None:
        """What the relay does with a committed event: hand it to its subscriber."""
        await notifications.SUBSCRIPTIONS[event.event_type](event)

    def uploaded(self, event_id: uuid.UUID | None = None) -> OutboxEvent:
        return self.event(
            "evidence.uploaded",
            event_id,
            evidence_version_id=self.site.version_id,
            client_id=self.site.client_id,
        )

    def mention(self, *people: Person, by: Person | None = None) -> OutboxEvent:
        return self.event(
            "comment.mentioned",
            comment_id=uuid.uuid4(),
            request_item_id=self.site.item_id,
            mentioned_user_ids=[str(p.user_id) for p in people],
            by_user=(by or self.partner).user_id,
        )

    async def rows(self, who: Person | None = None) -> list[asyncpg.Record]:
        if who is None:
            return await self.seed.rows(
                "SELECT * FROM notifications WHERE tenant_id = $1 ORDER BY created_at", self.tenant
            )
        return await self.seed.rows(
            "SELECT * FROM notifications WHERE tenant_id = $1 AND recipient_user_id = $2 "
            "ORDER BY created_at",
            self.tenant,
            who.user_id,
        )

    async def recipients(self) -> set[uuid.UUID]:
        return {cast(uuid.UUID, r["recipient_user_id"]) for r in await self.rows()}

    async def feed(self, who: Person, **params: object) -> Json:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        response = await self.net.call("GET", f"{FEED}?{query}" if query else FEED, who)
        assert response.status_code == 200, response.text
        return cast(Json, response.json())

    async def deliveries(self) -> list[tuple[uuid.UUID, str]]:
        rows = await self.seed.rows(
            "SELECT n.recipient_user_id, d.status FROM notification_deliveries d "
            "JOIN notifications n ON n.id = d.notification_id WHERE d.tenant_id = $1",
            self.tenant,
        )
        return [(cast(uuid.UUID, r["recipient_user_id"]), str(r["status"])) for r in rows]

    async def actions(self, prefix: str) -> list[str]:
        return [a for a in await self.seed.actions(self.tenant) if a.startswith(prefix)]


async def _flags(seed: Seeder, tenant: uuid.UUID, *, v2: bool = True, email: bool = False) -> None:
    for flag, on in (("notifications.v2", v2), ("notifications.email", email)):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, $3, 'test-seed', 'P-01-T14 tests')",
            tenant,
            flag,
            "true" if on else "false",
        )


async def _named(seed: Seeder, who: Person, name: str, email: str) -> None:
    await seed.run(
        "UPDATE users SET display_name = $2, email = $3 WHERE id = $1", who.user_id, name, email
    )


async def _world(net: Net, *, email: bool = False, synthetic: bool = False) -> World:
    seed = net.seed
    tenant = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = $2 WHERE tenant_id = $1", tenant, synthetic)
    await _flags(seed, tenant, email=email)
    admin = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "p01t14")
    people = {"admin": admin}
    for name, role in (
        ("partner", "engagement_partner"),
        ("manager", "manager"),
        ("senior", "senior"),
    ):
        who = await seed.person(tenant)
        await seed.member(site, who, role)  # type: ignore[arg-type]  # a staff role
        people[name] = who
    await _named(seed, people["manager"], "Hannah Leclerc", "hannah.leclerc@example.test")
    people["client"] = await seed.client_contact(site)
    return World(net, site, people)


@pytest.fixture
async def world(net: Net) -> World:
    return await _world(net)


def _ids(feed: Json) -> list[str]:
    return [str(cast(Json, i)["id"]) for i in cast(list[object], feed["items"])]


# --- SPEC-013 AC-1, AC-3 and P-01 AC-7 storage: one row per recipient, identifiers only --------


async def test_ac1_one_notification_per_recipient_even_when_relayed_twice(world: World) -> None:
    event = world.event("engagement_member.added", user_id=world.senior.user_id)
    await world.relay(event)
    await world.relay(event)  # the relay delivers the event again
    (row,) = await world.rows()
    assert row["recipient_user_id"] == world.senior.user_id
    assert row["kind"] == "engagement_member.added"
    assert row["event_id"] == event.event_id
    assert row["engagement_id"] == world.site.engagement_id
    assert (row["subject_type"], row["subject_id"]) == ("engagement", world.site.engagement_id)
    assert row["created_at"] is not None and row["read_at"] is None


async def test_ac7_rows_store_identifiers_and_codes_never_text(
    world: World, migrated_db: Migrated
) -> None:
    """P-01-T03/T06 acceptance "no row stores text": the only text columns are codes, each under
    a CHECK, and no client or person name reaches a row."""
    await world.relay(world.uploaded())
    await world.relay(world.mention(world.manager))
    text_columns = {
        str(r["column_name"])
        for r in await world.seed.rows(
            "SELECT column_name FROM information_schema.columns WHERE table_name = "
            "'notifications' AND data_type IN ('text', 'character varying', 'jsonb', 'json')"
        )
    }
    assert text_columns == {"kind", "subject_type", "category", "actor_kind"}
    stored = await world.seed.rows(
        "SELECT row_to_json(n)::text AS j FROM notifications n WHERE tenant_id = $1", world.tenant
    )
    assert len(stored) == 3 + 1  # the staff team of three for the upload, Hannah for the mention
    assert all(world.site.marker not in str(r["j"]) for r in stored)
    assert all("Hannah" not in str(r["j"]) for r in stored)


async def test_ac3_an_event_outside_the_catalogue_makes_no_notification(world: World) -> None:
    assert "evidence.downloaded" not in notifications.SUBSCRIPTIONS
    handler = notifications.SUBSCRIPTIONS["evidence.uploaded"]
    await handler(world.event("evidence.downloaded", evidence_version_id=world.site.version_id))
    assert await world.rows() == []


# --- SPEC-013 AC-2 and INV-3/INV-4 at fan-out: who is a recipient -------------------------------


async def test_ac2_a_client_upload_reaches_the_staff_team_never_the_client(world: World) -> None:
    await world.relay(world.uploaded())
    assert await world.recipients() == {
        world.partner.user_id,
        world.manager.user_id,
        world.senior.user_id,
    }
    (row, *_) = await world.rows(world.partner)
    assert (row["kind"], row["category"]) == ("client_uploaded", "client_activity")
    assert (row["subject_type"], row["subject_id"]) == ("evidence_version", world.site.version_id)


async def test_ac2_a_self_join_notifies_the_team_but_not_the_joiner(world: World) -> None:
    await world.relay(world.event("engagement.member_self_joined", user_id=world.admin.user_id))
    assert await world.recipients() == {
        world.partner.user_id,
        world.manager.user_id,
        world.senior.user_id,
    }


async def test_ac2_a_person_whose_membership_was_revoked_is_not_a_recipient(
    world: World,
) -> None:
    await world.seed.revoke(world.senior)
    await world.relay(world.mention(world.senior, world.manager))
    assert await world.recipients() == {world.manager.user_id}


async def test_ac2_a_person_of_another_firm_is_never_a_recipient(world: World) -> None:
    """A mention naming someone outside the firm makes no row for them, and still reaches the
    people of the firm it names (the event is not lost)."""
    other_firm = await world.seed.firm()
    stranger = await world.seed.person(other_firm)
    await world.relay(world.mention(stranger, world.manager))
    assert await world.recipients() == {world.manager.user_id}


async def test_inv3_nobody_walled_from_the_client_gets_a_row_at_fan_out(world: World) -> None:
    await world.net.wall(world.admin, world.senior, world.site)
    await world.relay(world.uploaded())
    await world.relay(world.event("engagement_member.added", user_id=world.senior.user_id))
    assert world.senior.user_id not in await world.recipients()
    assert await world.recipients() == {world.partner.user_id, world.manager.user_id}


# --- SPEC-013 AC-4, AC-5 and INV-3 at read: own rows, walls, removal ---------------------------


async def test_ac4_the_feed_lists_only_the_callers_own(world: World) -> None:
    await world.relay(world.uploaded())
    mine = await world.feed(world.partner)
    own = {str(r["id"]) for r in await world.rows(world.partner)}
    assert set(_ids(mine)) == own and len(own) == 1
    assert mine["unread_count"] == 1
    assert cast(Json, mine["counts"])["client_activity"] == 1


async def test_ac4_another_persons_notification_is_not_found_and_stays_unread(
    world: World,
) -> None:
    await world.relay(world.uploaded())
    (theirs,) = await world.rows(world.senior)
    response = await world.net.call(
        "POST", f"/v1/notifications/{theirs['id']}/read", world.partner
    )
    assert (response.status_code, response.json()) == (404, NOT_FOUND)
    (after,) = await world.rows(world.senior)
    assert after["read_at"] is None


async def test_inv3_a_wall_added_after_fan_out_hides_rows_from_list_counts_and_dot(
    world: World,
) -> None:
    await world.relay(world.uploaded())
    await world.relay(world.mention(world.senior))
    before = await world.feed(world.senior)
    assert len(_ids(before)) == 2 and before["unread_count"] == 2
    await world.net.wall(world.admin, world.senior, world.site)

    for tab in ("all", "approvals", "mentions", "client_activity"):
        after = await world.feed(world.senior, tab=tab)
        assert after["items"] == [], tab
        assert after["unread_count"] == 0
        assert after["counts"] == {"approvals": 0, "mentions": 0, "client_activity": 0}
    v1 = await world.net.call("GET", "/v1/notifications", world.senior)
    assert v1.status_code == 200 and v1.json()["items"] == [] and v1.json()["unread_count"] == 0

    walled = await world.rows(world.senior)
    response = await world.net.call(
        "POST", f"/v1/notifications/{walled[0]['id']}/read", world.senior
    )
    assert (response.status_code, response.json()) == (404, NOT_FOUND)
    await world.net.call("POST", "/v1/notifications/read-all", world.senior)
    assert all(r["read_at"] is None for r in await world.rows(world.senior))


async def test_ac5_a_person_removed_from_the_team_no_longer_sees_its_rows(world: World) -> None:
    await world.relay(world.uploaded())
    assert len(_ids(await world.feed(world.senior))) == 1
    await world.seed.run(
        "DELETE FROM engagement_members WHERE tenant_id = $1 AND engagement_id = $2 "
        "AND user_id = $3",
        world.tenant,
        world.site.engagement_id,
        world.senior.user_id,
    )
    after = await world.feed(world.senior)
    assert (after["items"], after["unread_count"]) == ([], 0)


# --- SPEC-013 AC-6: reading --------------------------------------------------------------------


async def test_ac6_reading_sets_read_at_once_and_read_all_reads_the_rest(world: World) -> None:
    await world.relay(world.uploaded())
    await world.relay(world.mention(world.partner))
    first, second = await world.rows(world.partner)
    response = await world.net.call("POST", f"/v1/notifications/{first['id']}/read", world.partner)
    assert response.status_code == 200, response.text
    (stamped,) = [r for r in await world.rows(world.partner) if r["id"] == first["id"]]
    assert stamped["read_at"] is not None
    await world.net.call("POST", f"/v1/notifications/{first['id']}/read", world.partner)
    (again,) = [r for r in await world.rows(world.partner) if r["id"] == first["id"]]
    assert again["read_at"] == stamped["read_at"]  # set once

    feed = await world.feed(world.partner)
    assert feed["unread_count"] == 1
    response = await world.net.call("POST", "/v1/notifications/read-all", world.partner)
    assert response.status_code == 200, response.text
    assert all(r["read_at"] is not None for r in await world.rows(world.partner))
    assert (await world.feed(world.partner))["unread_count"] == 0
    # Spec drift (TASK-993): SPEC-013 AC-6 says reading is not audited; C16 §7 lists
    # `notification.read` (TASK-028's decision under AGENTS.md #3). C16 is tested.
    assert "notification.read" in await world.actions("notification.read")
    assert second["read_at"] is None  # fetched before read-all; rows are otherwise immutable


async def test_ac6_rows_are_immutable_except_read_at(world: World) -> None:
    """The app role may set `read_at` and nothing else, and may never delete a row."""

    async def may(sql: str, *args: object) -> bool:
        return bool(await world.seed.value(sql, *args))

    columns = [
        str(r["column_name"])
        for r in await world.seed.rows(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'notifications'"
        )
    ]
    updatable = {
        c
        for c in columns
        if await may("SELECT has_column_privilege('abacus_app', 'notifications', $1, 'UPDATE')", c)
    }
    assert updatable == {"read_at"}
    assert not await may("SELECT has_table_privilege('abacus_app', 'notifications', 'DELETE')")


# --- SPEC-013 AC-7 and P-01 AC 3.1.x: the API returns kinds and references ---------------------


async def test_ac7_the_feed_returns_kinds_and_references_for_the_spa_to_render(
    world: World,
) -> None:
    await world.relay(world.mention(world.manager))
    (item,) = cast(list[Json], (await world.feed(world.manager))["items"])
    assert set(item) == {
        "id",
        "kind",
        "category",
        "created_at",
        "read",
        "actor",
        "subject",
        "engagement_id",
        "facts",
        "inline_actions",
        "pending",
    }
    assert (item["kind"], item["category"], item["read"]) == ("mention", "mention", False)
    assert item["subject"] == {"type": "request_item", "id": str(world.site.item_id)}
    assert item["engagement_id"] == str(world.site.engagement_id)
    # INV-5: the human who mentioned is the actor.
    assert item["actor"] == {"kind": "human", "user_id": str(world.partner.user_id)}
    assert item["inline_actions"] == []


async def test_ac3_1_1_the_feed_answers_not_found_while_v2_is_off(net: Net) -> None:
    tenant = await net.seed.firm()
    await _flags(net.seed, tenant, v2=False)
    who = await net.seed.person(tenant)
    for path in (FEED, PREFERENCES):
        response = await net.call("GET", path, who)
        assert (response.status_code, response.json()) == (404, NOT_FOUND), path


async def test_ac3_1_2_tabs_filter_by_category_and_counts_are_unread(world: World) -> None:
    await world.relay(world.uploaded())
    await world.relay(world.mention(world.partner))
    await world.relay(world.event("budget.anomaly"))  # the partner is a lead: system category
    all_ = await world.feed(world.partner)
    kinds = {str(cast(Json, i)["kind"]) for i in cast(list[object], all_["items"])}
    assert kinds == {"client_uploaded", "mention", "budget.anomaly"}
    mentions = await world.feed(world.partner, tab="mentions")
    assert [cast(Json, i)["kind"] for i in cast(list[object], mentions["items"])] == ["mention"]
    activity = await world.feed(world.partner, tab="client_activity")
    assert [cast(Json, i)["kind"] for i in cast(list[object], activity["items"])] == [
        "client_uploaded"
    ]
    assert all_["counts"] == {"approvals": 0, "mentions": 1, "client_activity": 1}
    assert all_["unread_count"] == 3


@pytest.mark.xfail(
    strict=True,
    reason=(
        "P-01-T06 acceptance (live rows d, e, g resolve with facts) and AC 3.1.2/3.1.3: no kind "
        "registers a facts or pending resolver yet, so a client upload lists with empty facts, "
        "never pending, outside Approvals and without Accept/Return; TASK-406 defers the wiring "
        "to P-01-T16. Recorded in "
        "work/tasks/TASK-993-notifications-binder-independent-tests.md (#380)"
    ),
)
async def test_ac3_1_2_a_client_upload_waits_in_approvals_with_facts_and_inline_actions(
    world: World,
) -> None:
    await world.relay(world.uploaded())
    feed = await world.feed(world.manager, tab="approvals")
    (item,) = cast(list[Json], feed["items"])
    assert item["pending"] is True
    assert item["inline_actions"] == ["accept_document", "return_document"]
    assert (
        cast(Json, item["facts"]).get("item_status") == "Uploaded \u2013 needs review"
    )  # status vocabulary
    assert cast(Json, feed["counts"])["approvals"] == 1


async def test_inv1_inv5_an_agent_originated_row_reads_agent_and_offers_nothing(
    world: World,
) -> None:
    """The engagement agent's digest (an agent kind) goes to the partner and managers; its row's
    actor is the agent, never a person, and it offers no inline action."""
    await world.relay(world.event("agent.digest", overdue=2, sent=1, drafted=1))
    assert await world.recipients() == {world.partner.user_id, world.manager.user_id}
    (item,) = cast(list[Json], (await world.feed(world.partner))["items"])
    assert item["kind"] == "agent.digest"
    assert cast(Json, item["actor"])["kind"] == "agent"
    assert item["inline_actions"] == []


# --- P-01 AC 4.1.4 and SPEC-013 AC-10: the 30-day window and the 180-day purge -----------------


async def _aged(world: World, who: Person, days: int) -> uuid.UUID:
    row_id = uuid.uuid4()
    await world.seed.run(
        "INSERT INTO notifications (id, tenant_id, recipient_user_id, kind, event_id, "
        "engagement_id, subject_type, subject_id, created_at, category) VALUES ($1, $2, $3, "
        "'engagement_member.added', $4, $5, 'engagement', $5, now() - make_interval(days => $6), "
        "'other')",
        row_id,
        world.tenant,
        who.user_id,
        uuid.uuid4(),
        world.site.engagement_id,
        days,
    )
    return row_id


async def test_ac4_1_4_rows_older_than_30_days_are_neither_shown_nor_counted(
    world: World,
) -> None:
    recent = await _aged(world, world.senior, 29)
    await _aged(world, world.senior, 31)
    feed = await world.feed(world.senior)
    assert _ids(feed) == [str(recent)]
    assert feed["unread_count"] == 1


async def test_ac10_the_daily_purge_deletes_rows_older_than_180_days(world: World) -> None:
    kept = await _aged(world, world.senior, 179)
    gone = await _aged(world, world.senior, 181)
    stop = asyncio.Event()
    job = asyncio.create_task(notifications.run_purge_job(stop))
    try:
        for _ in range(100):
            remaining = {r["id"] for r in await world.rows(world.senior)}
            if gone not in remaining:
                break
            await asyncio.sleep(0.1)
    finally:
        stop.set()
        await job
    assert {r["id"] for r in await world.rows(world.senior)} == {kept}


# --- P-01 AC 4.1.1: preferences are the caller's own --------------------------------------------


def _choices(body: Json) -> dict[str, tuple[bool, bool]]:
    return {
        str(cast(Json, i)["kind"]): (bool(cast(Json, i)["in_app"]), bool(cast(Json, i)["email"]))
        for i in cast(list[object], body["items"])
    }


async def test_ac4_1_1_every_registered_kind_with_its_default(world: World) -> None:
    response = await world.net.call("GET", PREFERENCES, world.senior)
    assert response.status_code == 200, response.text
    choices = _choices(cast(Json, response.json()))
    assert set(choices) == set(notifications.registered())
    # Email on by default for mention (inferred, P-01) and for an Accrued-side incident, which
    # Q-02 §4 says is emailed "even when digests are on" (Q-02-T30), and for a wall's approval
    # request to its named partner (G-01 §4.7, G-01-T09); every other kind is off.
    # G-02-T02 (G-02 section 4.8): governance's approval requests and incident deadline too.
    emailed = {
        "mention",
        "incident_from_accrued",
        "wall_approval_requested",
        "ai_policy_approval_requested",
        "incident_decision_requested",
        "incident_deadline_approaching",
        # P-07-T47 (DEC-540): the independence reminder goes by email by default.
        "independence_reminder",
    }
    assert {k: choices[k] for k in emailed} == dict.fromkeys(emailed, (True, True))
    assert {k: v for k, v in choices.items() if k not in emailed} == dict.fromkeys(
        set(choices) - emailed, (True, False)
    )


async def test_ac4_1_1_a_change_is_the_callers_own_and_audited(world: World) -> None:
    body = {"items": [{"kind": "mention", "in_app": True, "email": False}]}
    response = await world.net.call("PUT", PREFERENCES, world.senior, body=body)
    assert response.status_code == 200, response.text
    assert _choices(cast(Json, response.json()))["mention"] == (True, False)
    theirs = await world.net.call("GET", PREFERENCES, world.partner)
    assert _choices(cast(Json, theirs.json()))["mention"] == (True, True)
    changes = await world.seed.rows(
        "SELECT actor_id, target_id FROM audit_events WHERE tenant_id = $1 AND action = "
        "'notification_preference.changed'",
        world.tenant,
    )
    # Spec drift (TASK-993): P-01 AC 4.1.1 names `notification_preference.updated`; C16 §7 names
    # `.changed`, which is what C16 v1 froze. C16 is tested.
    assert [(str(r["actor_id"]), str(r["target_id"])) for r in changes] == [
        (str(world.senior.user_id), str(world.senior.user_id))
    ]
    await world.net.call("PUT", PREFERENCES, world.senior, body=body)  # unchanged: no audit
    assert len(await world.actions("notification_preference.")) == 1


async def test_ac4_1_1_nobody_can_set_another_persons_preferences(world: World) -> None:
    """OWN only: the body cannot name a person, an item that tries changes nobody else's
    choice, and no route takes another person's id."""
    named: Json = {"user_id": str(world.partner.user_id), "items": []}
    response = await world.net.call("PUT", PREFERENCES, world.senior, body=named)
    assert response.status_code == 422, response.text
    sneaky = {
        "items": [
            {
                "kind": "mention",
                "in_app": False,
                "email": False,
                "user_id": str(world.partner.user_id),
            }
        ]
    }
    response = await world.net.call("PUT", PREFERENCES, world.senior, body=sneaky)
    assert response.status_code in {200, 422}, response.text
    for path in (
        f"/v1/users/{world.partner.user_id}/notification-preferences",
        f"{PREFERENCES}/{world.partner.user_id}",
    ):
        response = await world.net.call("PUT", path, world.senior, body={"items": []})
        assert response.status_code in {404, 405}, path
    theirs = await world.net.call("GET", PREFERENCES, world.partner)
    assert _choices(cast(Json, theirs.json()))["mention"] == (True, True)
    stored = await world.seed.rows(
        "SELECT user_id FROM notification_preferences WHERE tenant_id = $1", world.tenant
    )
    assert {r["user_id"] for r in stored} <= {world.senior.user_id}


async def test_ac4_1_1_an_unknown_or_repeated_kind_is_refused_and_nothing_is_saved(
    world: World,
) -> None:
    for items in (
        [
            {"kind": "mention", "in_app": False, "email": False},
            {"kind": "no_such_kind", "in_app": True, "email": True},
        ],
        [
            {"kind": "mention", "in_app": False, "email": False},
            {"kind": "mention", "in_app": True, "email": True},
        ],
    ):
        response = await world.net.call("PUT", PREFERENCES, world.senior, body={"items": items})
        assert response.status_code == 422, response.text
        assert response.json()["detail"] == "unknown_notification_kind"
    assert (
        await world.seed.value(
            "SELECT count(*) FROM notification_preferences WHERE tenant_id = $1", world.tenant
        )
        == 0
    )


async def test_ac4_1_1_a_kind_off_in_the_app_is_neither_shown_nor_counted(world: World) -> None:
    await world.relay(world.uploaded())
    await world.relay(world.mention(world.senior))
    body = {"items": [{"kind": "client_uploaded", "in_app": False, "email": False}]}
    assert (await world.net.call("PUT", PREFERENCES, world.senior, body=body)).status_code == 200
    feed = await world.feed(world.senior)
    assert [cast(Json, i)["kind"] for i in cast(list[object], feed["items"])] == ["mention"]
    assert feed["unread_count"] == 1
    assert feed["counts"] == {"approvals": 0, "mentions": 1, "client_activity": 0}


# --- P-01 AC 4.1.2, AC 4.1.3 and INV-4: the email rules ------------------------------------------


async def test_ac4_1_2_email_follows_the_kinds_default_and_the_persons_choice(
    net: Net, started: list[object]
) -> None:
    world = await _world(net, email=True)
    await world.relay(world.event("engagement_member.added", user_id=world.senior.user_id))
    assert await world.deliveries() == []  # email is off by default for this kind
    off = {"items": [{"kind": "mention", "in_app": True, "email": False}]}
    assert (await net.call("PUT", PREFERENCES, world.senior, body=off)).status_code == 200
    await world.relay(world.mention(world.manager, world.senior))
    assert await world.deliveries() == [(world.manager.user_id, "queued")]
    assert len(started) == 1


async def test_ac4_1_2_the_kill_switch_off_queues_nothing_and_reads_suppressed(
    net: Net, started: list[object]
) -> None:
    world = await _world(net, email=False)
    await world.relay(world.mention(world.manager))
    assert await world.deliveries() == [(world.manager.user_id, "suppressed")]
    assert started == []
    assert await world.actions("notification_delivery.") == ["notification_delivery.suppressed"]


async def test_inv4_notification_email_goes_to_firm_staff_only(
    net: Net, started: list[object]
) -> None:
    """A client user may be mentioned in a comment they can read (SPEC-032) and so has an in-app
    row, but notification email is sent only to firm staff."""
    world = await _world(net, email=True)
    await world.relay(world.mention(world.client, world.manager))
    assert world.client.user_id in await world.recipients()
    assert await world.deliveries() == [(world.manager.user_id, "queued")]
    assert len(started) == 1


@pytest.mark.usefixtures("worker")
async def test_ac4_1_2_ac4_1_3_one_email_on_the_sink_with_no_restricted_fact(
    net: Net, temporal: Client, tmp_path: Path
) -> None:
    world = await _world(net, email=True, synthetic=True)
    await import_platform_version(
        "staff-p01t14", "notification.client_uploaded", "en-US", SUBJECT, BODY, VARIABLES
    )
    on = {"items": [{"kind": "client_uploaded", "in_app": True, "email": True}]}
    assert (await net.call("PUT", PREFERENCES, world.manager, body=on)).status_code == 200
    upload = world.uploaded()
    await world.relay(upload)
    await world.relay(upload)  # redelivered: still one email
    (notification,) = await world.rows(world.manager)
    handle = temporal.get_workflow_handle(
        notifications.notification_email_id(str(world.tenant), str(notification["id"])),
        result_type=str,
    )
    assert await handle.result() == "sent"

    (mail,) = LocalMailboxReader(tmp_path / "mailbox").messages()
    assert on_sink(mail.to) and f"+{world.tenant.hex[:8]}@" in mail.to  # synthetic: the sink
    assert "hannah.leclerc@example.test" not in mail.to
    lines = mail.body.splitlines()
    assert lines[0] == "Hi Hannah,"
    assert lines[2].startswith("The client uploaded a file on ")
    link = lines[5].removeprefix("Open it: ")
    assert link.startswith(settings().app_base_url)
    for restricted in ("Evidence ", "Bank confirmation", "Leclerc", "example.test"):
        assert restricted not in mail.body, restricted
    assert world.site.marker not in link  # no name in the URL
    assert (await world.deliveries()) == [(world.manager.user_id, "sent")]


# --- C16 and P-01-T03: every registered code passes the database CHECK ---------------------------


async def test_ac_c16_every_registered_kind_passes_the_widened_database_check(
    world: World,
) -> None:
    """Each registered code is stored in `notifications` and `notification_preferences` under
    their CHECKs; codes outside the convention are refused by the database."""
    insert_row = (
        "INSERT INTO notifications (tenant_id, recipient_user_id, kind, event_id, "
        "subject_type, subject_id) VALUES ($1, $2, $3, $4, 'firm', $1)"
    )
    for code in notifications.registered():
        await world.seed.run(insert_row, world.tenant, world.senior.user_id, code, uuid.uuid4())
        await world.seed.run(
            "INSERT INTO notification_preferences (tenant_id, user_id, kind, email) "
            "VALUES ($1, $2, $3, false)",
            world.tenant,
            world.senior.user_id,
            code,
        )
    stored = await world.seed.rows(
        "SELECT kind FROM notifications WHERE tenant_id = $1", world.tenant
    )
    assert sorted(str(r["kind"]) for r in stored) == sorted(notifications.registered())
    for bad in ("a.b.c", "Mention", "client-uploaded", "_mention", "mention.", "run2"):
        with pytest.raises(asyncpg.CheckViolationError):
            await world.seed.run(insert_row, world.tenant, world.senior.user_id, bad, uuid.uuid4())
