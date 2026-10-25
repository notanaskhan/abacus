"""Team rosters (G-01-T05, G-01-T08): a person's teams, read and replaced through identity's
`register_member_teams` slot, and a team's roster for ADM-03.

The table is insert-only history (0150, the `work_item_assignments` shape): adding someone is a
row, removing them is a new row with `removed_at`, and the roster is each person's latest row per
team when it carries none. Every change is audited (`team.member_added`, `team.member_removed`)
and keeps the person's service lines in agreement with their service-line teams (AC7.4) through
identity, in the same unit of work.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.identity.api import reconcile_service_lines
from abacus.modules.organisations.events import TeamMemberAdded, TeamMemberRemoved
from abacus.modules.organisations.models import Team, TeamRoster


def _latest() -> Select[UUID, UUID, datetime | None, datetime]:
    """Each (team, person)'s latest roster row."""
    return (
        select(TeamRoster.team_id, TeamRoster.user_id, TeamRoster.removed_at, TeamRoster.added_at)
        .distinct(TeamRoster.team_id, TeamRoster.user_id)
        .order_by(TeamRoster.team_id, TeamRoster.user_id, TeamRoster.seq.desc())
    )


def current_rows() -> Select[UUID, UUID, datetime]:
    """The roster now: (team, person, since), for people on a team."""
    latest = _latest().subquery("latest")
    query: Select[UUID, UUID, datetime] = select(
        latest.c.team_id, latest.c.user_id, latest.c.added_at
    ).where(latest.c.removed_at.is_(None))
    return query


async def member_teams(tenant: TenantContext, user_ids: list[UUID]) -> dict[UUID, list[UUID]]:
    async with tenant_session(tenant) as session:
        return await _member_teams(session, user_ids)


async def _member_teams(session: AsyncSession, user_ids: list[UUID]) -> dict[UUID, list[UUID]]:
    now = current_rows().subquery("roster")
    rows = await session.execute(
        select(now.c.user_id, now.c.team_id)
        .where(now.c.user_id.in_(user_ids))
        .order_by(now.c.added_at, now.c.team_id)
    )
    teams: dict[UUID, list[UUID]] = {}
    for user, team in rows:
        teams.setdefault(user, []).append(team)
    return teams


async def rosters(session: AsyncSession, team_ids: Iterable[UUID]) -> dict[UUID, list[UUID]]:
    """Each team's members, in the order they joined."""
    wanted = list(team_ids)
    if not wanted:
        return {}
    now = current_rows().subquery("roster")
    rows = await session.execute(
        select(now.c.team_id, now.c.user_id)
        .where(now.c.team_id.in_(wanted))
        .order_by(now.c.added_at, now.c.user_id)
    )
    found: dict[UUID, list[UUID]] = {team: [] for team in wanted}
    for team, user in rows:
        found[team].append(user)
    return found


async def _change(
    tx: UnitOfWork, tenant_id: UUID, team_id: UUID, user_id: UUID, *, added: bool
) -> None:
    values: dict[str, object] = {"tenant_id": tenant_id, "team_id": team_id, "user_id": user_id}
    if not added:
        values["removed_at"] = func.abacus_now()
    await tx.session.execute(insert(TeamRoster).values(**values))
    tx.record(
        "team.member_added" if added else "team.member_removed",
        target=Target("team", team_id),
        after=Ref(user_id=user_id),
    )
    event = TeamMemberAdded if added else TeamMemberRemoved
    tx.emit(event(team_id=team_id, user_id=user_id))


async def set_member_teams(
    tx: UnitOfWork, tenant_id: UUID, user_id: UUID, team_ids: list[UUID]
) -> bool:
    """Replace one person's teams. False (and nothing written) when a team isn't the firm's."""
    wanted = list(dict.fromkeys(team_ids))
    if wanted:
        known = await tx.session.scalar(
            select(func.count()).select_from(Team).where(Team.id.in_(wanted))
        )
        if known != len(wanted):
            return False
    held = (await _member_teams(tx.session, [user_id])).get(user_id, [])
    for team in held:
        if team not in wanted:
            await _change(tx, tenant_id, team, user_id, added=False)
    for team in wanted:
        if team not in held:
            await _change(tx, tenant_id, team, user_id, added=True)
    if set(held) != set(wanted):
        await reconcile_service_lines(tx, user_id)
    return True


async def set_roster(
    tx: UnitOfWork, tenant_id: UUID, team_id: UUID, member_ids: list[UUID]
) -> tuple[list[UUID], list[UUID]]:
    """Replace one team's roster; (added, removed). The caller checked the people are the
    firm's active staff."""
    wanted = list(dict.fromkeys(member_ids))
    held = (await rosters(tx.session, [team_id]))[team_id]
    removed = [user for user in held if user not in wanted]
    added = [user for user in wanted if user not in held]
    for user in removed:
        await _change(tx, tenant_id, team_id, user, added=False)
    for user in added:
        await _change(tx, tenant_id, team_id, user, added=True)
    for user in (*removed, *added):
        await reconcile_service_lines(tx, user)
    return added, removed


async def service_line_teams(
    tx: UnitOfWork, user_id: UUID
) -> tuple[frozenset[str], frozenset[str]]:
    """(the lines the firm's service-line teams manage, the lines this person's teams hold)."""
    managed = frozenset(
        (
            await tx.session.execute(
                select(Team.service_line).where(
                    Team.kind == "service_line", Team.service_line.is_not(None)
                )
            )
        ).scalars()
    )
    if not managed:
        return frozenset(), frozenset()
    now = current_rows().subquery("roster")
    held = frozenset(
        (
            await tx.session.execute(
                select(Team.service_line)
                .join(now, now.c.team_id == Team.id)
                .where(now.c.user_id == user_id, Team.kind == "service_line")
            )
        ).scalars()
    )
    return frozenset(str(line) for line in managed), frozenset(str(line) for line in held)
