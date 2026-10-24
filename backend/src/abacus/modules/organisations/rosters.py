"""Team rosters for identity's people screens (G-01-T05): a person's teams, read and replaced
through identity's `register_member_teams` slot. A roster row is the fact; replacing someone's
teams removes and adds rows (team membership history arrives with G-01-T08)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, insert, select

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import UnitOfWork
from abacus.modules.organisations.models import Team, TeamRoster


async def member_teams(tenant: TenantContext, user_ids: list[UUID]) -> dict[UUID, list[UUID]]:
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(TeamRoster.user_id, TeamRoster.team_id)
            .where(TeamRoster.user_id.in_(user_ids))
            .order_by(TeamRoster.added_at, TeamRoster.team_id)
        )
    teams: dict[UUID, list[UUID]] = {}
    for user, team in rows:
        teams.setdefault(user, []).append(team)
    return teams


async def set_member_teams(
    tx: UnitOfWork, tenant_id: UUID, user_id: UUID, team_ids: list[UUID]
) -> bool:
    """False (and nothing written) when a team isn't the firm's."""
    wanted = list(dict.fromkeys(team_ids))
    if wanted:
        known = await tx.session.scalar(
            select(func.count()).select_from(Team).where(Team.id.in_(wanted))
        )
        if known != len(wanted):
            return False
    await tx.session.execute(
        delete(TeamRoster).where(
            TeamRoster.user_id == user_id, TeamRoster.team_id.not_in(wanted or [UUID(int=0)])
        )
    )
    held = set(
        (
            await tx.session.execute(
                select(TeamRoster.team_id).where(TeamRoster.user_id == user_id)
            )
        ).scalars()
    )
    for team in wanted:
        if team not in held:
            await tx.session.execute(
                insert(TeamRoster).values(tenant_id=tenant_id, team_id=team, user_id=user_id)
            )
    return True
