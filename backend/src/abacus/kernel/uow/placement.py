"""Where an audit event sits: its client and office (G-02-T08 gap; SPEC-349 §4, §7; DEC-458).
PROTECTED.

`audit_events.client_id` and `office_id` (migration 0172) let the explorer key walls on a stored
client and filter by office. The unit of work fills them at insert, so they are part of the
event's leaf (`chain.LEAF_V2_COLUMNS`) from the start and never change afterwards.

The kernel owns no client, engagement or office table and imports no module (ADR-101): the
modules that own them register a placer here, as identity registers its session resolver in
`kernel.request_context`, and the unit of work calls them on its own connection (the same
transaction and tenant row-level security):

- the engagement placer: `(engagement, work item or None)` pairs -> the engagement's client and
  the office (the work item's, else the engagement's);
- the client placer: client ids -> the client's primary office.

Unregistered or answering nothing, the column stays null: the explorer's ref-based wall rule
still applies to such rows, as it does to history.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class Placement:
    client_id: UUID | None
    office_id: UUID | None


EngagementKey = tuple[UUID, UUID | None]  # (engagement, work item)
EngagementPlacer = Callable[
    [AsyncConnection, Sequence[EngagementKey]], Awaitable[Mapping[EngagementKey, Placement]]
]
ClientPlacer = Callable[[AsyncConnection, Sequence[UUID]], Awaitable[Mapping[UUID, UUID | None]]]

_engagement: list[EngagementPlacer] = []
_client: list[ClientPlacer] = []


def register_engagement_placer(placer: EngagementPlacer) -> None:
    """Engagements' lookup (one per process)."""
    if _engagement and _engagement[0] is not placer:
        raise ValueError("an engagement placer is already registered")
    _engagement[:] = [placer]


def register_client_placer(placer: ClientPlacer) -> None:
    """Organisations' lookup of a client's primary office (one per process)."""
    if _client and _client[0] is not placer:
        raise ValueError("a client placer is already registered")
    _client[:] = [placer]


class PlacementMismatch(ValueError):
    """A writer passed a client or office its engagement does not have (a bug, never stored)."""


@dataclass(frozen=True)
class Placeable:
    """What the unit of work knows about one event before placing it."""

    engagement_id: UUID | None
    work_item_id: UUID | None
    client_target: UUID | None  # the target, when it is a client
    client_id: UUID | None  # the writer's explicit scope values
    office_id: UUID | None


async def place(conn: AsyncConnection, events: Sequence[Placeable]) -> list[Placement]:
    """Each event's client and office, in order: one query per placer for the whole batch."""
    wanted: set[EngagementKey] = set()
    for e in events:
        if e.engagement_id is not None:
            wanted.add((e.engagement_id, e.work_item_id))
    keys = sorted(wanted, key=lambda k: (str(k[0]), str(k[1])))
    by_engagement: Mapping[EngagementKey, Placement] = (
        await _engagement[0](conn, keys) if keys and _engagement else {}
    )
    placed: list[Placement] = []
    for e in events:
        client, office = e.client_id, e.office_id
        if e.engagement_id is not None:
            found = by_engagement.get((e.engagement_id, e.work_item_id))
            if found is not None:
                client = _agree(e.client_id, found.client_id, "client")
                office = _agree(e.office_id, found.office_id, "office")
        elif e.client_target is not None:
            client = _agree(e.client_id, e.client_target, "client")
        placed.append(Placement(client, office))
    # An event with a client and no office takes the client's primary office (DEC-415 Q9).
    clients = sorted({p.client_id for p in placed if p.client_id and p.office_id is None}, key=str)
    if clients and _client:
        offices = await _client[0](conn, clients)
        placed = [
            Placement(p.client_id, offices.get(p.client_id))
            if p.client_id is not None and p.office_id is None
            else p
            for p in placed
        ]
    return placed


def _agree(explicit: UUID | None, derived: UUID | None, what: str) -> UUID | None:
    """The derived value wins; an explicit one must match it."""
    if explicit is not None and derived is not None and explicit != derived:
        raise PlacementMismatch(f"the scope's {what} is not its engagement's")
    return derived if derived is not None else explicit


__all__ = [
    "ClientPlacer",
    "EngagementKey",
    "EngagementPlacer",
    "Placeable",
    "Placement",
    "PlacementMismatch",
    "place",
    "register_client_placer",
    "register_engagement_placer",
]
