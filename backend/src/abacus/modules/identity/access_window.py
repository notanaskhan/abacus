"""Whether a person's access has ended (G-01-T13; DEC-383): the one check every path reads.

A staff member's `access_ends_on` is the last day of access in the firm's time zone
(`kernel.clock`, with the firm's demo clock). Once it has passed, access ends at once, whatever the
hourly access-end job has done: `routing.current_context` refuses the person's requests,
`authorise` refuses an agent acting for them, and `/v1/me` stops listing the firm. The job keeps
the state change (deactivation), the notices and the audit (`access_end.py`).

Kept free of `authz` and the services so that `authz`, `routing` and the job can all import it.
"""

from __future__ import annotations

from datetime import date
from typing import cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.identity.repository import time_zone_of

_ENDS = text(
    "SELECT access_ends_on FROM memberships WHERE user_id = :u AND kind = 'staff' "
    "AND status = 'active'"
)


async def firm_zone(tenant: TenantContext) -> ZoneInfo:
    """The firm's time zone (Central when unset or unknown)."""
    async with tenant_session(tenant) as session:
        name = await time_zone_of(session)
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return clock.FIRM_ZONE


async def access_has_ended(tenant: TenantContext, user_id: UUID) -> bool:
    """Whether the person's active staff membership in `tenant` is past its access end on the
    firm's business date. No end date, or no staff membership: False."""
    async with tenant_session(tenant) as session:
        ends = await session.scalar(_ENDS, {"u": user_id})
    if ends is None:
        return False
    return cast(date, ends) < await clock.today(tenant, await firm_zone(tenant))
