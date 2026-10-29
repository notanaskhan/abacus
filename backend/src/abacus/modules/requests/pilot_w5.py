"""W5 for the pilot metrics (Q-04-T008; DEC-825): received ÷ asked over the enrolled work item's
published PBC binders' client-visible requests, which reach the client only through the portal.
Registered with platform at import."""

from __future__ import annotations

from decimal import Decimal

from abacus.kernel.db import TenantContext
from abacus.modules.platform.api import PilotWeek, pilot_ratio
from abacus.modules.requests.source_documents import pbc_counts_of


async def w5_pbc_via_portal(tenant: TenantContext, week: PilotWeek) -> dict[str, Decimal]:
    received, total = (await pbc_counts_of(tenant, [week.work_item_id])).get(
        week.work_item_id, (0, 0)
    )
    share = pilot_ratio(received, total)
    return {} if share is None else {"w5_pbc_via_portal.v1": share}
