"""Outbox relay: publish domain events at least once (ADR-018). PROTECTED. TASK-006 design §4,
contract revision 1.

Runs as `abacus_relay`, the one role that reads every tenant's outbox; it can read the outbox and
mark delivery, nothing else (schema_check enforces it). Semantics:

- At least once: an event is marked published only after `publish` returns. A crash or cancel
  before the pass commits republishes it with the same `event_id`; consumers deduplicate on
  `(tenant_id, event_id)`.
- Concurrent relays don't publish an event twice in one pass (`FOR UPDATE SKIP LOCKED`).
- Fair across tenants: a pass claims at most `per_tenant` events of any one tenant, so one
  firm's flood can't hold back the others.
- A failing event backs off exponentially (capped at an hour) and is parked after MAX_ATTEMPTS:
  one poison event can't stall the queue. Its tenant's later events in the same pass are deferred,
  so they don't overtake it.
- Order: per tenant within a pass, best effort across passes. `seq` is insert order, not commit
  order, so consumers must not assume a global order.
- Locks are held while publishing: keep `batch` small.

`RoutingPublisher` hands each event to the handlers subscribed to its type (modules declare
them as `SUBSCRIPTIONS` in their `api.py`; the worker composes them), each bounded by
`HANDLER_TIMEOUT` (a hung handler fails the event, which backs off). Handlers must be
idempotent: a redelivery, or a later handler failing, runs them again. `run_relay` is the loop
the worker runs (TASK-011 Q4); each pass is bounded by `PASS_TIMEOUT`.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import relay_engine
from abacus.kernel.logging import get_logger
from abacus.kernel.telemetry import continue_trace, tracer

MAX_ATTEMPTS = 10
MAX_BACKOFF_SECONDS = 3600
HANDLER_TIMEOUT = 15.0
PASS_TIMEOUT = 120.0
_log = get_logger(__name__)
_tracer = tracer(__name__)

_CLAIM = text(
    "SELECT id, tenant_id, event_type, payload, attempts, trace_context, grant_id FROM outbox "
    "WHERE id IN ("
    "SELECT id FROM (SELECT id, row_number() OVER (PARTITION BY tenant_id ORDER BY seq) AS n "
    "FROM outbox WHERE published_at IS NULL AND attempts < :max_attempts "
    "AND (next_attempt_at IS NULL OR next_attempt_at <= clock_timestamp()) "
    "AND (not_before IS NULL OR not_before <= clock_timestamp())) AS due "
    "WHERE n <= :per_tenant) "
    "ORDER BY seq LIMIT :batch FOR UPDATE SKIP LOCKED"
)
_PUBLISHED = text(
    "UPDATE outbox SET published_at = clock_timestamp() WHERE tenant_id = :tenant AND id = :id"
)
_FAILED = text(
    "UPDATE outbox SET attempts = attempts + 1, last_error = :error, "
    "next_attempt_at = clock_timestamp() + make_interval(secs => :backoff) "
    "WHERE tenant_id = :tenant AND id = :id"
)


# P-06-T06 (ADR-161): a grant-held event is delivered only if its approval grant is consumed at
# delivery. Identity registers the consumer (`consume_grant`, P-04-T10); until then a held event
# waits, retried with backoff, and nothing goes out. The consumer gets the tenant, the grant, the
# event (a retry of the same event stays consumed) and the payload's SHA-256 (the grant is bound
# to it), and answers whether to deliver. Raising leaves the event for a retry.
GrantConsumer = Callable[[UUID, UUID, UUID, str], Awaitable[bool]]
_GRANT_CONSUMER: list[GrantConsumer] = []


class GrantConsumerMissing(RuntimeError):
    """A grant-held event can't be delivered before a grant consumer is registered."""


def register_grant_consumer(consumer: GrantConsumer) -> None:
    if _GRANT_CONSUMER and _GRANT_CONSUMER[0] is not consumer:
        raise ValueError("a grant consumer is already registered")
    _GRANT_CONSUMER[:] = [consumer]


