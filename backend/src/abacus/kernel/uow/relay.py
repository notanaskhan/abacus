"""Outbox relay: publish domain events at least once (ADR-018). PROTECTED. TASK-006 design §4.

Runs as `abacus_relay`, the one role that reads every tenant's outbox; it can read the outbox and
mark delivery, nothing else (schema_check enforces it). Each pass locks a batch with
`FOR UPDATE SKIP LOCKED`, so relays can run side by side without publishing an event twice in one
pass. An event is marked published only after `publish` returns; a crash in between republishes it
with the same `event_id`, which consumers use to deduplicate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import relay_engine

_CLAIM = text(
    "SELECT id, tenant_id, event_type, payload FROM outbox WHERE published_at IS NULL "
    "ORDER BY seq LIMIT :batch FOR UPDATE SKIP LOCKED"
)
_PUBLISHED = text("UPDATE outbox SET published_at = clock_timestamp() WHERE id = :id")
_FAILED = text("UPDATE outbox SET attempts = attempts + 1, last_error = :error WHERE id = :id")


@dataclass(frozen=True)
class OutboxEvent:
    event_id: UUID
    tenant_id: UUID
    event_type: str
    payload: dict[str, object]


class Publisher(Protocol):
    async def publish(self, event: OutboxEvent) -> None: ...


@dataclass
class InMemoryPublisher:
    """Records what was published; for tests and local runs."""

    published: list[OutboxEvent] = field(default_factory=list[OutboxEvent])

    async def publish(self, event: OutboxEvent) -> None:
        self.published.append(event)


def _payload(raw: object) -> dict[str, object]:
    loaded: object = json.loads(raw) if isinstance(raw, str | bytes) else raw
    if not isinstance(loaded, dict):
        raise ValueError("outbox payload is not a JSON object")
    return cast(dict[str, object], loaded)


async def relay_once(publisher: Publisher, batch: int = 100) -> int:
    """Publish up to `batch` unpublished events, oldest first. Returns how many were published."""
    published = 0
    async with relay_engine().connect() as conn:
        rows = (await conn.execute(_CLAIM, {"batch": batch})).all()
        for row in rows:
            event = OutboxEvent(row.id, row.tenant_id, row.event_type, _payload(row.payload))
            try:
                await publisher.publish(event)
            except Exception as exc:  # the event stays unpublished; record why (type only)
                await conn.execute(_FAILED, {"id": row.id, "error": type(exc).__name__})
                continue
            await conn.execute(_PUBLISHED, {"id": row.id})
            published += 1
        await conn.commit()
    return published
