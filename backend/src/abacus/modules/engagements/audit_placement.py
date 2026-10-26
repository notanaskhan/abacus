"""Where an engagement's audit events sit: its client and office (G-02-T08 gap; DEC-458).

The unit of work asks this placer, through `kernel.uow.placement`, for the client and office of
the engagements (and work items) its events name, on its own connection: the same transaction,
so an engagement created in it is found, and the same tenant row-level security. The office is
the work item's when it has one, else the engagement's (`index_facts` reads it the same way).
Identifiers only; nothing here writes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from abacus.kernel.uow.placement import EngagementKey, Placement

_PLACE = text(
    "SELECT asked.engagement_id, asked.work_item_id, e.client_id, "
    "coalesce(w.office_id, e.office_id) AS office_id "
    "FROM unnest(CAST(:engagements AS uuid[]), CAST(:work_items AS uuid[])) "
    "AS asked(engagement_id, work_item_id) "
    "JOIN engagements e ON e.id = asked.engagement_id "
    "LEFT JOIN work_items w ON w.id = asked.work_item_id AND w.engagement_id = e.id"
)


async def place_engagements(
    conn: AsyncConnection, keys: Sequence[EngagementKey]
) -> Mapping[EngagementKey, Placement]:
    rows = await conn.execute(
        _PLACE,
        {"engagements": [k[0] for k in keys], "work_items": [k[1] for k in keys]},
    )
    return {
        (UUID(str(e)), UUID(str(w)) if w is not None else None): Placement(client, office)
        for e, w, client, office in rows.all()
    }
