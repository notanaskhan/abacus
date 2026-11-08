"""Which workbench session first named each agent run (P-10-T14). Workbench owns `session_items`
(P-10-T04, 0682); the agents module's legacy run backfill asks through this port."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_FIRST_SESSION = text(
    """
    SELECT DISTINCT ON (run_id) run_id, session_id FROM session_items
     WHERE run_id = ANY(:ids)
     ORDER BY run_id, seq
    """
)


async def session_links(session: AsyncSession, run_ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """In the caller's tenant session (RLS scopes it); runs no item names are absent."""
    if not run_ids:
        return {}
    rows = (await session.execute(_FIRST_SESSION, {"ids": list(run_ids)})).all()
    return {row.run_id: row.session_id for row in rows}
