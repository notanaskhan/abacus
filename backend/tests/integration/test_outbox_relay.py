"""AC-20: the outbox relay publishes at least once, and `abacus_relay` can do nothing else.

Events are created through the real unit of work (audit event only plus `emit`), so the tests need
no probe state tables. The shared database may hold unpublished rows from other tests, so each
test first drains the outbox with a throwaway publisher and then asserts on its own events only.
The relay role is exercised through a raw engine on `relay_url`.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator
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
    await relay_once(publisher)
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
    await relay_once(publisher)
    assert publisher.events == []


async def test_ac20_batch_limits_a_pass_and_the_next_pass_continues_in_order() -> None:
    ctx = _ctx()
    ids = [await _emit(ctx, n) for n in range(5)]
    first, second, third = RecordingPublisher(), RecordingPublisher(), RecordingPublisher()
    await relay_once(first, batch=2)
    await relay_once(second, batch=2)
    await relay_once(third, batch=2)
    assert first.ids == ids[:2]
    assert second.ids == ids[2:4]
    assert third.ids == ids[4:]


async def test_ac20_the_in_memory_publisher_collects_published_events() -> None:
    event_id = await _emit(_ctx())
    memory = InMemoryPublisher()
    await relay_once(memory)
    assert [_event_id(e) for e in memory.published] == [event_id]


# --- AC-20: failures --------------------------------------------------------------------------


async def test_ac20_a_publisher_failure_leaves_the_event_unpublished_and_counts_the_attempt(
    relay_engine: AsyncEngine,
) -> None:
    secret_marker = f"secret-{uuid.uuid4().hex}"
    event_id = await _emit(_ctx(), marker=secret_marker)
    failing = FailingPublisher(ValueError(f"cannot send {secret_marker}"))
    with contextlib.suppress(Exception):  # the relay may re-raise or swallow; both are valid
        await relay_once(failing)
    row = (await _rows(relay_engine, [event_id]))[event_id]
    assert row["published_at"] is None
    assert row["attempts"] == 1
    last_error = cast(str, row["last_error"])
    assert last_error
    assert "ValueError" in last_error
    assert secret_marker not in last_error
    assert secret_marker not in str(row["last_error"])


async def test_ac20_repeated_failures_increment_attempts_and_success_publishes_later(
    relay_engine: AsyncEngine,
) -> None:
    event_id = await _emit(_ctx())
    for _ in range(2):
        with contextlib.suppress(Exception):  # re-raise or swallow; both are valid
            await relay_once(FailingPublisher(RuntimeError("down")))
    row = (await _rows(relay_engine, [event_id]))[event_id]
    assert (row["published_at"], row["attempts"]) == (None, 2)
    ok = RecordingPublisher()
    await relay_once(ok)
    assert ok.ids == [event_id]
    row = (await _rows(relay_engine, [event_id]))[event_id]
    assert row["published_at"] is not None


# --- AC-20: concurrency and crashes ----------------------------------------------------------


async def test_ac20_two_concurrent_relays_never_publish_the_same_event_twice() -> None:
    ctx = _ctx()
    ids = [await _emit(ctx, n) for n in range(6)]
    one, two = RecordingPublisher(delay=0.05), RecordingPublisher(delay=0.05)
    await asyncio.gather(relay_once(one, batch=3), relay_once(two, batch=3))
    published = [*one.ids, *two.ids]
    assert len(published) == len(set(published))
    assert set(published) == set(ids)
    assert one.ids == sorted(one.ids, key=ids.index)
    assert two.ids == sorted(two.ids, key=ids.index)


async def test_ac20_two_concurrent_relays_with_one_batch_publish_each_event_once() -> None:
    ids = [await _emit(_ctx(), n) for n in range(4)]
    one, two = RecordingPublisher(delay=0.05), RecordingPublisher(delay=0.05)
    await asyncio.gather(relay_once(one), relay_once(two))
    published = [*one.ids, *two.ids]
    assert sorted(published, key=ids.index) == ids


async def test_ac20_a_crash_before_commit_republishes_the_event_with_the_same_event_id(
    relay_engine: AsyncEngine,
) -> None:
    event_id = await _emit(_ctx())
    crashing = CrashingPublisher()
    with pytest.raises(Crash):
        await relay_once(crashing)
    assert crashing.ids == [event_id]
    row = (await _rows(relay_engine, [event_id]))[event_id]
    assert row["published_at"] is None
    recovered = RecordingPublisher()
    await relay_once(recovered)
    assert recovered.ids == [event_id]
    assert (await _rows(relay_engine, [event_id]))[event_id]["published_at"] is not None


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
                "last_error = 'X' WHERE id = :id"
            ),
            {"id": event_id},
        )
    row = (await _rows(relay_engine, [event_id]))[event_id]
    assert row["published_at"] is not None
    assert (row["attempts"], row["last_error"]) == (1, "X")
