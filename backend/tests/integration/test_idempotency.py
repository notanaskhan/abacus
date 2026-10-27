"""P-06-T06 against Postgres (migration 0099): "A retried publish returns the stored response and
dispatches no second email." The same key with another request is refused; held events wait for
their time and their grant."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.db import (
    TenantContext,
    configure_engine,
    configure_relay_engine,
    tenant_connection,
)
from abacus.kernel.uow import DomainEvent, Target, uow
from abacus.kernel.uow import relay as relay_module
from abacus.kernel.uow.idempotency import (
    PENDING_RECLAIM_S,
    IdempotencyInProgress,
    IdempotencyKeyReused,
    idempotent,
    request_hash,
)
from abacus.kernel.uow.relay import InMemoryPublisher, relay_once

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
ATTEMPT = "retry-publish-0001"  # an Idempotency-Key value (not a credential)
REWRITE = "rewrite-attempt-0001"  # an Idempotency-Key value (not a credential)


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
    first = await idempotent(ctx, route="binder.publish", key=ATTEMPT, body=body, run=publish)
    again = await idempotent(ctx, route="binder.publish", key=ATTEMPT, body=body, run=publish)
    assert (first.replayed, again.replayed) == (False, True)
    assert again.body == first.body and sends == [1]
    with pytest.raises(IdempotencyKeyReused):
        await idempotent(
            ctx, route="binder.publish", key=ATTEMPT, body={"binder_id": "b-2"}, run=publish
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

    # P-04-T10: the relay hands the consumer the event and its payload digest as well.
    async def consume(
        _tenant: uuid.UUID, grant: uuid.UUID, _event: uuid.UUID, _digest: str
    ) -> bool:
        return grant == granted

    monkeypatch.setattr(relay_module, "_GRANT_CONSUMER", [consume])
    publisher = InMemoryPublisher()
    # The database is shared across tests: relay until nothing more is due, then look only at
    # this test's events.
    ours = {later.event_id, held.event_id, void.event_id}
    for _ in range(50):
        result = await relay_once(publisher, batch=200)
        if result.published + result.failed == 0:
            break
    assert [e.event_id for e in publisher.published if e.event_id in ours] == [held.event_id]


async def test_a_key_in_use_is_in_progress_and_a_failed_run_releases_it(
    migrated_db: MigratedDatabase,
) -> None:
    """P-04-T22 re-review M1 (0214, DEC-507): the key is claimed before the effect runs, without
    holding a connection. While the first runs, the same request is told it is in progress and
    another is refused; a run that fails releases the key, and a crashed claim is reclaimed."""
    configure_engine(migrated_db.app_url)
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    ctx = TenantContext(tenant, "human", str(uuid.uuid4()))
    key, body = "claim-probe-0001", {"binder_id": "b-1"}
    seen: list[str] = []

    async def first() -> tuple[int, dict[str, object]]:
        with pytest.raises(IdempotencyInProgress):
            await idempotent(ctx, route="binder.publish", key=key, body=body, run=never)
        with pytest.raises(IdempotencyKeyReused):
            await idempotent(ctx, route="binder.publish", key=key, body={"x": 1}, run=never)
        seen.append("first")
        return 200, {"ok": True}

    async def never() -> tuple[int, dict[str, object]]:
        raise AssertionError("a second run")

    done = await idempotent(ctx, route="binder.publish", key=key, body=body, run=first)
    assert (done.replayed, seen) == (False, ["first"])

    async def broken() -> tuple[int, dict[str, object]]:
        raise RuntimeError("the effect failed")

    async def works() -> tuple[int, dict[str, object]]:
        return 201, {"id": "x"}

    failing = "claim-probe-0002"
    with pytest.raises(RuntimeError):
        await idempotent(ctx, route="binder.publish", key=failing, body=body, run=broken)
    retried = await idempotent(ctx, route="binder.publish", key=failing, body=body, run=works)
    assert (retried.status_code, retried.replayed) == (201, False)

    # A claim left pending by a crash blocks the key only until it is reclaimed.
    crashed = "claim-probe-0003"
    await seed.run(
        "INSERT INTO idempotency_keys (tenant_id, actor_id, route, key, request_sha256, "
        "created_at) VALUES ($1, $2, 'binder.publish', $3, $4, "
        "clock_timestamp() - make_interval(secs => $5))",
        tenant,
        ctx.actor_id,
        crashed,
        request_hash(body),
        PENDING_RECLAIM_S + 1,
    )
    reclaimed = await idempotent(ctx, route="binder.publish", key=crashed, body=body, run=works)
    assert (reclaimed.status_code, reclaimed.replayed) == (201, False)
    # Another actor's or firm's row with the same key is never theirs.
    other = TenantContext(tenant, "human", str(uuid.uuid4()))
    mine = await idempotent(other, route="binder.publish", key=key, body={"y": 2}, run=works)
    assert mine.replayed is False


async def test_a_claim_answers_and_releases_only_for_itself(migrated_db: MigratedDatabase) -> None:
    """Re-review M1 (0214, DEC-507): a run whose claim was taken over neither writes its answer
    into the claim that took it nor releases it."""
    configure_engine(migrated_db.app_url)
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    ctx = TenantContext(tenant, "human", str(uuid.uuid4()))
    body = {"binder_id": "b-1"}
    age = "UPDATE idempotency_keys SET created_at = created_at - interval '2 hours' WHERE key = $1"

    async def answer_b() -> tuple[int, dict[str, object]]:
        return 200, {"by": "b"}

    taken = "claim-token-0001"

    async def stale_a() -> tuple[int, dict[str, object]]:
        await seed.run(age, taken)  # A outlives the reclaim window; B takes the key over
        b = await idempotent(ctx, route="binder.publish", key=taken, body=body, run=answer_b)
        assert b.replayed is False
        return 200, {"by": "a"}

    await idempotent(ctx, route="binder.publish", key=taken, body=body, run=stale_a)
    stored = await seed.value("SELECT response->>'by' FROM idempotency_keys WHERE key = $1", taken)
    assert stored == "b"

    released = "claim-token-0002"

    async def stale_then_fails() -> tuple[int, dict[str, object]]:
        # Another claim takes the key over (as the claim upsert would) and is still running.
        await seed.run(
            "UPDATE idempotency_keys SET claim_id = gen_random_uuid(), "
            "created_at = clock_timestamp() WHERE key = $1",
            released,
        )
        raise RuntimeError("A fails late")

    with pytest.raises(RuntimeError):
        await idempotent(
            ctx, route="binder.publish", key=released, body=body, run=stale_then_fails
        )
    with pytest.raises(IdempotencyInProgress):  # the live claim was not released by A
        await idempotent(ctx, route="binder.publish", key=released, body=body, run=answer_b)


async def test_a_failure_after_the_effect_committed_keeps_the_claim(
    migrated_db: MigratedDatabase,
) -> None:
    """Re-review M2: once a unit of work inside the run reached its commit, a later failure
    doesn't free the key, so a retry can't run the effect again."""
    configure_engine(migrated_db.app_url)
    tenant = await Seeder(migrated_db.superuser_dsn).firm()
    ctx = TenantContext(tenant, "human", str(uuid.uuid4()))
    body = {"binder_id": "b-1"}

    async def commits_then_fails() -> tuple[int, dict[str, object]]:
        async with uow(ctx) as tx:
            tx.record("binder.published", target=Target("firm", tenant))
        raise RuntimeError("after the commit")

    async def again() -> tuple[int, dict[str, object]]:
        raise AssertionError("the effect ran twice")

    attempt = "after-commit-0001"
    with pytest.raises(RuntimeError):
        await idempotent(
            ctx, route="binder.publish", key=attempt, body=body, run=commits_then_fails
        )
    with pytest.raises(IdempotencyInProgress):
        await idempotent(ctx, route="binder.publish", key=attempt, body=body, run=again)


async def test_a_completed_answer_is_never_rewritten(migrated_db: MigratedDatabase) -> None:
    """Re-review L1 (0214's trigger): the app role may only claim, fill once or release."""
    configure_engine(migrated_db.app_url)
    tenant = await Seeder(migrated_db.superuser_dsn).firm()
    ctx = TenantContext(tenant, "human", str(uuid.uuid4()))

    async def done() -> tuple[int, dict[str, object]]:
        return 200, {"ok": True}

    await idempotent(ctx, route="binder.publish", key=REWRITE, body={}, run=done)
    with pytest.raises(DBAPIError):
        async with tenant_connection(ctx) as conn:
            await conn.execute(
                text(
                    "UPDATE idempotency_keys SET response = '{\"ok\": false}' WHERE key = :attempt"
                ),
                {"attempt": REWRITE},
            )  # refused at the statement; the connection rolls back on leaving
