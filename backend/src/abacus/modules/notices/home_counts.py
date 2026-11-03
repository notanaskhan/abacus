"""HOME-01's notices tile (N-04-T06; I-01's `platform.register_home_count`): the viewer's visible
open notices by tile, the same rows NOT-01 tallies (DEC-43). Counts only; no names or amounts."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from abacus.modules.identity.api import AuthContext
from abacus.modules.notices import service
from abacus.modules.platform.api import HomeCount, HomeStatusCount, register_home_count


async def notices(viewer: object, office_id: UUID | None) -> HomeCount:
    ctx = cast(AuthContext, viewer)  # HOME-01's viewer is the signed-in person, never an agent
    rows = [n for n in await service.visible_notices(ctx) if n.open]
    on = await service.on_day(ctx)
    counts = service.tallies(rows, on)
    return HomeCount(
        total=counts.open,
        by_status=tuple(
            HomeStatusCount(tile, n, f"tile={tile}") for tile, n in counts.tiles.items() if n
        ),
        target_filter=None,
    )


def register_home_counts() -> None:
    register_home_count("notices", notices)
