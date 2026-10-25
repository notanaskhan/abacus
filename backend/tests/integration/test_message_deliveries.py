"""Q-01-T46 against Postgres (migration 0104): SES bounce and complaint events create delivery
rows and suppress the next send to that address hash, with no clear-text address in rows,
events or audit. Everything runs as the app role through the module's own functions."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import Target, uow
from abacus.modules.communications.deliveries import (
    QueuedEvent,
    configure_ses_event_queue,
    drain_ses_events,
    is_suppressed,
    parse_ses_event,
    record_ses_event,
    send_email,
)
from abacus.modules.communications.transport import configure_transport

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

ADDRESS = "claire.feld@example.test"


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()
    configure_ses_event_queue(None)
    configure_transport(None)


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


def _envelope(
    tenant: uuid.UUID,
    message: uuid.UUID,
    kind: str,
    *,
    bounce_type: str = "Permanent",
    event_id: str | None = None,
) -> str:
    detail: dict[str, object] = {
        "eventType": kind,
        "mail": {"tags": {"tenant_id": [str(tenant)], "message_id": [str(message)]}},
    }
    if kind == "Bounce":
        detail["bounce"] = {
            "bounceType": bounce_type,
            "bouncedRecipients": [{"emailAddress": ADDRESS}],
        }
    if kind == "Complaint":
        detail["complaint"] = {"complainedRecipients": [{"emailAddress": ADDRESS}]}
    return json.dumps(
        {
            "id": event_id or str(uuid.uuid4()),
            "time": "2026-10-23T14:05:00Z",
            "source": "aws.ses",
            "detail": detail,
        }
    )


@dataclass
class RecordingTransport:
    sent: list[str] = field(default_factory=list[str])

    def send(self, *, to: str, **_: object) -> None:
        self.sent.append(to)


@dataclass
class MemoryQueue:
    messages: list[QueuedEvent]
    deleted: list[str] = field(default_factory=list[str])

    def receive(self, limit: int) -> Sequence[QueuedEvent]:
        batch, self.messages = self.messages[:limit], self.messages[limit:]
        return batch

    def delete(self, receipts: Sequence[str]) -> None:
        self.deleted.extend(receipts)


@pytest.mark.parametrize(
    ("kind", "event", "bounce"),
    [
        ("Delivery", "delivered", None),
        ("Bounce", "bounced", "permanent"),
        ("Complaint", "complained", None),
        ("Reject", "rejected", None),
        ("DeliveryDelay", "delayed", None),
    ],
)
def test_q01t46_ses_events_parse_from_their_eventbridge_envelope(
    kind: str, event: str, bounce: str | None
) -> None:
    tenant, message = uuid.uuid4(), uuid.uuid4()
    parsed = parse_ses_event(_envelope(tenant, message, kind))
    assert parsed is not None
    assert (parsed.tenant_id, parsed.message_id, parsed.event, parsed.bounce_kind) == (
        tenant,
        message,
        event,
        bounce,
    )


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        json.dumps({"id": "x", "time": "2026-10-23T14:05:00Z", "detail": {"eventType": "Open"}}),
        _envelope(uuid.uuid4(), uuid.uuid4(), "Send"),
        json.dumps({"id": "x", "time": "2026-10-23T14:05:00Z", "detail": {"eventType": "Bounce"}}),
        _envelope(uuid.uuid4(), uuid.uuid4(), "Bounce", event_id="bad id with spaces"),
    ],
    # Fixed ids: the envelopes carry fresh UUIDs, and every pytest-xdist worker must collect the
    # same test names (DEC-335).
    ids=["not_json", "array", "open", "send", "bounce_untagged", "bad_event_id"],
)
def test_q01t46_anything_else_is_not_an_event_of_ours(raw: str) -> None:
    assert parse_ses_event(raw) is None


async def _count(seed: Seeder, sql: str, *args: object) -> int:
    return cast(int, await seed.value(sql, *args))


async def test_q01t46_a_permanent_bounce_records_once_and_suppresses_the_next_send(
    seed: Seeder,
) -> None:
    tenant, message = await seed.firm(), uuid.uuid4()
    event = parse_ses_event(_envelope(tenant, message, "Bounce", event_id="ev-bounce-1"))
    assert event is not None
    assert await record_ses_event(event)
    assert not await record_ses_event(event)  # SQS redelivered it
    rows = "SELECT count(*) FROM message_deliveries WHERE provider_event_id = $1"
    assert await _count(seed, rows, "ev-bounce-1") == 1
    assert await is_suppressed(tenant, ADDRESS)
    assert await is_suppressed(tenant, "  Claire.Feld@Example.TEST ")
    assert not await is_suppressed(await seed.firm(), ADDRESS)  # per firm
    outbox = "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'message.bounced'"
    assert await _count(seed, outbox, tenant) == 1
    mailer = RecordingTransport()
    configure_transport(mailer)
    assert not await send_email(
        tenant_id=tenant, message_id=uuid.uuid4(), to=ADDRESS, subject="s", body="b"
    )
    assert mailer.sent == []


async def test_q01t46_a_complaint_suppresses_and_a_transient_bounce_does_not(
    seed: Seeder,
) -> None:
    complained, bounced = await seed.firm(), await seed.firm()
    complaint = parse_ses_event(_envelope(complained, uuid.uuid4(), "Complaint"))
    transient = parse_ses_event(
        _envelope(bounced, uuid.uuid4(), "Bounce", bounce_type="Transient")
    )
    assert complaint is not None and transient is not None
    assert await record_ses_event(complaint)
    assert await record_ses_event(transient)
    assert await is_suppressed(complained, ADDRESS)
    assert not await is_suppressed(bounced, ADDRESS)
    mailer = RecordingTransport()
    configure_transport(mailer)
    assert await send_email(
        tenant_id=bounced, message_id=uuid.uuid4(), to=ADDRESS, subject="s", body="b"
    )
    assert mailer.sent == [ADDRESS]


async def test_q01t46_no_clear_text_address_is_stored_emitted_or_audited(seed: Seeder) -> None:
    tenant = await seed.firm()
    event = parse_ses_event(_envelope(tenant, uuid.uuid4(), "Complaint"))
    assert event is not None
    await record_ses_event(event)
    for sql in (
        "SELECT string_agg(row_to_json(d)::text, '') FROM message_deliveries d "
        "WHERE tenant_id = $1",
        "SELECT string_agg(encode(address_hash, 'escape'), '') FROM email_suppressions "
        "WHERE tenant_id = $1",
        "SELECT string_agg(payload::text, '') FROM outbox WHERE tenant_id = $1",
        "SELECT string_agg(row_to_json(a)::text, '') FROM audit_events a WHERE tenant_id = $1",
    ):
        dumped = cast(str | None, await seed.value(sql, tenant)) or ""
        assert "claire" not in dumped.casefold()


async def test_q01t46_the_drain_records_and_deletes_and_leaves_failures_queued(
    seed: Seeder, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant = await seed.firm()
    good = _envelope(tenant, uuid.uuid4(), "Delivery")
    ours_failing = _envelope(tenant, uuid.uuid4(), "Bounce", event_id="ev-fails")
    queue = MemoryQueue(
        [
            QueuedEvent("r-good", good),
            QueuedEvent("r-junk", "not an event"),
            QueuedEvent("r-fail", ours_failing),
        ]
    )
    configure_ses_event_queue(queue)
    import abacus.modules.communications.deliveries as deliveries

    real = deliveries.record_ses_event

    async def flaky(event: deliveries.SesEvent) -> bool:
        if event.provider_event_id == "ev-fails":
            raise RuntimeError("database away")
        return await real(event)

    monkeypatch.setattr(deliveries, "record_ses_event", flaky)
    assert await drain_ses_events() == 1
    assert sorted(queue.deleted) == ["r-good", "r-junk"]


async def test_q01t46_deliveries_are_insert_only_for_the_app(seed: Seeder) -> None:
    tenant = await seed.firm()
    event = parse_ses_event(_envelope(tenant, uuid.uuid4(), "Delivery"))
    assert event is not None
    await record_ses_event(event)
    with pytest.raises(DBAPIError):
        async with uow(TenantContext(tenant, "system", "probe")) as tx:
            await tx.session.execute(text("UPDATE message_deliveries SET event = 'bounced'"))
            tx.record("message.delivered", target=Target("message", tenant))