def payload_sha256(payload: Mapping[str, object]) -> str:
    """The SHA-256 of an event payload in canonical JSON (sorted keys, no spaces). The issuer of a
    grant and the relay compute the same digest (`kernel.uow.event_sha256` on the event)."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


async def _grant_allows(event: OutboxEvent, grant_id: UUID | None) -> bool:
    """True to deliver. A voided or spent grant (an Undo) delivers nothing."""
    if grant_id is None:
        return True
    if not _GRANT_CONSUMER:
        raise GrantConsumerMissing
    digest = payload_sha256(event.payload)
    return await _GRANT_CONSUMER[0](event.tenant_id, grant_id, event.event_id, digest)


@dataclass(frozen=True)
class OutboxEvent:
    event_id: UUID
    tenant_id: UUID
    event_type: str
    payload: dict[str, object]
    # The W3C traceparent of the transaction that emitted it (TASK-013): publishing continues it.
    trace_context: str | None = None


@dataclass(frozen=True)
class RelayResult:
    published: int
    failed: int
    deferred: int


class Publisher(Protocol):
    async def publish(self, event: OutboxEvent) -> None: ...


@dataclass
class InMemoryPublisher:
    """Records what was published; for tests and local runs."""

    published: list[OutboxEvent] = field(default_factory=list[OutboxEvent])

    async def publish(self, event: OutboxEvent) -> None:
        self.published.append(event)


Handler = Callable[[OutboxEvent], Awaitable[None]]


@dataclass(frozen=True)
class RoutingPublisher:
    """Publishes an event by running every handler subscribed to its type, in order. An event
    nobody subscribes to is delivered as it is."""

    handlers: Mapping[str, Sequence[Handler]]

    async def publish(self, event: OutboxEvent) -> None:
        for handler in self.handlers.get(event.event_type, ()):
            async with asyncio.timeout(HANDLER_TIMEOUT):
                await handler(event)


def _payload(raw: object) -> dict[str, object]:
    loaded: object = json.loads(raw) if isinstance(raw, str | bytes) else raw
    if not isinstance(loaded, dict):
        raise ValueError("outbox payload is not a JSON object")
    return cast(dict[str, object], loaded)


def _backoff(attempts_after_failure: int) -> int:
    return min(2**attempts_after_failure, MAX_BACKOFF_SECONDS)


async def relay_once(publisher: Publisher, batch: int = 25, per_tenant: int = 10) -> RelayResult:
    """Publish up to `batch` due events, oldest first. Never raises for a failing event."""
    published = failed = deferred = 0
    blocked: set[UUID] = set()  # tenants with a failure in this pass
    async with relay_engine().connect() as conn:
        claim = {"batch": batch, "per_tenant": per_tenant, "max_attempts": MAX_ATTEMPTS}
        rows = (await conn.execute(_CLAIM, claim)).all()
        for row in rows:
            tenant = cast(UUID, row.tenant_id)
            if tenant in blocked:
                deferred += 1
                continue
            keys = {"tenant": tenant, "id": row.id}
            try:
                event = OutboxEvent(
                    row.id, tenant, row.event_type, _payload(row.payload), row.trace_context
                )
                with (
                    continue_trace(event.trace_context),
                    _tracer.start_as_current_span(
                        "outbox.publish",
                        attributes={
                            "outbox.event_type": event.event_type,
                            "outbox.event_id": str(event.event_id),
                            "tenant.id": str(tenant),
                        },
                        record_exception=False,  # the failure is logged below, by class name
                    ),
                ):
                    if await _grant_allows(event, row.grant_id):
                        await publisher.publish(event)
                    else:
                        _log.info("outbox.grant_void", event_id=row.id, tenant_id=tenant)
            except Exception as exc:  # stays unpublished; record why (class name only)
                attempts = int(row.attempts) + 1
                error = type(exc).__name__
                await conn.execute(
                    _FAILED, {**keys, "error": error, "backoff": _backoff(attempts)}
                )
                _log.warning(
                    "outbox.publish_failed",
                    event_id=row.id,
                    tenant_id=tenant,
                    event_type=str(row.event_type),
                    attempts=attempts,
                    error=error,
                    parked=attempts >= MAX_ATTEMPTS,
                )
                blocked.add(tenant)
                failed += 1
                continue
            await conn.execute(_PUBLISHED, keys)
            published += 1
        await conn.commit()
    return RelayResult(published, failed, deferred)


async def run_relay(
    publisher: Publisher, stop: asyncio.Event, *, interval: float = 1.0, batch: int = 25
) -> None:
    """Relay until `stop` is set: drain while there is work, then poll every `interval` seconds.
    A failing or hung pass (bounded by `PASS_TIMEOUT`) is logged and retried with a capped
    backoff, never fatal."""
    failures = 0
    while not stop.is_set():
        busy = False
        try:
            async with asyncio.timeout(PASS_TIMEOUT):
                result = await relay_once(publisher, batch)
            busy = result.published + result.failed + result.deferred >= batch
            failures = 0
        except Exception as exc:  # log the class only: messages can carry database values
            failures += 1
            _log.warning("outbox.relay_pass_failed", error=type(exc).__name__, failures=failures)
        if not busy:
            wait = min(interval * 2 ** min(failures, 6), 60.0)
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), wait)


_EVENT_STATE = text(
    "SELECT published_at IS NOT NULL FROM outbox WHERE tenant_id = :tenant "
    "AND event_type = :event_type AND payload ->> :field = :value ORDER BY seq DESC LIMIT 1"
)


async def event_state(
    tenant_id: UUID, event_type: str, *, field: str, value: str
) -> Literal["absent", "pending", "published"]:
    """Q-01-T30 (the canary): whether the newest `event_type` event of one firm whose payload
    `field` is `value` has been published. Reads one row through the relay role (the app role
    may only insert into the outbox); returns no payload."""
    async with relay_engine().connect() as conn:
        found = (
            await conn.execute(
                _EVENT_STATE,
                {"tenant": tenant_id, "event_type": event_type, "field": field, "value": value},
            )
        ).scalar_one_or_none()
    if found is None:
        return "absent"
    return "published" if found else "pending"


_PUBLISHED_SINCE = text(
    "SELECT id, tenant_id, event_type, payload, trace_context, occurred_at FROM outbox "
    "WHERE tenant_id = :tenant AND event_type = ANY(:types) AND published_at IS NOT NULL "
    "AND occurred_at >= :since ORDER BY seq"
)


async def published_events(
    tenant_id: UUID, event_types: Sequence[str], since: datetime
) -> list[tuple[OutboxEvent, datetime]]:
    """I-01-T12 (DEC-900): one firm's published events of the given types since a moment, with
    when each was written, oldest first, for a projection's rebuild. Reads through the relay
    role (the app role may only insert into the outbox); one firm only."""
    async with relay_engine().connect() as conn:
        rows = (
            await conn.execute(
                _PUBLISHED_SINCE, {"tenant": tenant_id, "types": list(event_types), "since": since}
            )
        ).all()
    return [
        (
            OutboxEvent(
                row.id, row.tenant_id, row.event_type, _payload(row.payload), row.trace_context
            ),
            cast(datetime, row.occurred_at),
        )
        for row in rows
    ]
