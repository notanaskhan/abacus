"""AC-20: the outbox relay publishes at least once, and `abacus_relay` can do nothing else.

Events are created through the real unit of work (audit event only plus `emit`), so the tests need
no probe state tables. The shared database may hold unpublished rows from other tests, so each
test first drains the outbox with a throwaway publisher and then asserts on its own events only.
The relay role is exercised through a raw engine on `relay_url`.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, ClassVar, Protocol, cast

import pytest
from alembic.operations import Operations
from sqlalchemy import Column, DateTime, Integer, MetaData, Table, Text, Uuid, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from abacus.kernel.classification import classified
from abacus.kernel.db import (
    TenantContext,
    configure_engine,
    configure_relay_engine,
    dispose_engine,
)
from abacus.kernel.db.migration import tenant_table
from abacus.kernel.uow import DomainEvent, Target, uow
from abacus.kernel.uow.relay import InMemoryPublisher, OutboxEvent, relay_once


class Migrated(Protocol):
    owner_url: str
    app_url: str
    relay_url: str
    superuser_dsn: str


METADATA = MetaData()
OUTBOX = Table(
    "outbox",
    METADATA,
    Column("id", Uuid(), primary_key=True),
    Column("tenant_id", Uuid(), nullable=False),
    Column("seq", Integer()),
    Column("event_type", Text()),
    Column("payload", JSONB()),
    Column("published_at", DateTime(timezone=True)),
    Column("attempts", Integer()),
    Column("last_error", Text()),
    Column("next_attempt_at", DateTime(timezone=True)),
)
RELAY_PROBE = Table(
    "relay_probe",
    METADATA,
    Column("id", Uuid(), primary_key=True),
    Column("tenant_id", Uuid(), nullable=False),
)


class Pinged(DomainEvent):
    event_type: ClassVar[str] = "probe.pinged"
    n: Annotated[int, classified("public")]
    marker: Annotated[str, classified("internal")]


class Crash(BaseException):  # simulates the process dying; deliberately not an Exception
    pass


def _event_id(event: object) -> uuid.UUID:
    fields = vars(event)
    return uuid.UUID(str(fields["event_id"] if "event_id" in fields else fields["id"]))


class RecordingPublisher:
    def __init__(self, delay: float = 0.0) -> None:
        self.events: list[OutboxEvent] = []
        self.delay = delay

    async def publish(self, event: OutboxEvent) -> None:
        if self.delay:
            await asyncio.sleep(self.delay)
        self.events.append(event)

    @property
    def ids(self) -> list[uuid.UUID]:
        return [_event_id(e) for e in self.events]


class FailOnPublisher(RecordingPublisher):
    """Fails (without recording) for the given event ids; records the rest."""

    def __init__(self, failing: set[uuid.UUID]) -> None:
        super().__init__()
        self.failing = failing

    async def publish(self, event: OutboxEvent) -> None:
        if _event_id(event) in self.failing:
            raise ValueError("cannot send")
        await super().publish(event)


class BarrierPublisher(RecordingPublisher):
    """Signals that it holds its claim, then waits to be released before publishing."""

    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def publish(self, event: OutboxEvent) -> None:
        self.started.set()
        await asyncio.wait_for(self.release.wait(), timeout=20)
        await super().publish(event)


class FailingPublisher:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def publish(self, event: OutboxEvent) -> None:
        raise self.error


class CrashingPublisher(RecordingPublisher):
    async def publish(self, event: OutboxEvent) -> None:
        await super().publish(event)
        raise Crash


def _ctx(tenant_id: uuid.UUID | None = None) -> TenantContext:
    return TenantContext(tenant_id=tenant_id or uuid.uuid4(), actor_kind="human", actor_id="u-1")


async def _emit(ctx: TenantContext, n: int = 0, marker: str = "m") -> uuid.UUID:
    event = Pinged(n=n, marker=marker)
    async with uow(ctx) as tx:
        tx.record("probe.pinged", target=Target("probe", str(n)))
        tx.emit(event)
    return event.event_id


class RecordingOp:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, sql: str) -> None:
        self.statements.append(sql)


@pytest.fixture(autouse=True)
async def engines_for_this_loop(migrated_db: Migrated) -> AsyncIterator[None]:
    configure_engine(migrated_db.app_url)
    configure_relay_engine(migrated_db.relay_url)
    yield
    await dispose_engine()


@pytest.fixture
async def relay_engine(migrated_db: Migrated) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(migrated_db.relay_url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
async def drained_outbox(engines_for_this_loop: None) -> None:
    for _ in range(100):
        publisher = RecordingPublisher()
        await relay_once(publisher)
        if not publisher.events:
            return
    pytest.fail("could not drain the outbox")


async def _rows(engine: AsyncEngine, ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, object]]:
    async with engine.connect() as conn:
        result = await conn.execute(select(OUTBOX).where(OUTBOX.c.id.in_(ids)))
        return {r["id"]: dict(r) for r in result.mappings().all()}


# --- AC-20: publish once, in order -----------------------------------------------------------


async def test_ac20_relay_publishes_every_tenants_events_once_in_seq_order(
    relay_engine: AsyncEngine,
) -> None:
    a, b = _ctx(), _ctx()
    ids = [
        await _emit(a, 1),
        await _emit(b, 2),
        await _emit(a, 3),
        await _emit(b, 4),
    ]
    publisher = RecordingPublisher()
    result = await relay_once(publisher)
    assert (result.published, result.failed, result.deferred) == (4, 0, 0)
    assert publisher.ids == ids
    assert [e.tenant_id for e in publisher.events] == [
        a.tenant_id,
        b.tenant_id,
        a.tenant_id,
        b.tenant_id,
    ]
    assert {e.event_type for e in publisher.events} == {"probe.pinged"}
    assert [e.payload["n"] for e in publisher.events] == [1, 2, 3, 4]
    rows = await _rows(relay_engine, ids)
    assert all(r["published_at"] is not None for r in rows.values())
    assert all(r["last_error"] is None for r in rows.values())


async def test_ac20_a_second_pass_publishes_nothing_again() -> None:
    await _emit(_ctx())
    first, second = RecordingPublisher(), RecordingPublisher()
    await relay_once(first)
    await relay_once(second)
    assert len(first.events) == 1
    assert second.events == []


async def test_ac20_a_pass_with_nothing_to_publish_is_a_no_op() -> None:
    publisher = RecordingPublisher()
    result = await relay_once(publisher)
    assert publisher.events == []
    assert (result.published, result.failed, result.deferred) == (0, 0, 0)


async def test_ac20_batch_limits_a_pass_and_the_next_pass_continues_in_order() -> None:
    ctx = _ctx()
    ids = [await _emit(ctx, n) for n in range(5)]
    first, second, third = RecordingPublisher(), RecordingPublisher(), RecordingPublisher()
    results = [
        await relay_once(first, batch=2),
        await relay_once(second, batch=2),
        await relay_once(third, batch=2),
    ]
    assert [r.published for r in results] == [2, 2, 1]
    assert first.ids == ids[:2]
    assert second.ids == ids[2:4]
    assert third.ids == ids[4:]


async def test_ac20_the_in_memory_publisher_collects_published_events() -> None:
    event_id = await _emit(_ctx())
    memory = InMemoryPublisher()
    await relay_once(memory)
    assert [_event_id(e) for e in memory.published] == [event_id]


# --- AC-20: failures, backoff, parking -------------------------------------------------------


async def _row(engine: AsyncEngine, event_id: uuid.UUID) -> dict[str, object]:
    return (await _rows(engine, [event_id]))[event_id]


async def _relay_sql(engine: AsyncEngine, statement: str, **params: object) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(statement), params)


async def test_ac20_a_publisher_failure_leaves_the_event_unpublished_and_counts_the_attempt(
    relay_engine: AsyncEngine,
) -> None:
    secret_marker = f"secret-{uuid.uuid4().hex}"
    event_id = await _emit(_ctx(), marker=secret_marker)
    result = await relay_once(FailingPublisher(ValueError(f"cannot send {secret_marker}")))
    assert (result.published, result.failed, result.deferred) == (0, 1, 0)
    row = await _row(relay_engine, event_id)
    assert row["published_at"] is None
    assert row["attempts"] == 1
    assert row["last_error"] == "ValueError"
    next_attempt = cast(datetime, row["next_attempt_at"])
    assert next_attempt > datetime.now(UTC)


async def test_ac20_a_failed_event_is_not_claimed_again_before_its_next_attempt_at(
    relay_engine: AsyncEngine,
) -> None:
    event_id = await _emit(_ctx())
    await relay_once(FailingPublisher(RuntimeError("down")))
    early = RecordingPublisher()
    result = await relay_once(early)
    assert early.events == []
    assert (result.published, result.failed) == (0, 0)
    assert (await _row(relay_engine, event_id))["attempts"] == 1
    await _relay_sql(
        relay_engine,
        "UPDATE outbox SET next_attempt_at = now() - interval '1 minute' WHERE id = :id",
        id=event_id,
    )
    due = RecordingPublisher()
    result = await relay_once(due)
    assert due.ids == [event_id]
    assert result.published == 1
    assert (await _row(relay_engine, event_id))["published_at"] is not None


async def test_ac20_backoff_grows_with_each_failure(relay_engine: AsyncEngine) -> None:
    event_id = await _emit(_ctx())
    delays: list[float] = []
    for _ in range(3):
        await relay_once(FailingPublisher(RuntimeError("down")))
        next_attempt = cast(datetime, (await _row(relay_engine, event_id))["next_attempt_at"])
        delays.append((next_attempt - datetime.now(UTC)).total_seconds())
        await _relay_sql(
            relay_engine,
            "UPDATE outbox SET next_attempt_at = now() - interval '1 second' WHERE id = :id",
            id=event_id,
        )
    assert delays[0] < delays[1] < delays[2]


async def test_ac20_an_event_is_parked_after_ten_attempts(relay_engine: AsyncEngine) -> None:
    event_id = await _emit(_ctx())
    for attempt in range(1, 11):
        result = await relay_once(FailingPublisher(RuntimeError("down")))
        assert result.failed == 1, attempt
        await _relay_sql(
            relay_engine,
            "UPDATE outbox SET next_attempt_at = now() - interval '1 second' WHERE id = :id",
            id=event_id,
        )
    assert (await _row(relay_engine, event_id))["attempts"] == 10
    parked = RecordingPublisher()
    result = await relay_once(parked)
    assert parked.events == []
    assert (result.published, result.failed, result.deferred) == (0, 0, 0)
    row = await _row(relay_engine, event_id)
    assert (row["published_at"], row["attempts"]) == (None, 10)


async def test_ac20_a_failure_defers_the_rest_of_that_tenants_events_but_not_other_tenants(
    relay_engine: AsyncEngine,
) -> None:
    a, b = _ctx(), _ctx()
    a1, b1, a2, b2, a3 = [
        await _emit(a, 1),
        await _emit(b, 2),
        await _emit(a, 3),
        await _emit(b, 4),
        await _emit(a, 5),
    ]
    publisher = FailOnPublisher({a1})
    result = await relay_once(publisher)
    assert publisher.ids == [b1, b2]
    assert (result.published, result.failed, result.deferred) == (2, 1, 2)
    rows = await _rows(relay_engine, [a1, a2, a3, b1, b2])
    assert rows[a1]["attempts"] == 1
    for untouched in (a2, a3):
        assert rows[untouched]["published_at"] is None
        assert rows[untouched]["attempts"] == 0
        assert rows[untouched]["last_error"] is None
        assert rows[untouched]["next_attempt_at"] is None
    assert rows[b1]["published_at"] is not None
    assert rows[b2]["published_at"] is not None


async def test_ac20_a_malformed_payload_is_counted_as_failed_and_does_not_abort_the_pass(
    migrated_db: Migrated, relay_engine: AsyncEngine
) -> None:
    # The unit of work only writes model objects, so plant the malformed row as superuser.
    bad_id = uuid.uuid4()
    superuser = create_async_engine(
        migrated_db.superuser_dsn.replace("postgresql://", "postgresql+asyncpg://", 1),
        poolclass=NullPool,
    )
    try:
        async with superuser.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO outbox (id, tenant_id, event_type, payload) "
                    "VALUES (:id, :t, 'probe.malformed', CAST(:p AS jsonb))"
                ),
                {"id": bad_id, "t": uuid.uuid4(), "p": json.dumps([1])},
            )
        good_id = await _emit(_ctx(), 9)
        publisher = RecordingPublisher()
        result = await relay_once(publisher)
        assert publisher.ids == [good_id]
        assert (result.published, result.failed) == (1, 1)
        bad = await _row(relay_engine, bad_id)
        assert (bad["published_at"], bad["attempts"]) == (None, 1)
        assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,199}", str(bad["last_error"]))
        assert (await _row(relay_engine, good_id))["published_at"] is not None
    finally:
        async with superuser.begin() as conn:
            await conn.execute(text("DELETE FROM outbox WHERE id = :id"), {"id": bad_id})
        await superuser.dispose()


async def test_ac20_a_failure_is_logged_as_outbox_publish_failed_without_the_payload(
    capsys: pytest.CaptureFixture[str],
) -> None:
    marker = f"secret-{uuid.uuid4().hex}"
    ctx = _ctx()
    event_id = await _emit(ctx, 1, marker=marker)
    capsys.readouterr()
    await relay_once(FailingPublisher(ValueError(f"cannot send {marker}")))
    out = capsys.readouterr().out
    lines = [json.loads(line) for line in out.splitlines() if line.strip().startswith("{")]
    [entry] = [line for line in lines if line.get("event") == "outbox.publish_failed"]
    assert entry["event_id"] == str(event_id)
    assert entry["tenant_id"] == str(ctx.tenant_id)
    assert entry["event_type"] == "probe.pinged"
    assert entry["attempts"] == 1
    assert entry["error"] == "ValueError"
    assert marker not in out
    assert "payload" not in entry


# --- AC-20: concurrency and crashes ----------------------------------------------------------


async def test_ac20_a_second_relay_claims_while_the_first_holds_its_locks_without_overlap() -> (
    None
):
    ctx = _ctx()
    ids = [await _emit(ctx, n) for n in range(6)]
    first, second = BarrierPublisher(), RecordingPublisher()
    task = asyncio.create_task(relay_once(first, batch=3))
    await asyncio.wait_for(first.started.wait(), timeout=20)
    # the first relay now holds its batch locked and has not committed
    await asyncio.wait_for(relay_once(second, batch=3), timeout=20)
    first.release.set()
    await asyncio.wait_for(task, timeout=20)
    assert first.ids and second.ids
    assert not set(first.ids) & set(second.ids)
    assert set(first.ids) | set(second.ids) == set(ids)
    assert first.ids == ids[:3]
    assert second.ids == ids[3:]


async def test_ac20_a_second_relay_skips_every_event_the_first_holds() -> None:
    ids = [await _emit(_ctx(), n) for n in range(4)]
    first, second = BarrierPublisher(), RecordingPublisher()
    task = asyncio.create_task(relay_once(first))
    await asyncio.wait_for(first.started.wait(), timeout=20)
    result = await asyncio.wait_for(relay_once(second), timeout=20)
    first.release.set()
    await asyncio.wait_for(task, timeout=20)
    assert second.events == []
    assert result.published == 0
    assert first.ids == ids


async def test_ac20_a_crash_before_commit_republishes_the_event_with_the_same_event_id(
    relay_engine: AsyncEngine,
) -> None:
    event_id = await _emit(_ctx())
    crashing = CrashingPublisher()
    with pytest.raises(Crash):
        await relay_once(crashing)
    assert crashing.ids == [event_id]
    row = await _row(relay_engine, event_id)
    assert (row["published_at"], row["attempts"]) == (None, 0)
    recovered = RecordingPublisher()
    await relay_once(recovered)
    assert recovered.ids == [event_id]
    assert (await _row(relay_engine, event_id))["published_at"] is not None


# --- AC-20: the relay role can read the outbox and nothing else -----------------------------


@pytest.fixture
async def relay_probe_table(migrated_db: Migrated) -> AsyncIterator[None]:
    owner = create_async_engine(migrated_db.owner_url, poolclass=NullPool)
    try:
        async with owner.begin() as conn:
            await conn.run_sync(RELAY_PROBE.drop, checkfirst=True)
            await conn.run_sync(RELAY_PROBE.create)
            op = RecordingOp()
            tenant_table(cast(Operations, op), "relay_probe")
            for statement in op.statements:
                await conn.exec_driver_sql(statement)
        yield
        async with owner.begin() as conn:
            await conn.run_sync(RELAY_PROBE.drop, checkfirst=True)
    finally:
        await owner.dispose()


async def test_ac20_the_relay_role_reads_every_tenants_outbox_rows(
    relay_engine: AsyncEngine,
) -> None:
    ids = [await _emit(_ctx()), await _emit(_ctx())]
    assert set(await _rows(relay_engine, ids)) == set(ids)
    async with relay_engine.connect() as conn:
        assert (await conn.execute(text("SELECT current_user"))).scalar_one() == "abacus_relay"


@pytest.mark.parametrize(
    "statement",
    [
        "SELECT * FROM audit_events",
        "SELECT * FROM alembic_version",
        "SELECT * FROM relay_probe",
        "SELECT * FROM pg_catalog.pg_authid",
    ],
    ids=["audit-events", "alembic-version", "other-tenant-table", "pg-authid"],
)
async def test_ac20_the_relay_role_cannot_read_anything_but_the_outbox(
    relay_engine: AsyncEngine, relay_probe_table: None, statement: str
) -> None:
    with pytest.raises(DBAPIError, match="permission denied"):
        async with relay_engine.connect() as conn:
            await conn.execute(text(statement))


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE outbox SET payload = '{}'::jsonb",
        "UPDATE outbox SET event_type = 'x'",
        "UPDATE outbox SET tenant_id = gen_random_uuid()",
        "UPDATE outbox SET occurred_at = now()",
        "DELETE FROM outbox",
        "INSERT INTO outbox (id, tenant_id, event_type, payload) "
        "VALUES (gen_random_uuid(), gen_random_uuid(), 'x', '{}'::jsonb)",
        "UPDATE audit_events SET action = 'x.y'",
    ],
    ids=[
        "update-payload",
        "update-event-type",
        "update-tenant",
        "update-occurred-at",
        "delete",
        "insert",
        "update-audit",
    ],
)
async def test_ac20_the_relay_role_cannot_change_anything_but_the_status_columns(
    relay_engine: AsyncEngine, statement: str
) -> None:
    await _emit(_ctx())
    with pytest.raises(DBAPIError, match="permission denied"):
        async with relay_engine.begin() as conn:
            await conn.execute(text(statement))


async def test_ac20_the_relay_role_can_update_the_three_status_columns(
    relay_engine: AsyncEngine,
) -> None:
    event_id = await _emit(_ctx())
    async with relay_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE outbox SET published_at = clock_timestamp(), attempts = attempts + 1, "
                "last_error = 'X', next_attempt_at = now() WHERE id = :id"
            ),
            {"id": event_id},
        )
    row = (await _rows(relay_engine, [event_id]))[event_id]
    assert row["published_at"] is not None
    assert (row["attempts"], row["last_error"]) == (1, "X")
    assert row["next_attempt_at"] is not None


@pytest.mark.parametrize("value", ["has spaces", "", "1Starts", "a-b", "x" * 201, "Value Error"])
async def test_ac20_the_database_rejects_a_last_error_that_is_not_a_class_name(
    relay_engine: AsyncEngine, value: str
) -> None:
    event_id = await _emit(_ctx())
    with pytest.raises(DBAPIError, match=r"check constraint|violates"):
        await _relay_sql(
            relay_engine, "UPDATE outbox SET last_error = :v WHERE id = :id", v=value, id=event_id
        )


@pytest.mark.parametrize("value", ["ValueError", "asyncpg.exceptions.PostgresError", "_Private"])
async def test_ac20_the_database_accepts_a_class_name_as_last_error(
    relay_engine: AsyncEngine, value: str
) -> None:
    event_id = await _emit(_ctx())
    await _relay_sql(
        relay_engine, "UPDATE outbox SET last_error = :v WHERE id = :id", v=value, id=event_id
    )
    assert (await _row(relay_engine, event_id))["last_error"] == value
