"""A working paper as a comment and to-do anchor (P-05-T09; SPEC-650 AC-1, AC-15; P-05 §4.1).

`workpaper` is registered into collaboration's anchor slot (`collaboration.api.register_anchor`),
so collaboration never imports this module. The locator pins a place on the paper:

- `{"sheet": "Exceptions", "cell": "A3"}`: one cell (AUD-09's grid, "Exceptions!A3");
- `{"sheet": "Exceptions", "row": 6}`: one row ("Exceptions row 6");
- `{"sheet": "Exceptions"}` or no locator: the sheet, or the whole paper.

The label is composed at read time and never stored ("Northwind · WP-7 Revenue cut-off ·
Exceptions!A3"). A paper is internal: its threads are never shareable with a client
(`client_visible` false), and its anchor is a reviewable (`workpaper`), so "Convert to review
note…" raises the note on the paper itself with the cell or row as the note's anchor.
"""

from __future__ import annotations

import re
from typing import Final
from uuid import UUID

from sqlalchemy import select

from abacus.kernel.db import tenant_session
from abacus.modules.collaboration.api import AnchorFacts, Locator
from abacus.modules.engagements.api import engagement_label, get_ref
from abacus.modules.identity.api import AuthContext
from abacus.modules.workpapers.models import Workpaper

KIND: Final = "workpaper"
_CELL: Final = re.compile(r"^[A-Z]{1,3}[1-9][0-9]{0,6}$")
MAX_SHEET: Final = 60
MAX_ROW: Final = 1_048_576


def place_of(locator: Locator | None) -> str | None:
    """The locator as the note's anchor text (`Exceptions!A3`, `Exceptions row 6`), or None when
    it is not a valid place on a paper."""
    if not locator:
        return ""
    sheet = locator.get("sheet")
    if not isinstance(sheet, str) or not sheet.strip() or len(sheet) > MAX_SHEET:
        return None
    cell, row = locator.get("cell"), locator.get("row")
    if cell is not None and row is not None:
        return None
    if cell is not None:
        if not isinstance(cell, str) or not _CELL.fullmatch(cell):
            return None
        return f"{sheet}!{cell}"
    if row is not None:
        if not isinstance(row, int) or isinstance(row, bool) or not 1 <= row <= MAX_ROW:
            return None
        return f"{sheet} row {row}"
    return sheet


class WorkpaperAnchors:
    """AUD-09 rows and cells (P-05-T09)."""

    locator_keys: frozenset[str] = frozenset({"sheet", "cell", "row"})

    async def facts(
        self, ctx: AuthContext, anchor_id: UUID, locator: Locator | None
    ) -> AnchorFacts | None:
        place = place_of(locator)
        if place is None:
            return None
        async with tenant_session(ctx.tenant) as session:
            paper = (
                await session.execute(
                    select(
                        Workpaper.engagement_id,
                        Workpaper.work_item_id,
                        Workpaper.code,
                        Workpaper.title,
                    ).where(Workpaper.id == anchor_id)
                )
            ).first()
        if paper is None:
            return None
        ref = await get_ref(ctx, paper.engagement_id)  # 404 for a walled or unknown engagement
        label = await engagement_label(ctx.tenant, ref.id)
        client = label.client_name if label is not None else ""
        parts = [p for p in (client, f"{paper.code} {paper.title}".strip(), place) if p]
        return AnchorFacts(
            ctx.tenant_id,
            ref.id,
            ref.client_id,
            " · ".join(parts),
            archived=ref.archived,
            work_item_id=paper.work_item_id,
        )


WORKPAPER_ANCHORS: Final = WorkpaperAnchors()

__all__ = ["KIND", "WORKPAPER_ANCHORS", "WorkpaperAnchors", "place_of"]
