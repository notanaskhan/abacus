"""Region sources for the C4 regions read (T-07-T11; ADR-343 §4). PROTECTED.

`GET /v1/evidence-versions/{v}/regions?match_ids=…` lights a citation's passage in the viewer. A
citation whose source is not the evidence version itself (an instrument clause: its source is
the segmentation) is resolved by its owner, which registers a region source for its match-id
prefix (`ic:`, `tax`). A source answers only for the version asked and only what the reader may
see; it returns ids, pages and boxes and a code-held label, never document text.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Final
from uuid import UUID

from abacus.modules.identity.api import AuthContext

# (match id, page, [x0, top, x1, bottom], label)
RegionHit = tuple[str, int, tuple[float, float, float, float], str | None]
RegionSource = Callable[[AuthContext, UUID, Sequence[str]], Awaitable[list[RegionHit]]]

_sources: dict[str, RegionSource] = {}
_PREFIX: Final = frozenset({"ic:"})


def register_region_source(prefix: str, source: RegionSource) -> None:
    """Once per prefix, at the owner's import (ADR-343: `ic:` is the instrument clause's)."""
    if prefix not in _PREFIX:
        raise ValueError(f"{prefix!r} is not a registered match-id prefix")
    known = _sources.get(prefix)
    if known is not None and known is not source:
        raise ValueError(f"{prefix} already has a region source")
    _sources[prefix] = source


async def owned_regions(
    ctx: AuthContext, version_id: UUID, match_ids: Sequence[str]
) -> list[RegionHit]:
    """Every registered source's regions for the match ids with its prefix."""
    out: list[RegionHit] = []
    for prefix, source in _sources.items():
        wanted = [m for m in match_ids if m.startswith(prefix)]
        if wanted:
            out.extend(await source(ctx, version_id, wanted))
    return out
