"""AC-20: trace IDs in audit rows and outbox rows, their database checks and grants, and the
relay's span (TASK-013 interface contract, "One trace"; ADR-007, ADR-022).

Events are emitted through the real unit of work. The shared database may hold other tests' rows,
so every assertion is about the rows a test wrote itself. Expectations come from the contract.
"""

from __future__ import annotations

import uuid
from typing import Annotated, ClassVar

import asyncpg
import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, configure_relay_engine
from abacus.kernel.telemetry import (
    TRACEPARENT,
    current_span_id,
    current_trace_id,
    current_traceparent,
    tracer,
)
from abacus.kernel.uow import DomainEvent, Target, uow
from abacus.kernel.uow.relay import OutboxEvent, relay_once

from . import tracing_support
from .support import Migrated, Seeder

TRACE = "c3" * 16
PARENT = f"00-{TRACE}-{'d4' * 8}-01"
KNOWN = f"obs_trace.known_{uuid.uuid4().hex[:8]}"


class Known(DomainEvent):
    event_type: ClassVar[str] = KNOWN
    n: Annotated[int, classified("public")]


@pytest.fixture(autouse=True)
def relay_engine_for_this_loop(migrated_db: Migrated) -> None:
    configure_relay_engine(migrated_db.relay_url)


@pytest.fixture(autouse=True)
def exporter() -> InMemorySpanExporter:
    memory = tracing_support.install()
    memory.clear()
    return memory


async def _emit(tenant_id: uuid.UUID | None = None) -> tuple[uuid.UUID, uuid.UUID]:
    tenant = tenant_id or uuid.uuid4()
    event = Known(n=1)
    async with uow(TenantContext(tenant, "human", "u-obs")) as tx:
        tx.record("probe.pinged", target=Target("probe", "1"))
        tx.record("probe.pinged", target=Target("probe", "2"))
        tx.emit(event)
    return tenant, event.event_id


async def _audit_traces(seed: Seeder, tenant: uuid.UUID) -> list[str | None]:
    rows = await seed.rows(
        "SELECT trace_id FROM audit_events WHERE tenant_id = $1 ORDER BY seq", tenant
    )
    return [r["trace_id"] for r in rows]


async def _context(seed: Seeder, event_id: uuid.UUID) -> str | None:
    value = await seed.value("SELECT trace_context FROM outbox WHERE id = $1", event_id)
    return None if value is None else str(value)


# --- written inside and outside a span -----------------------------------------------------------


async def test_ac20_audit_rows_written_inside_a_span_carry_its_trace_id(seed: Seeder) -> None:
    with tracer("test").start_as_current_span("parent"):
        trace_id = current_trace_id()
        tenant, _ = await _emit()
    assert await _audit_traces(seed, tenant) == [trace_id, trace_id]


async def test_ac20_an_outbox_row_written_inside_a_span_carries_its_traceparent(
    seed: Seeder,
) -> None:
    with tracer("test").start_as_current_span("parent"):
        trace_id, span_id, header = current_trace_id(), current_span_id(), current_traceparent()
        _, event_id = await _emit()
    stored = await _context(seed, event_id)
    assert stored is not None
    assert stored == header
    assert TRACEPARENT.fullmatch(stored)
    assert stored.split("-")[1:3] == [trace_id, span_id]


async def test_ac20_rows_written_outside_any_span_have_null_trace_id_and_context(
    seed: Seeder,
) -> None:
    assert current_trace_id() is None
    tenant, event_id = await _emit()
    assert await _audit_traces(seed, tenant) == [None, None]
    assert await _context(seed, event_id) is None


async def test_ac20_each_trace_writes_its_own_id(seed: Seeder) -> None:
    tenant = uuid.uuid4()
    with tracer("test").start_as_current_span("one"):
        first = current_trace_id()
        await _emit(tenant)
    with tracer("test").start_as_current_span("two"):
        second = current_trace_id()
        await _emit(tenant)
    assert first != second
    assert await _audit_traces(seed, tenant) == [first, first, second, second]


