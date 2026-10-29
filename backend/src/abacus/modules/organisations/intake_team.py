"""The intake scope's membership (N-01-T08; DEC-20, P-10; DEC-819).

A person is in the intake scope while they are on a team of kind `intake` (the roster now).
Registered with identity at import (`identity.api.register_intake_scope`). A roster change on an
intake team also emits `access.changed` for the person, so sessions and caches that hold their
reach drop it (`rosters._change`).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.organisations.models import Team
from abacus.modules.organisations.rosters import current_rows

INTAKE = "intake"


async def on_intake_team(tenant: TenantContext, user_id: UUID) -> bool:
    now = current_rows().subquery("roster")
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            select(Team.id)
            .join(now, now.c.team_id == Team.id)
            .where(now.c.user_id == user_id, Team.kind == INTAKE)
            .limit(1)
        )
    return found is not None
