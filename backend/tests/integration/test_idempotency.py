"""P-06-T06 against Postgres (migration 0099): "A retried publish returns the stored response and
dispatches no second email." The same key with another request is refused; held events wait for
their time and their grant."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from abacus.kernel.db import TenantContext, configure_engine, configure_relay_engine
from abacus.kernel.uow import DomainEvent, Target, uow
from abacus.kernel.uow import relay as relay_module
from abacus.kernel.uow.idempotency import IdempotencyKeyReused, idempotent
from abacus.kernel.uow.relay import InMemoryPublisher, relay_once

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio


class ProbeSent(DomainEvent):
    event_type = "probe.sent"


async def test_a_retry_replays_and_a_different_request_is_refused(
    migrated_db: MigratedDatabase,
) -> None:
    configure_engine(migrated_db.app_url)
    tenant = await Seeder(migrated_db.superuser_dsn).firm()
    ctx = TenantContext(tenant, "human", str(uuid.uuid4()))
    sends: list[int] = []

    async def publish() -> tuple[int, dict[str, object]]:
        sends.append(1)  # stands for the email a publish dispatches
        return 200, {"binder_id": "b-1", "status": "published"}

    body = {"binder_id": "b-1"}
    first = await idempotent(
        ctx, route="binder.publish", key="key-00000001", body=body, run=publish
    )
    again = await idempotent(
        ctx, route="binder.publish", key="key-00000001", body=body, run=publish
    )
    assert (first.replayed, again.replayed) == (False, True)
    assert again.body == first.body and sends == [1]
    with pytest.raises(IdempotencyKeyReused):
        await idempotent(
            ctx, route="binder.publish", key="key-00000001", body={"binder_id": "b-2"}, run=publish
        )
    assert sends == [1]


async def test_held_events_wait_for_their_time_and_their_grant(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_engine(migrated_db.app_url)
    configure_relay_engine(migrated_db.relay_url)
    tenant = await Seeder(migrated_db.superuser_dsn).firm()
    ctx = TenantContext(tenant, "human", str(uuid.uuid4()))
    later, held, void = ProbeSent(), ProbeSent(), ProbeSent()
    granted, voided = uuid.uuid4(), uuid.uuid4()
    async with uow(ctx) as tx:
        tx.record("probe.sent", target=Target("probe", uuid.uuid4()))
        tx.emit(later, not_before=datetime.now(UTC) + timedelta(hours=1))
        tx.emit(held, grant_id=granted)
        tx.emit(void, grant_id=voided)

    async def consume(_tenant: uuid.UUID, grant: uuid.UUID) -> bool:
        return grant == granted

    monkeypatch.setattr(relay_module, "_GRANT_CONSUMER", [consume])
    publisher = InMemoryPublisher()
    await relay_once(publisher)
    assert [e.event_id for e in publisher.published] == [held.event_id]
