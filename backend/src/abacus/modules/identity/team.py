"""Engagement team management (SPEC-017). PROTECTED.

Called by the engagements module inside its unit of work, after `lock_ref` and
`authorise(engagement.member_add | member_remove)`. Managers act on seniors, staff and reviewers
only (Q1); an engagement always keeps a partner (Q2, enforced again by the definer functions);
walled people, client users and other firms' users aren't candidates and get the same 404.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound, ServiceUnavailable
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.identity.authz import Forbidden
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import EngagementMemberAdded
from abacus.modules.identity.member_hooks import member_added
from abacus.modules.identity.repository import (
    display_names,
    engagement_role,
    insert_engagement_member,
    remove_team_member_row,
    set_team_role,
    team_candidate_ids,
)

StaffRole = Literal["engagement_partner", "manager", "senior", "staff", "reviewer"]
MANAGER_MAY_HANDLE: Final = frozenset({"senior", "staff", "reviewer"})
MemberRemoved = Callable[[UnitOfWork, UUID, UUID, UUID], Awaitable[None]]
_member_removed: MemberRemoved | None = None


class LastPartner(DomainConflict):
    """An engagement keeps at least one engagement partner (SPEC-017 Q2)."""

    code = "last_partner"


@dataclass(frozen=True)
class Candidate:
    user_id: UUID
    display_name: str


def register_member_removed(handler: MemberRemoved) -> None:
    """ADR-106 (TASK-032 D2): evidence releases the person's review assignments."""
    global _member_removed
    if _member_removed is not None and _member_removed is not handler:
        raise RuntimeError("the member-removed handler is already registered")
    _member_removed = handler


async def _within_limits(
    ctx: AuthContext, engagement_id: UUID, roles: set[str], action: str
) -> None:
    caller = await engagement_role(ctx.tenant, ctx.user_id, engagement_id)
    if caller != "engagement_partner" and not roles <= MANAGER_MAY_HANDLE:
        raise Forbidden(action, "role")


async def candidates(
    tenant: TenantContext, engagement_id: UUID, client_id: UUID
) -> list[Candidate]:
    """After the caller's `authorise(engagement.member_add)`."""
    async with tenant_session(tenant) as session:
        ids = await team_candidate_ids(session, engagement_id, client_id)
    names = await display_names(ids)
    found = [Candidate(user_id, names.get(user_id, "")) for user_id in ids]
    return sorted(found, key=lambda c: (c.display_name.casefold(), str(c.user_id)))


async def add_member(
    tx: UnitOfWork,
    ctx: AuthContext,
    engagement_id: UUID,
    client_id: UUID,
    user_id: UUID,
    role: StaffRole,
) -> None:
    await _within_limits(ctx, engagement_id, {role}, "engagement.member_add")
    if user_id not in await team_candidate_ids(tx.session, engagement_id, client_id):
        raise NotFound("person")  # walled, a client user, another firm's, or already a member
    await insert_engagement_member(tx.session, ctx.tenant_id, engagement_id, user_id, role)
    tx.record(
        "engagement_member.added",
        target=Target("engagement", engagement_id),
        after=Ref(user_id=user_id),
    )
    tx.emit(EngagementMemberAdded(engagement_id=engagement_id, user_id=user_id))
    await member_added(tx, engagement_id, user_id)  # SPEC-025: asked to confirm independence


async def change_role(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, user_id: UUID, role: StaffRole
) -> None:
    current = await engagement_role(ctx.tenant, user_id, engagement_id)
    if current is None or current in ("client_admin", "client_contributor"):
        raise NotFound("team_member")
    await _within_limits(ctx, engagement_id, {current, role}, "engagement.member_add")
    outcome = await set_team_role(tx.session, engagement_id, user_id, role)
    if outcome == "last_partner":
        raise LastPartner(str(engagement_id))
    if outcome != "ok":
        raise NotFound("team_member")
    tx.record(
        "engagement_member.role_changed",
        target=Target("engagement", engagement_id),
        after=Ref(user_id=user_id),
    )


async def remove_member(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, user_id: UUID
) -> None:
    """AC-5: their next request is refused; their review assignments here are released."""
    if _member_removed is None:
        raise ServiceUnavailable("review assignments can't be released")
    current = await engagement_role(ctx.tenant, user_id, engagement_id)
    if current is None or current in ("client_admin", "client_contributor"):
        raise NotFound("team_member")
    await _within_limits(ctx, engagement_id, {current}, "engagement.member_remove")
    outcome = await remove_team_member_row(tx.session, engagement_id, user_id)
    if outcome == "last_partner":
        raise LastPartner(str(engagement_id))
    if outcome != "ok":
        raise NotFound("team_member")
    await _member_removed(tx, engagement_id, user_id, ctx.user_id)
    tx.record(
        "engagement_member.removed",
        target=Target("engagement", engagement_id),
        after=Ref(user_id=user_id),
    )
