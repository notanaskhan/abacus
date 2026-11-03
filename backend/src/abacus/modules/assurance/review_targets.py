"""The SUM schedule as a C3 reviewable (A-06-T15; A-06 §3 F7; AUD-17; DEC-2215).

The newest conclusion snapshot of each audit work item's SUM is one `sum_schedule` reviewable,
its content hash the snapshot's inputs hash: a new snapshot leaves its sign-offs stale. Its
preparer is the person who froze it.
"""

from __future__ import annotations

from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.review.api import Reviewable, ReviewableFacts

SUM_TARGET: Final = "sum_schedule"
_BY_ENGAGEMENT = text(
    "SELECT DISTINCT ON (work_item_id) work_item_id, engagement_id, version_no, inputs_hash, "
    "created_by FROM sum_snapshots WHERE purpose = 'conclusion' AND engagement_id = :e "
    "ORDER BY work_item_id, version_no DESC"
)
_BY_ITEM = text(
    "SELECT DISTINCT ON (work_item_id) work_item_id, engagement_id, version_no, inputs_hash, "
    "created_by FROM sum_snapshots WHERE purpose = 'conclusion' AND work_item_id = :w "
    "ORDER BY work_item_id, version_no DESC"
)


async def sum_reviewables(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_BY_ENGAGEMENT, {"e": engagement_id})).mappings().all()
    return [
        Reviewable(
            SUM_TARGET,
            cast(UUID, r["work_item_id"]),
            "SUM",
            "Summary of uncorrected misstatements",
            cast(str, r["inputs_hash"]),
            True,
        )
        for r in rows
    ]


async def sum_facts(tenant: TenantContext, work_item_id: UUID) -> ReviewableFacts | None:
    async with tenant_session(tenant) as session:
        r = (await session.execute(_BY_ITEM, {"w": work_item_id})).mappings().one_or_none()
    if r is None:
        return None
    return ReviewableFacts(
        SUM_TARGET,
        work_item_id,
        cast(UUID, r["engagement_id"]),
        cast(str, r["inputs_hash"]),
        int(cast(int, r["version_no"])),
        frozenset({cast(UUID, r["created_by"])}),
        label="Summary of uncorrected misstatements",
    )
