"""The `sheet` and `sheet_row` comment anchors (K-03-T22/T23; TASK-9029; DEC-6034).

SHT-01's row drawer hosts a thread on one row (its Comments tab) and SHT-02's "Suggest to <name>…"
a thread on the sheet. The sheet's own read authorises both (`sheet.read`, so a walled engagement
answers 404); the label is the client, the sheet's title and, for a row, its key.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.collaboration.api import AnchorFacts, Locator
from abacus.modules.engagements.api import engagement_label, get_ref
from abacus.modules.identity.api import AuthContext, Forbidden

SHEET: Final = "sheet"
ROW: Final = "sheet_row"

_OF_SHEET: Final = text("SELECT id, title, NULL AS row_key FROM sheets WHERE id = :id")
_OF_ROW: Final = text(
    "SELECT s.id, s.title, r.row_key FROM sheet_rows r JOIN sheets s ON s.id = r.sheet_id "
    "WHERE r.id = :id"
)


async def _facts(ctx: AuthContext, anchor_id: UUID, row: bool) -> AnchorFacts | None:
    from abacus.modules.workpapers import sheets as sh

    async with tenant_session(ctx.tenant) as session:
        found = (await session.execute(_OF_ROW if row else _OF_SHEET, {"id": anchor_id})).first()
    if found is None:
        return None
    try:
        sheet = await sh.sheet_scope(ctx, found.id)
    except (NotFound, Forbidden):
        return None
    ref = await get_ref(ctx, sheet.engagement_id)  # 404 for a walled or unknown engagement
    label = await engagement_label(ctx.tenant, ref.id)
    client = label.client_name if label is not None else ""
    parts = [p for p in (client, str(found.title), str(found.row_key or "")) if p]
    return AnchorFacts(
        ctx.tenant_id,
        ref.id,
        ref.client_id,
        " · ".join(parts)[:200],
        archived=ref.archived,
        work_item_id=sheet.work_item_id,
    )


class SheetAnchors:
    locator_keys: frozenset[str] = frozenset()

    async def facts(
        self, ctx: AuthContext, anchor_id: UUID, locator: Locator | None
    ) -> AnchorFacts | None:
        del locator
        return await _facts(ctx, anchor_id, row=False)


class SheetRowAnchors:
    locator_keys: frozenset[str] = frozenset()

    async def facts(
        self, ctx: AuthContext, anchor_id: UUID, locator: Locator | None
    ) -> AnchorFacts | None:
        del locator
        return await _facts(ctx, anchor_id, row=True)


SHEET_ANCHORS: Final = SheetAnchors()
ROW_ANCHORS: Final = SheetRowAnchors()

__all__ = ["ROW", "ROW_ANCHORS", "SHEET", "SHEET_ANCHORS", "SheetAnchors", "SheetRowAnchors"]