async def test_ac20_a_continued_trace_is_what_rows_record(seed: Seeder) -> None:
    from abacus.kernel.telemetry import continue_trace

    with continue_trace(PARENT):
        tenant, event_id = await _emit()
    assert await _audit_traces(seed, tenant) == [TRACE, TRACE]
    stored = await _context(seed, event_id)
    assert stored is not None
    assert stored.split("-")[1] == TRACE


# --- database checks -----------------------------------------------------------------------------

_OUTBOX = (
    "INSERT INTO outbox (id, tenant_id, event_type, payload, trace_context) "
    "VALUES ($1, $2, 'probe.pinged', '{}'::jsonb, $3)"
)


async def test_ac20_the_audit_trace_id_check_requires_32_lower_hex_digits(seed: Seeder) -> None:
    [row] = await seed.rows(
        "SELECT convalidated, pg_get_constraintdef(oid) AS definition FROM pg_constraint "
        "WHERE conname = 'audit_events_trace_id_is_trace_id' "
        "AND conrelid = 'audit_events'::regclass"
    )
    assert row["convalidated"] is True
    assert "[0-9a-f]{32}" in str(row["definition"])


@pytest.mark.parametrize("value", [None, PARENT, f"00-{'0' * 32}-{'0' * 16}-00"])
async def test_ac20_the_database_accepts_null_or_a_traceparent_in_the_outbox(
    seed: Seeder, value: str | None
) -> None:
    event_id = uuid.uuid4()
    await seed.run(_OUTBOX, event_id, uuid.uuid4(), value)
    assert await _context(seed, event_id) == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        "garbage",
        f"01-{TRACE}-{'d4' * 8}-01",
        f"00-{TRACE.upper()}-{'d4' * 8}-01",
        f"00-{TRACE[:-1]}-{'d4' * 8}-01",
        f"00-{TRACE}-{'d4' * 7}-01",
        f"00-{TRACE}-{'d4' * 8}-1",
        f"00-{TRACE}-{'d4' * 8}-01-x",
        TRACE,
    ],
)
async def test_ac20_the_database_rejects_an_outbox_trace_context_that_is_not_a_traceparent(
    seed: Seeder, value: str
) -> None:
    with pytest.raises(asyncpg.CheckViolationError, match="outbox_trace_context_is_traceparent"):
        await seed.run(_OUTBOX, uuid.uuid4(), uuid.uuid4(), value)


# --- grants --------------------------------------------------------------------------------------


async def _privilege(seed: Seeder, role: str, table: str, column: str, kind: str) -> bool:
    return bool(
        await seed.value("SELECT has_column_privilege($1, $2, $3, $4)", role, table, column, kind)
    )


async def test_ac20_the_app_role_may_insert_the_outbox_trace_context_but_not_change_it(
    seed: Seeder,
) -> None:
    assert await _privilege(seed, "abacus_app", "outbox", "trace_context", "INSERT")
    assert not await _privilege(seed, "abacus_app", "outbox", "trace_context", "UPDATE")


async def test_ac20_the_relay_role_may_read_the_outbox_trace_context_but_not_change_it(
    seed: Seeder,
) -> None:
    assert await _privilege(seed, "abacus_relay", "outbox", "trace_context", "SELECT")
    assert not await _privilege(seed, "abacus_relay", "outbox", "trace_context", "UPDATE")
    assert not await _privilege(seed, "abacus_relay", "outbox", "trace_context", "INSERT")


async def test_ac20_the_app_role_may_insert_an_audit_trace_id_but_not_change_it(
    seed: Seeder,
) -> None:
    assert await _privilege(seed, "abacus_app", "audit_events", "trace_id", "INSERT")
    assert not await _privilege(seed, "abacus_app", "audit_events", "trace_id", "UPDATE")


# --- the relay -----------------------------------------------------------------------------------


