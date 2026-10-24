"""Engagement team management (SPEC-017). PROTECTED.

Called by the engagements module inside its unit of work, after `lock_ref` and
`authorise(engagement.member_add | member_remove)`. Managers act on seniors, staff and reviewers
only (Q1); an engagement always keeps a partner (Q2, enforced again by the definer functions);
walled people, client users and other firms' users aren't candidates and get the same 404.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound, ServiceUnavailable
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.identity.authz import Forbidden
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import EngagementMemberAdded
from abacus.modules.identity.invitations import revoke_invitations_by
from abacus.modules.identity.member_hooks import member_added
from abacus.modules.identity.repository import (
    MemberDetail,
    display_names,
    engagement_role,
    insert_engagement_member,
    member_details_of,
    my_engagement_roles,
    remove_team_member_row,
    set_member_columns,
    set_team_role,
    team_candidate_ids,
)

# P-07-T30: `specialist` joins the team roles; the EQR (`eqr_reviewer`) is never one of them and
# is set only through `replace_eqr` (EQR never on the team, DEC-327).
StaffRole = Literal["engagement_partner", "manager", "senior", "staff", "reviewer", "specialist"]
MANAGER_MAY_HANDLE: Final = frozenset({"senior", "staff", "reviewer", "specialist"})
EQR_ROLE: Final = "eqr_reviewer"
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
    await revoke_invitations_by(tx, user_id, engagement_id)  # DEC-277


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
    await revoke_invitations_by(tx, user_id, engagement_id)  # DEC-277


# --- ENG-05 (P-07-T30): details, hours, the portal flag and the EQR ------------------------------


async def member_details(tenant: TenantContext, engagement_id: UUID) -> list[MemberDetail]:
    """After the caller's `authorise` of a read on the engagement."""
    return await member_details_of(tenant, engagement_id)


async def set_member_hours(
    tx: UnitOfWork, engagement_id: UUID, user_id: UUID, hours: Decimal | None
) -> None:
    """After `authorise(engagement.member_add)`; 404 for someone not on the firm team."""
    if not await set_member_columns(tx.session, engagement_id, user_id, {"budget_hours": hours}):
        raise NotFound("team_member")
    tx.record(
        "engagement_member.hours_changed",
        target=Target("engagement", engagement_id),
        after=Ref(user_id=user_id),
    )


async def set_member_portal(
    tx: UnitOfWork, engagement_id: UUID, user_id: UUID, shown: bool
) -> None:
    """After `authorise(engagement.update)`: POR-02's team card shows this person or not."""
    if not await set_member_columns(
        tx.session, engagement_id, user_id, {"shown_on_portal": shown}
    ):
        raise NotFound("team_member")
    tx.record(
        "team.portal_visibility_changed",
        target=Target("engagement", engagement_id),
        after=Ref(user_id=user_id),
    )


async def replace_eqr(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, client_id: UUID, user_id: UUID
) -> None:
    """After `authorise(eqr.assign)` and the engagements module's eligibility checks: the
    engagement's EQR becomes `user_id` (any earlier EQR leaves the engagement, its review
    assignments released). The candidate must be an active staff member of the firm, not on the
    engagement and not walled from its client (404 otherwise, as for team candidates)."""
    if _member_removed is None:
        raise ServiceUnavailable("review assignments can't be released")
    if user_id not in await team_candidate_ids(tx.session, engagement_id, client_id):
        raise NotFound("person")
    for row in await member_details_of(ctx.tenant, engagement_id):
        if row.role != EQR_ROLE:
            continue
        if await remove_team_member_row(tx.session, engagement_id, row.user_id) != "ok":
            raise NotFound("team_member")
        await _member_removed(tx, engagement_id, row.user_id, ctx.user_id)
        tx.record(
            "engagement_member.removed",
            target=Target("engagement", engagement_id),
            after=Ref(user_id=row.user_id),
        )
        await revoke_invitations_by(tx, row.user_id, engagement_id)  # DEC-277
    await insert_engagement_member(tx.session, ctx.tenant_id, engagement_id, user_id, EQR_ROLE)
    tx.record(
        "eqr.assigned", target=Target("engagement", engagement_id), after=Ref(user_id=user_id)
    )
    tx.emit(EngagementMemberAdded(engagement_id=engagement_id, user_id=user_id))
    await member_added(tx, engagement_id, user_id)  # asked to confirm independence


Standing = Literal["partner", "team", "eqr", "client", "none"]


async def team_standing(tenant: TenantContext, engagement_id: UUID, user_id: UUID) -> Standing:
    """Where a person stands on an engagement, for ENG-05's rules (never an authorisation):
    its engagement partner, on the team in another role, its EQR, a client user, or not on it."""
    role = await engagement_role(tenant, user_id, engagement_id)
    if role is None:
        return "none"
    standing: dict[str, Standing] = {
        "client_admin": "client",
        "client_contributor": "client",
        EQR_ROLE: "eqr",
        "engagement_partner": "partner",
    }
    return standing.get(role, "team")


@dataclass(frozen=True)
class Served:
    """The engagements a person is engagement partner on, and those they lead or review as EQR
    (for cooling-off and competence, P-07-T30)."""

    as_partner: frozenset[UUID]
    as_partner_or_eqr: frozenset[UUID]


async def engagements_served(tenant: TenantContext, user_id: UUID) -> Served:
    held = await my_engagement_roles(tenant, user_id)
    by_kind: dict[str, set[UUID]] = {"engagement_partner": set(), EQR_ROLE: set()}
    for engagement_id, held_as in held.items():
        by_kind.get(held_as, set()).add(engagement_id)
    partner = frozenset(by_kind["engagement_partner"])
    eqr = frozenset(by_kind[EQR_ROLE])
    return Served(partner, partner | eqr)
