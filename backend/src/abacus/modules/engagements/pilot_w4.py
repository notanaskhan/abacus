"""W4 for the pilot metrics (Q-04-T008; DEC-825): the enrolled work item's client's contacts who
signed in to the portal at least once ÷ invited. Registered with platform at import."""

from __future__ import annotations

from decimal import Decimal

from abacus.kernel.db import TenantContext
from abacus.modules.engagements.hold_scope import work_item_engagement
from abacus.modules.engagements.service import client_of
from abacus.modules.organisations.api import portal_activation
from abacus.modules.platform.api import PilotWeek, pilot_ratio


async def w4_portal_activation(tenant: TenantContext, week: PilotWeek) -> dict[str, Decimal]:
    engagement = await work_item_engagement(tenant, week.work_item_id)
    client = await client_of(tenant, engagement) if engagement is not None else None
    if client is None:
        return {}
    invited, signed_in = await portal_activation(tenant, client)
    share = pilot_ratio(signed_in, invited)
    return {} if share is None else {"w4_portal_activation.v1": share}
