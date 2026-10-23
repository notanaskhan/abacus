"""P-01-T12 against Postgres and Temporal (SPEC-013 AC-1, AC-7; P-01 AC 4.1.2; C16): "A mention
emails Hannah exactly once on the sink with no Restricted fact."

- Preferences: every registered kind with the person's own choice or its default; OWN only;
  an unknown or repeated kind answers 422 `unknown_notification_kind`; a change is audited.
- Email: with `notifications.email` on and Hannah's email on for `mention`, Margaret's mention
  sends one email through `communications` (`send_email`) using the published C16 template
  `notification.mention`, idempotent on (notification, email). On a synthetic firm it reaches
  the sink (F-04-T22). With the flag off (the kill switch) nothing is sent and the delivery row
  reads `suppressed`.

The fan-out and the activities run as the app role; the workflow runs on a real Temporal dev
server with the module's own worker composition.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import pytest
from temporalio.client import Client
from temporalio.worker import Worker

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.kernel.dispatch import queue_for
from abacus.kernel.flags import forget_flags
from abacus.kernel.temporal import configure_temporal_client, data_converter
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.communications.api import (
    LOCAL_SINK_DOMAIN,
    FakeSesTransport,
    configure_transport,
)
from abacus.modules.communications.templates import import_platform_version
from abacus.modules.identity.api import AuthContext
from abacus.modules.notifications import api as notifications
from abacus.modules.notifications.email import (
    record_delivery_activity,
    send_email_activity,
)
from abacus.modules.notifications.service import (
    Preference,
    UnknownNotificationKind,
    my_preferences,
    notify,
    set_my_preferences,
)
from abacus.modules.notifications.workflows import (
    DeliveryOutcome,
    NotificationEmailInput,
    notification_email_id,
)
from abacus_tools.harness.mailbox import LocalMailboxReader

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

QUEUE = f"p01t12-{uuid.uuid4().hex[:8]}"
SUBJECT = "{{kind_sentence}}"
BODY = (
    "Hi {{recipient_first_name}},\n\n{{kind_sentence}}\n\n"
    "Engagement: {{engagement_display_name}}\nOpen it: {{app_link}}\n"
)
VARIABLES = ["recipient_first_name", "kind_sentence", "engagement_display_name", "app_link"]


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_TEMPORAL_TASK_QUEUE", QUEUE)
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    configure_transport(FakeSesTransport(tmp_path / "mailbox"))
    yield
    configure_transport(None)
    notifications.configure_email_starter(None)
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


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


class World:
    def __init__(
        self,
        seed: Seeder,
        tenant: uuid.UUID,
        hannah: Person,
        margaret: Person,
        engagement: uuid.UUID,
    ) -> None:
        self.seed, self.tenant, self.hannah, self.margaret = seed, tenant, hannah, margaret
        self.engagement = engagement

    def mention(self, event_id: uuid.UUID | None = None) -> OutboxEvent:
        return OutboxEvent(
            event_id=event_id or uuid.uuid4(),
            tenant_id=self.tenant,
            event_type="comment.mentioned",
            payload={
                "comment_id": str(uuid.uuid4()),
                "request_item_id": str(uuid.uuid4()),
                "engagement_id": str(self.engagement),
                "mentioned_user_ids": [str(self.hannah.user_id)],
                "by_user": str(self.margaret.user_id),
            },
        )

    async def deliveries(self) -> list[tuple[str, str | None]]:
        rows = await self.seed.rows(
            "SELECT status, message_ref FROM notification_deliveries WHERE tenant_id = $1",
            self.tenant,
        )
        return [(str(r["status"]), r["message_ref"]) for r in rows]

    async def actions(self) -> list[str]:
        rows = await self.seed.rows(
            "SELECT action FROM audit_events WHERE tenant_id = $1 AND action LIKE "
            "'notification_deliver%' ORDER BY seq",
            self.tenant,
        )
        return [str(r["action"]) for r in rows]


async def _person(seed: Seeder, tenant: uuid.UUID, name: str, email: str) -> Person:
    who = await seed.person(tenant)
    await seed.run(
        "UPDATE users SET display_name = $2, email = $3 WHERE id = $1", who.user_id, name, email
    )
    return who


async def _world(seed: Seeder, *, email_flag: bool = True, synthetic: bool = True) -> World:
    tenant = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = $2 WHERE tenant_id = $1", tenant, synthetic)
    for flag, on in (("notifications.v2", True), ("notifications.email", email_flag)):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, $3, 'test-seed', 'P-01-T12 tests')",
            tenant,
            flag,
            "true" if on else "false",
        )
    hannah = await _person(seed, tenant, "Hannah Leclerc", "hannah.leclerc@brightwaterhale.com")
    margaret = await _person(seed, tenant, "Margaret Chen", "margaret.chen@brightwaterhale.com")
    entity = await seed.entity(tenant, "Northwind Logistics, Inc.")
    engagement = await seed.engagement(tenant, entity, margaret.user_id)
    await seed.member(engagement, margaret, "engagement_partner")
    await seed.member(engagement, hannah, "manager")
    await import_platform_version(
        "staff-p01t12", "notification.mention", "en-US", SUBJECT, BODY, VARIABLES
    )
    return World(seed, tenant, hannah, margaret, engagement)


async def _finished(temporal: Client, world: World) -> list[str]:
    rows = await world.seed.rows(
        "SELECT notification_id FROM notification_deliveries WHERE tenant_id = $1", world.tenant
    )
    outcomes: list[str] = []
    for row in rows:
        handle = temporal.get_workflow_handle(
            notification_email_id(str(world.tenant), str(row["notification_id"])),
            result_type=str,
        )
        outcomes.append(await handle.result())
    return outcomes


def _mail(tmp_path: Path) -> LocalMailboxReader:
    return LocalMailboxReader(tmp_path / "mailbox")


# --- The email channel --------------------------------------------------------------------------


@pytest.mark.usefixtures("worker")
async def test_a_mention_emails_hannah_exactly_once_on_the_sink_with_no_restricted_fact(
    seed: Seeder, temporal: Client, tmp_path: Path
) -> None:
    world = await _world(seed)
    event = world.mention()
    await notify(event)
    assert await _finished(temporal, world) == ["sent"]
    await notify(event)  # the relay delivers the event again
    assert await _finished(temporal, world) == ["sent"]

    (mail,) = _mail(tmp_path).messages()
    assert mail.to == f"hannah.leclerc+{world.tenant.hex[:8]}@{LOCAL_SINK_DOMAIN}"
    sentence = "You were mentioned in a comment on Seeded client · "
    assert mail.subject.startswith(sentence)
    # Only the four whitelisted values: a first name, the sentence, the engagement and a link.
    lines = mail.body.splitlines()
    assert lines[0] == "Hi Hannah,"
    assert lines[2].startswith(sentence)
    assert lines[4].startswith("Engagement: Seeded client · ")
    assert lines[5] == f"Open it: {settings().app_base_url}/?ov=notifications"
    assert "Leclerc" not in mail.body and "brightwaterhale.com" not in mail.body
    assert mail.code is None

    (delivery,) = await world.deliveries()
    notification = await seed.value(
        "SELECT id FROM notifications WHERE tenant_id = $1", world.tenant
    )
    assert delivery == ("sent", str(notification))
    assert await world.actions() == [
        "notification_delivery.queued",
        "notification_delivery.sent",
    ]


async def test_the_kill_switch_off_sends_nothing_and_the_row_reads_suppressed(
    seed: Seeder, tmp_path: Path
) -> None:
    world = await _world(seed, email_flag=False)
    started: list[NotificationEmailInput] = []

    async def record(given: NotificationEmailInput) -> None:
        started.append(given)

    notifications.configure_email_starter(record)
    await notify(world.mention())
    assert started == []
    assert await world.deliveries() == [("suppressed", None)]
    assert await world.actions() == ["notification_delivery.suppressed"]
    assert _mail(tmp_path).messages() == []


async def test_email_off_for_the_kind_makes_no_delivery_and_the_default_is_the_kinds(
    seed: Seeder,
) -> None:
    world = await _world(seed)
    started: list[NotificationEmailInput] = []

    async def record(given: NotificationEmailInput) -> None:
        started.append(given)

    notifications.configure_email_starter(record)
    hannah = world.hannah.context()
    await set_my_preferences(hannah, [Preference("mention", True, False)])
    await notify(world.mention())
    assert (await world.deliveries(), started) == ([], [])
    # Review assignment emails by no default: no row either.
    defaults = {p.kind: p.email for p in await my_preferences(world.margaret.context())}
    assert defaults["mention"] is True and defaults["review_assigned"] is False


async def test_a_wall_added_after_the_fan_out_stops_the_email(
    seed: Seeder, tmp_path: Path
) -> None:
    world = await _world(seed)
    started: list[NotificationEmailInput] = []

    async def record(given: NotificationEmailInput) -> None:
        started.append(given)

    notifications.configure_email_starter(record)
    await notify(world.mention())
    (given,) = started
    client = await seed.value("SELECT client_id FROM engagements WHERE id = $1", world.engagement)
    await seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        world.tenant,
        world.hannah.user_id,
        client,
        world.margaret.user_id,
    )
    outcome = await send_email_activity(given)
    assert outcome == "suppressed"
    assert (
        await record_delivery_activity(
            DeliveryOutcome(given.tenant_id, given.notification_id, outcome)
        )
        == "suppressed"
    )
    assert await world.deliveries() == [("suppressed", None)]
    assert _mail(tmp_path).messages() == []
    # Settled once: running the activities again sends and writes nothing more.
    assert await send_email_activity(given) == "suppressed"
    assert await world.actions() == [
        "notification_delivery.queued",
        "notification_delivery.suppressed",
    ]


async def test_no_published_template_fails_the_delivery_without_sending(
    seed: Seeder, tmp_path: Path
) -> None:
    world = await _world(seed)
    started: list[NotificationEmailInput] = []

    async def record(given: NotificationEmailInput) -> None:
        started.append(given)

    notifications.configure_email_starter(record)
    await notify(world.mention())
    (given,) = started
    await seed.run(
        "UPDATE notifications SET kind = 'engagement_member.added' WHERE tenant_id = $1",
        world.tenant,
    )
    outcome = await send_email_activity(given)
    assert outcome == "failed"
    await record_delivery_activity(
        DeliveryOutcome(given.tenant_id, given.notification_id, outcome)
    )
    assert await world.deliveries() == [("failed", None)]
    assert _mail(tmp_path).messages() == []


# --- Preferences (OWN) --------------------------------------------------------------------------


async def test_preferences_are_the_callers_own_with_defaults_and_audited_changes(
    seed: Seeder,
) -> None:
    world = await _world(seed)
    hannah, margaret = world.hannah.context(), world.margaret.context()
    before = {p.kind: (p.in_app, p.email) for p in await my_preferences(hannah)}
    assert before["mention"] == (True, True)
    assert set(before) == set(notifications.registered())

    after = await set_my_preferences(
        hannah, [Preference("mention", True, False), Preference("client_uploaded", False, True)]
    )
    mine = {p.kind: (p.in_app, p.email) for p in after}
    assert mine["mention"] == (True, False) and mine["client_uploaded"] == (False, True)
    theirs = {p.kind: (p.in_app, p.email) for p in await my_preferences(margaret)}
    assert theirs["mention"] == (True, True) and theirs["client_uploaded"] == (True, False)

    await set_my_preferences(hannah, [Preference("mention", True, False)])  # unchanged
    changes = await seed.rows(
        "SELECT actor_id, target_id, after_ref FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'notification_preference.changed'",
        world.tenant,
    )
    assert [(r["actor_id"], r["target_id"]) for r in changes] == [
        (str(world.hannah.user_id), str(world.hannah.user_id))
    ]


@pytest.mark.parametrize(
    "items",
    [
        [Preference("not_a_kind", True, True)],
        [Preference("mention", True, True), Preference("mention", True, False)],
    ],
)
async def test_an_unknown_or_repeated_kind_is_refused_and_nothing_changes(
    seed: Seeder, items: list[Preference]
) -> None:
    world = await _world(seed)
    hannah: AuthContext = world.hannah.context()
    with pytest.raises(UnknownNotificationKind):
        await set_my_preferences(hannah, items)
    stored = cast(
        int,
        await seed.value(
            "SELECT count(*) FROM notification_preferences WHERE tenant_id = $1", world.tenant
        ),
    )
    assert stored == 0
