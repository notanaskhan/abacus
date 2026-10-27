"""The C6 v1 run-summary provider for AUD-01's "Processing" pill and AUD-02's audit bar
(A-01-T27; DV-11; DEC-717): each work item's engagement, its active C6 engagement run
(`agents.api.active_engagement_runs`), and the starter's name. Policy ticks are not engagement
runs, so live data never shows Processing for them; with no engagement-run agent registered, no
pill shows at all.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.agents.api import active_engagement_runs
from abacus.modules.assurance.sections import RunSummary
from abacus.modules.engagements.api import work_item_engagement
from abacus.modules.identity.api import names_of


async def run_badges(
    tenant: TenantContext, work_item_ids: Sequence[UUID]
) -> Mapping[UUID, RunSummary]:
    engagement_of: dict[UUID, UUID] = {}
    for work_item in work_item_ids:
        engagement = await work_item_engagement(tenant, work_item)
        if engagement is not None:
            engagement_of[work_item] = engagement
    runs = await active_engagement_runs(tenant, sorted(set(engagement_of.values())))
    if not runs:
        return {}
    names = await names_of(sorted({r.initiator_user_id for r in runs.values()}))
    out: dict[UUID, RunSummary] = {}
    for work_item, engagement in engagement_of.items():
        run = runs.get(engagement)
        if run is None:
            continue
        out[work_item] = RunSummary(
            run_id=run.run_id,
            run_number=run.run_number,
            started_at=run.started_at,
            started_by_user_id=run.initiator_user_id,
            started_by_name=names.get(run.initiator_user_id, ""),
            workpapers_complete=run.workpapers_complete,
            workpapers_total=run.workpapers_total,
            blocked_on_role=run.blocked_on_role,
        )
    return out
