"""A methodology version's template wrapper (K-03-T19; TASK-9013; K-03 F5; DEC-6019).

1010 wrapped every published methodology version (and every pinned one) in a published template
version; engagements' link points at that wrapper. These reads answer which wrapper a methodology
version has, and which methodology version a template version carries, inside the caller's
session (engagements' unit of work), so the link and the pin see one transaction.
"""

from __future__ import annotations

from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_WRAPPER: Final = text(
    "SELECT template_id, id FROM template_versions WHERE methodology_version_id = :m "
    "AND status = 'published' ORDER BY seq DESC LIMIT 1"
)
_CARRIED: Final = text("SELECT methodology_version_id FROM template_versions WHERE id = :v")


async def template_wrapper_of(
    session: AsyncSession, methodology_version_id: UUID
) -> tuple[UUID, UUID] | None:
    """(template, template version) wrapping the methodology version, or None."""
    row = (await session.execute(_WRAPPER, {"m": methodology_version_id})).first()
    return None if row is None else (cast(UUID, row.template_id), cast(UUID, row.id))


async def wrapped_methodology_version(session: AsyncSession, version_id: UUID) -> UUID | None:
    """The methodology version a template version carries, or None."""
    return cast(UUID | None, await session.scalar(_CARRIED, {"v": version_id}))


__all__ = ["template_wrapper_of", "wrapped_methodology_version"]
