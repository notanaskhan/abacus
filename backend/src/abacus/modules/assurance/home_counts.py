"""HOME-01's audits tile (I-01-T08; `home-and-gates.md` §3): AUD-01's own index counts (A-01-T08),
so the tile and the index never disagree: the audits the viewer may read, by phase tile, narrowed
to an office through the index's office filter (DEC-30: a filter, never a boundary)."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from abacus.modules.assurance.index import IndexFilters, audits_index
from abacus.modules.identity.api import AuthContext
from abacus.modules.platform.api import HomeCount, HomeStatusCount, register_home_count


async def audits(viewer: object, office_id: UUID | None) -> HomeCount:
    ctx = cast(AuthContext, viewer)
    page, _summary = await audits_index(ctx, IndexFilters(office=office_id), cursor=None, limit=1)
    counts = page.counts or {}
    return HomeCount(
        total=page.total,
        by_status=tuple(
            HomeStatusCount(code, n, f"phase={code}") for code, n in counts.items() if n
        ),
    )


def register_home_counts() -> None:
    register_home_count("audits", audits)
