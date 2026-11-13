"""Colleagues of a person (W-02-T09/T13; DEC-4601 Q1; DEC-4717): the active staff members of the
firm who share the person's office or one of their teams. For the Workbench list's membership
("sessions whose owner shares a team or office with me"); the caller still applies walls and
locks per session (DEC-87)."""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.identity.slots import member_teams

_MEMBERS: Final = text(
    "SELECT user_id, office_id FROM memberships WHERE status = 'active' AND kind = 'staff'"
)


async def colleagues_of(tenant: TenantContext, user_id: UUID) -> frozenset[UUID]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_MEMBERS)).all()
    offices = {r.user_id: r.office_id for r in rows}
    mine = offices.get(user_id)
    same_office = {u for u, o in offices.items() if mine is not None and o == mine}
    teams = await member_teams(tenant, list(offices))
    my_teams = set(teams.get(user_id, []))
    same_team = {u for u, ts in teams.items() if my_teams & set(ts)}
    return frozenset((same_office | same_team) - {user_id})


__all__ = ["colleagues_of"]