class Collecting:
    """A publisher that remembers the events it is given (all events, any test's) and the trace
    it was called in."""

    def __init__(self) -> None:
        self.events: dict[uuid.UUID, OutboxEvent] = {}
        self.in_trace: dict[uuid.UUID, tuple[str | None, str | None]] = {}

    async def publish(self, event: OutboxEvent) -> None:
        self.events[event.event_id] = event
        self.in_trace[event.event_id] = (current_trace_id(), current_span_id())


def _publish_span(spans: list[ReadableSpan], event_id: uuid.UUID) -> ReadableSpan:
    [found] = [
        s
        for s in spans
        if s.name == "outbox.publish"
        and (s.attributes or {}).get("outbox.event_id") == str(event_id)
    ]
    return found


async def test_ac20_the_relay_hands_the_stored_trace_context_to_the_publisher(
    seed: Seeder,
) -> None:
    with tracer("test").start_as_current_span("emitter"):
        header = current_traceparent()
        _, event_id = await _emit()
    publisher = Collecting()
    await relay_once(publisher, batch=500)
    assert publisher.events[event_id].trace_context == header


async def test_ac20_the_relay_publishes_inside_the_emitting_trace(
    seed: Seeder, exporter: InMemorySpanExporter
) -> None:
    with tracer("test").start_as_current_span("emitter"):
        trace_id, emitter_span = current_trace_id(), current_span_id()
        _, event_id = await _emit()
    exporter.clear()
    publisher = Collecting()
    await relay_once(publisher, batch=500)
    seen_trace, seen_span = publisher.in_trace[event_id]
    assert seen_trace == trace_id
    span = _publish_span(list(exporter.get_finished_spans()), event_id)
    assert tracing_support.trace_hex(span) == trace_id
    assert span.parent is not None
    assert format(span.parent.span_id, "016x") == emitter_span
    assert tracing_support.span_hex(span) == seen_span


async def test_ac20_the_relay_publish_span_names_the_event_and_the_tenant_only(
    seed: Seeder, exporter: InMemorySpanExporter
) -> None:
    with tracer("test").start_as_current_span("emitter"):
        tenant, event_id = await _emit()
    exporter.clear()
    await relay_once(Collecting(), batch=500)
    span = _publish_span(list(exporter.get_finished_spans()), event_id)
    attributes = dict(span.attributes or {})
    assert attributes["outbox.event_type"] == KNOWN
    assert attributes["outbox.event_id"] == str(event_id)
    assert attributes["tenant.id"] == str(tenant)
    assert "payload" not in tracing_support.everything([span])


async def test_ac20_an_event_with_no_trace_context_starts_a_new_trace_when_relayed(
    seed: Seeder, exporter: InMemorySpanExporter
) -> None:
    _, event_id = await _emit()
    exporter.clear()
    publisher = Collecting()
    await relay_once(publisher, batch=500)
    assert publisher.events[event_id].trace_context is None
    span = _publish_span(list(exporter.get_finished_spans()), event_id)
    assert span.parent is None
    assert publisher.in_trace[event_id][0] == tracing_support.trace_hex(span)


class Failing:
    async def publish(self, event: OutboxEvent) -> None:
        raise RuntimeError("handler said CLIENT-ROW-MARKER-8812")


async def test_ac20_a_failing_publish_records_no_exception_event_or_message_on_its_span(
    seed: Seeder, exporter: InMemorySpanExporter
) -> None:
    with tracer("test").start_as_current_span("emitter"):
        _, event_id = await _emit()
    exporter.clear()
    await relay_once(Failing(), batch=500)
    span = _publish_span(list(exporter.get_finished_spans()), event_id)
    assert [e for e in span.events if e.name == "exception"] == []
    assert "CLIENT-ROW-MARKER-8812" not in tracing_support.everything([span])


async def test_ac20_an_outbox_event_built_without_a_trace_context_has_none() -> None:
    event = OutboxEvent(uuid.uuid4(), uuid.uuid4(), "probe.pinged", {})
    assert event.trace_context is None
