"""The evidence board's summary strip (SPEC-022 AC-5; TASK-038).

"Retrieved, never asked" (Q5): items whose first evidence was retrieved, so the client never had
to supply it. Follow-ups (increment 8) will add "and never followed up".
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence.repository import methods_of
from abacus.modules.identity.api import AuthContext, authorise
from abacus.modules.requests.api import fulfilled_versions, request_items_for

_RETRIEVABLE = frozenset({"A", "B", "C"})


@dataclass(frozen=True)
class BoardSummary:
    total: int
    by_status: dict[str, int]
    by_tier: dict[str, int]
    unclassified: int
    retrieved_never_asked: int
    retrievable_share: float | None  # of classified items; None when none are classified


async def board_summary(ctx: AuthContext, engagement_id: UUID) -> BoardSummary:
    items = await request_items_for(ctx, engagement_id)
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "review.read", ref.resource())
    first: dict[UUID, tuple[datetime, UUID]] = {}
    for fulfilled in await fulfilled_versions(ctx, engagement_id):
        seen = first.get(fulfilled.request_item_id)
        key = (fulfilled.fulfilled_at, fulfilled.evidence_version_id)
        if seen is None or key < seen:
            first[fulfilled.request_item_id] = key
    async with tenant_session(ctx.tenant) as session:
        methods = await methods_of(
            session, ctx, engagement_id, [version for _, version in first.values()]
        )
    visible_ids = {item.id for item in items}
    never_asked = sum(
        1
        for item_id, (_, version) in first.items()
        if item_id in visible_ids and methods.get(version) == "retrieved"
    )
    tiers = Counter(i.retrievability_tier for i in items if i.retrievability_tier is not None)
    classified = sum(tiers.values())
    retrievable = sum(n for tier, n in tiers.items() if tier in _RETRIEVABLE)
    return BoardSummary(
        total=len(items),
        by_status=dict(Counter(i.status for i in items)),
        by_tier=dict(tiers),
        unclassified=len(items) - classified,
        retrieved_never_asked=never_asked,
        retrievable_share=None if classified == 0 else round(retrievable / classified, 4),
    )
