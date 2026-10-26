"""A client's primary office for its audit events (G-02-T08 gap; DEC-415 Q9; DEC-458).

The unit of work asks this placer, through `kernel.uow.placement`, for the primary office of the
clients its events name when nothing nearer (a work item or an engagement) gives one. Its own
connection and tenant row-level security; identifiers only; nothing here writes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

_OFFICES = text("SELECT id, primary_office_id FROM clients WHERE id = ANY(CAST(:ids AS uuid[]))")


async def client_offices(conn: AsyncConnection, ids: Sequence[UUID]) -> Mapping[UUID, UUID | None]:
    rows = await conn.execute(_OFFICES, {"ids": list(ids)})
    return {UUID(str(client)): office for client, office in rows.all()}
