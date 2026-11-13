"""The tax module's work-item hooks for the attention slot (I-02-T11; DEC-88; DEC-4723): an entity
return's next milestone is its K-1 release while any of its packages is unreleased; its dependents
are the returns of its K-1 recipients' client entities for the same year (Ridgeline's K-1s for the
Feld and Shah 1040s). Visibility of both sides is the slot's (`dependents_visible`)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.modules.identity.api import AuthContext

_UNRELEASED: Final = text(
    "SELECT count(*) FROM k1_packages WHERE work_item_id = :r AND status NOT IN "
    "('released', 'viewed', 'downloaded', 'bounced')"
)
_DEPENDENTS: Final = text(
    "SELECT d.work_item_id, d.engagement_id FROM k1_recipients k JOIN tax_returns s "
    "ON s.work_item_id = k.work_item_id JOIN tax_returns d ON d.client_entity_id = "
    "k.client_entity_id AND d.tax_year = s.tax_year WHERE k.work_item_id = :r "
    "AND k.client_entity_id IS NOT NULL ORDER BY d.work_item_id"
)


async def next_milestone(ctx: AuthContext, return_id: UUID) -> str | None:
    async with tenant_session(ctx.tenant) as session:
        open_packages = int(await session.scalar(_UNRELEASED, {"r": return_id}) or 0)
    return "K-1 release" if open_packages else None


async def dependents(ctx: AuthContext, return_id: UUID) -> Sequence[tuple[UUID, UUID]]:
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_DEPENDENTS, {"r": return_id})).all()
    return [(r.work_item_id, r.engagement_id) for r in rows]


__all__ = ["dependents", "next_milestone"]
