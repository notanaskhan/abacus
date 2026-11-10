"""Who may be mentioned or assigned (P-05-T05, T06; SPEC-650 AC-5, AC-6, AC-17, AC-19; DEC-43).

Only people on the engagement who may read its comments (or to-dos), by the same `authorise`
(roles, walls, independence): never the agent, which is not a person. Firm members not on the
engagement are listed greyed for a mention search, never selectable; a person walled from the
client is absent everywhere and no count reveals them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from uuid import UUID

from abacus.modules.engagements.api import EngagementRef, engagement_label, get_ref
from abacus.modules.identity.api import (
    ROLE_LABELS,
    AuthContext,
    authorise,
    available_staff,
    could,
    engagement_team,
    names_of,
)

# Client and service roles on an engagement are not "the team" for comments and to-dos.
TEAM_ROLES: Final = frozenset(
    {"engagement_partner", "manager", "senior", "staff", "reviewer", "eqr_reviewer", "specialist"}
)
MAX_NOT_ON_ENGAGEMENT: Final = 10


@dataclass(frozen=True)
class Candidate:
    user_id: UUID
    name: str
    title: str | None
    is_self: bool
    selectable: bool = True
    reason: str | None = None


@dataclass(frozen=True)
class Candidates:
    team_label: str
    members: list[Candidate]
    not_on_engagement: list[Candidate]


def initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    if not parts:
        return "?"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


def matches(name: str, q: str | None) -> bool:
    """A word of the name starts with `q` (case-insensitive): "Ha" finds Hannah Leclerc."""
    if not q:
        return True
    needle = q.strip().casefold()
    return any(word.casefold().startswith(needle) for word in name.split()) or (
        name.casefold().startswith(needle)
    )


async def team_members(ctx: AuthContext, ref: EngagementRef, action: str) -> list[Candidate]:
    """The engagement's people who may `action` on it now, the caller marked "(you)"."""
    found: list[Candidate] = []
    for member in await engagement_team(ctx, ref.id):
        if member.role not in TEAM_ROLES:
            continue
        if member.user_id != ctx.user_id and not await could(
            ctx, member.user_id, action, ref.resource()
        ):
            continue  # walled, independence not confirmed, or no longer allowed
        found.append(
            Candidate(
                member.user_id,
                member.display_name,
                ROLE_LABELS.get(member.role),
                member.user_id == ctx.user_id,
            )
        )
    return sorted(found, key=lambda c: (c.name.casefold(), str(c.user_id)))


async def team_label(ctx: AuthContext, engagement_id: UUID) -> str:
    label = await engagement_label(ctx.tenant, engagement_id)
    return f"{label.name} team" if label is not None else "Engagement team"


async def mention_candidates(ctx: AuthContext, engagement_id: UUID, q: str | None) -> Candidates:
    """AC-5, AC-6, after `comment.create` on the engagement."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "comment.create", ref.resource())
    members = await team_members(ctx, ref, "comment.read")
    on = {m.user_id for m in members}
    greyed: list[Candidate] = []
    if q and q.strip():
        others = sorted(await available_staff(ctx.tenant, ref.client_id) - on, key=str)
        names = await names_of(others)
        greyed = sorted(
            (
                Candidate(u, names.get(u, ""), None, False, False, "not_on_engagement")
                for u in others
                if matches(names.get(u, ""), q)
            ),
            key=lambda c: c.name.casefold(),
        )[:MAX_NOT_ON_ENGAGEMENT]
    return Candidates(
        await team_label(ctx, engagement_id),
        [m for m in members if matches(m.name, q)],
        greyed,
    )


async def mentionable(ctx: AuthContext, ref: EngagementRef) -> dict[UUID, Candidate]:
    """Who a comment on this engagement may mention (the author included, then dropped)."""
    return {m.user_id: m for m in await team_members(ctx, ref, "comment.read")}


async def assignee_candidates(
    ctx: AuthContext, engagement_id: UUID, q: str | None
) -> list[Candidate]:
    """AC-17, after `todo.assign` on the engagement: members only, never the agent."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "todo.assign", ref.resource())
    return [m for m in await team_members(ctx, ref, "todo.read") if matches(m.name, q)]


async def assignable(ctx: AuthContext, ref: EngagementRef, user_id: UUID) -> bool:
    """AC-19: a human member of the engagement who may read its to-dos, not walled."""
    return any(m.user_id == user_id for m in await team_members(ctx, ref, "todo.read"))
