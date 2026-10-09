"""Sign-in and the request context (ADR-002, ADR-029). PROTECTED. TASK-007 design §4.

1. Verify the bearer token (401 if not valid).
2. Resolve the user by issuer and subject (403 if unknown).
3. Load the user's active memberships, fresh on every request.
4. Choose the active tenant: the only membership, or the one named in `X-Abacus-Tenant`, which
   counts only if it matches an active membership. Otherwise 403.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity.authz import Forbidden, Resource, authorise
from abacus.modules.identity.context import AuthContext, NoActiveTenant
from abacus.modules.identity.events import EngagementMemberAdded, EngagementMemberSelfJoined
from abacus.modules.identity.member_hooks import member_added
from abacus.modules.identity.repository import (
    EngagementRole,
    MembershipRecord,
    UserRecord,
    WallRecord,
    active_firm_admins,
    active_memberships,
    active_staff_ids,
    all_walls,
    display_names,
    engagement_members_of,
    engagement_role,
    find_user,
    firm_name_of,
    get_wall,
    insert_engagement_member,
    insert_wall,
    remove_wall,
    team_candidate_ids,
    walled_clients,
)
from abacus.modules.identity.tokens import InvalidToken, VerifiedIdentity, token_verifier

TENANT_HEADER = "X-Abacus-Tenant"
CREATOR_ROLE: EngagementRole = "engagement_partner"


class Unauthenticated(Exception):
    """No valid bearer token."""


@dataclass(frozen=True)
class SignedIn:
    """A verified user and their active memberships; no tenant chosen yet."""

    user: UserRecord
    identity: VerifiedIdentity
    memberships: list[MembershipRecord]


def _bearer(authorization: str | None) -> str:
    if authorization is None:
        raise Unauthenticated("missing bearer token")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise Unauthenticated("missing bearer token")
    return token.strip()


def verify_bearer(authorization: str | None) -> VerifiedIdentity:
    """The firm-user issuer's verification of a bearer token (`InvalidToken` otherwise)."""
    return token_verifier().verify(_bearer(authorization))


async def sign_in(authorization: str | None) -> SignedIn:
    try:
        identity = token_verifier().verify(_bearer(authorization))
    except InvalidToken as exc:
        raise Unauthenticated(str(exc)) from None
    user = await find_user(identity.issuer, identity.subject)
    if user is None:
        raise NoActiveTenant("unknown user")
    return SignedIn(user, identity, await active_memberships(user.id))


def choose_tenant(signed_in: SignedIn, requested: str | None) -> AuthContext:
    memberships = signed_in.memberships
    if requested is not None:
        try:
            tenant_id = UUID(requested)
        except ValueError:
            raise NoActiveTenant("malformed tenant") from None
        chosen = [m for m in memberships if m.tenant_id == tenant_id]
    else:
        chosen = memberships if len(memberships) == 1 else []
    if len(chosen) != 1:
        raise NoActiveTenant("no active membership chosen")
    membership = chosen[0]
    user_id = signed_in.user.id
    return AuthContext(
        tenant=TenantContext(membership.tenant_id, "human", str(user_id)),
        user_id=user_id,
        membership_id=membership.membership_id,
        firm_role=membership.firm_role,
        mfa_at=signed_in.identity.mfa_at,
    )


@dataclass(frozen=True)
class TeamMember:
    user_id: UUID
    display_name: str
    role: EngagementRole


async def add_creator_as_partner(tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID) -> None:
    """The creator of an engagement becomes its engagement partner (AC-4; TASK-008 Q2), inside the
    creating unit of work, after `engagement.create` was authorised. The only way to add a member
    until `engagement.member_add` has its own route; who and which role are not the caller's to
    choose."""
    await insert_engagement_member(
        tx.session, ctx.tenant_id, engagement_id, ctx.user_id, CREATOR_ROLE
    )
    tx.record(
        "engagement_member.added",
        target=Target("engagement", engagement_id),
        after=Ref(user_id=ctx.user_id),
    )
    await member_added(tx, engagement_id, ctx.user_id)  # SPEC-025: confirm independence


async def available_staff(tenant: TenantContext, client_id: UUID) -> frozenset[UUID]:
    """Active staff of the firm not walled from the client (SPEC-025, TASK-048: who of last year's
    team can be proposed), for a caller that authorised `roll_forward.read`. A fresh engagement ID
    has no members, so `team_candidate_ids` excludes nobody for being on a team."""
    async with tenant_session(tenant) as session:
        return frozenset(await team_candidate_ids(session, uuid4(), client_id))


async def add_rolled_forward_member(
    tx: UnitOfWork,
    ctx: AuthContext,
    engagement_id: UUID,
    client_id: UUID,
    user_id: UUID,
    role: EngagementRole,
) -> None:
    """SPEC-025 AC-2 (TASK-048 D2): a confirmed member of last year's team joins the engagement
    being created, inside the creating unit of work, after `engagement.create` and
    `roll_forward.read` were authorised. `team.add_member` can't run here: its check of the
    caller's own role reads outside this transaction, where the creator isn't partner yet. The
    person is re-checked: active staff, not walled from the client, not already on the team."""
    if user_id not in await team_candidate_ids(tx.session, engagement_id, client_id):
        raise NotFound("person")  # left, walled, a client user, or already a member
    await insert_engagement_member(tx.session, ctx.tenant_id, engagement_id, user_id, role)
    tx.record(
        "engagement_member.added",
        target=Target("engagement", engagement_id),
        after=Ref(user_id=user_id),
    )
    tx.emit(EngagementMemberAdded(engagement_id=engagement_id, user_id=user_id))
    await member_added(tx, engagement_id, user_id)  # SPEC-025: asked to confirm independence


class AlreadyMember(DomainConflict):
    """The caller is already on the engagement's team."""

    code = "already_member"


SELF_JOIN_ROLE: EngagementRole = "reviewer"


async def add_self_joined_admin(tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID) -> None:
    """ADR-024: a firm admin joins to see content, as `reviewer` (content reads, no decisions;
    TASK-028 D1), inside the caller's unit of work after `authorise(engagement.self_join)`. The
    `notify: engagement_team` obligation is met by the event emitted here (SPEC-013 AC-8)."""
    if await engagement_role(ctx.tenant, ctx.user_id, engagement_id) is not None:
        raise AlreadyMember(str(engagement_id))
    await insert_engagement_member(
        tx.session, ctx.tenant_id, engagement_id, ctx.user_id, SELF_JOIN_ROLE
    )
    tx.record(
        "engagement_member.self_joined",
        target=Target("engagement", engagement_id),
        after=Ref(user_id=ctx.user_id),
    )
    tx.emit(EngagementMemberSelfJoined(engagement_id=engagement_id, user_id=ctx.user_id))
    await member_added(tx, engagement_id, ctx.user_id)  # SPEC-025: confirm independence


async def firm_admins(tenant_id: UUID) -> list[UUID]:
    """Recipients for firm-level notifications (SPEC-013)."""
    return await active_firm_admins(TenantContext(tenant_id, "system", "notifications"))


async def team_of(tenant_id: UUID, engagement_id: UUID) -> list[tuple[UUID, EngagementRole]]:
    """An engagement's members and roles, for notification recipients (SPEC-013)."""
    return await engagement_members_of(
        TenantContext(tenant_id, "system", "notifications"), engagement_id
    )


LEAD_ROLES: frozenset[EngagementRole] = frozenset({"engagement_partner", "manager"})


async def engagement_leads(tenant_id: UUID, engagement_id: UUID) -> list[UUID]:
    """The engagement's partner and managers (SPEC-013 recipients)."""
    return [user for user, role in await team_of(tenant_id, engagement_id) if role in LEAD_ROLES]


async def engagement_team(ctx: AuthContext, engagement_id: UUID) -> list[TeamMember]:
    members = await engagement_members_of(ctx.tenant, engagement_id)
    names = await display_names([user_id for user_id, _ in members])
    return [TeamMember(user_id, names.get(user_id, ""), role) for user_id, role in members]


async def could(ctx: AuthContext, user_id: UUID, action: str, resource: Resource) -> bool:
    """Whether another active member of the caller's firm may `action` on `resource` now, by the
    same `authorise` (roles, walls, attributes). For giving work to someone who can do it
    (TASK-019 security review M2): never a grant for the caller. Fresh-MFA actions answer False,
    since only the person themself can have signed in recently."""
    found = [m for m in await active_memberships(user_id) if m.tenant_id == ctx.tenant_id]
    if not found:
        return False
    other = AuthContext(
        tenant=TenantContext(ctx.tenant_id, "human", str(user_id)),
        user_id=user_id,
        membership_id=found[0].membership_id,
        firm_role=found[0].firm_role,
        mfa_at=None,
    )
    try:
        await authorise(other, action, resource)
    except Forbidden:
        return False
    return True


async def is_active_member(tenant_id: UUID, user_id: UUID) -> bool:
    """Whether this person has an active membership in this firm now."""
    return any(m.tenant_id == tenant_id for m in await active_memberships(user_id))


# --- Ethical walls (SPEC-002; ADR-026) -----------------------------------------------------------

_UNIQUE_VIOLATION = "23505"
_FOREIGN_KEY_VIOLATION = "23503"


class WallExists(DomainConflict):
    """The person is already walled off from this client."""

    code = "wall_exists"


class OwnWall(DomainConflict):
    """A firm admin can't lift a wall on themself: another firm admin must (ADR-026: walls are
    absolute; TASK-016 security review)."""

    code = "own_wall"


@dataclass(frozen=True)
class WallView:
    id: UUID
    user_id: UUID
    client_id: UUID
    status: str
    created_by: UUID
    created_at: datetime
    removed_by: UUID | None
    removed_at: datetime | None


def _wall_view(wall: WallRecord) -> WallView:
    return WallView(
        wall.id,
        wall.user_id,
        wall.client_id,
        wall.status,
        wall.created_by,
        wall.created_at,
        wall.removed_by,
        wall.removed_at,
    )


def _sqlstate(exc: IntegrityError) -> str | None:
    state = getattr(exc.orig, "sqlstate", None)
    return state if isinstance(state, str) else None


async def create_wall(ctx: AuthContext, *, user_id: UUID, client_id: UUID) -> WallView:
    """Wall `user_id` off from `client_id` (firm admin, fresh MFA). It applies from the person's
    next request, everywhere on that client (ADR-026)."""
    await authorise(ctx, "wall.create", Resource.firm(ctx.tenant_id))
    wall_id = uuid4()
    try:
        async with uow(ctx.tenant) as tx:
            await insert_wall(
                tx.session,
                wall_id=wall_id,
                tenant_id=ctx.tenant_id,
                user_id=user_id,
                client_id=client_id,
                created_by=ctx.user_id,
            )
            tx.record(
                "wall.created",
                target=Target("ethical_wall", wall_id),
                after=Ref(user_id=user_id, client_id=client_id),
            )
            wall = await get_wall(tx.session, wall_id)
    except IntegrityError as exc:
        state = _sqlstate(exc)
        if state == _UNIQUE_VIOLATION:
            raise WallExists from None
        if state == _FOREIGN_KEY_VIOLATION:
            raise NotFound("member or client") from None  # not in this firm
        raise
    if wall is None:  # just written in this tenant
        raise RuntimeError("ethical wall vanished after insert")
    return _wall_view(wall)


async def remove_wall_by_id(ctx: AuthContext, wall_id: UUID) -> WallView:
    """Lift an active wall (firm admin, fresh MFA); its record stays, marked removed."""
    await authorise(ctx, "wall.remove", Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        wall = await get_wall(tx.session, wall_id)
        if wall is not None and wall.status == "active" and wall.user_id == ctx.user_id:
            raise OwnWall
        removed = await remove_wall(tx.session, wall_id, ctx.user_id)
        if removed is None:
            raise NotFound("ethical wall")
        tx.record(
            "wall.removed",
            target=Target("ethical_wall", wall_id),
            before=Ref(user_id=removed.user_id, client_id=removed.client_id),
        )
    return _wall_view(removed)


async def list_walls(ctx: AuthContext) -> list[WallView]:
    """Every wall of the firm, active and removed (firm admin, fresh MFA): who is walled off
    from which client is itself sensitive."""
    await authorise(ctx, "wall.list", Resource.firm(ctx.tenant_id))
    return [_wall_view(wall) for wall in await all_walls(ctx.tenant)]


@dataclass(frozen=True)
class FirmMember:
    user_id: UUID
    display_name: str


async def firm_members(ctx: AuthContext) -> list[FirmMember]:
    """For picking whom to wall (SPEC-019 Q4): authorised as `wall.create`."""
    await authorise(ctx, "wall.create", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        ids = await active_staff_ids(session)
    names = await display_names(ids)
    members = [FirmMember(user_id, names.get(user_id, "")) for user_id in ids]
    return sorted(members, key=lambda m: (m.display_name.casefold(), str(m.user_id)))


async def engagement_role_of(
    tenant: TenantContext, engagement_id: UUID, user_id: UUID
) -> str | None:
    """A person's role on an engagement (staff or client), or None (SPEC-020: client assignees)."""
    return await engagement_role(tenant, user_id, engagement_id)


async def names_of(user_ids: list[UUID]) -> dict[UUID, str]:
    """Display names for people the caller already read under RLS (SPEC-020: upload history)."""
    return await display_names(user_ids)


async def member_context(tenant_id: UUID, user_id: UUID) -> AuthContext | None:
    """A person's context for background work the platform starts on their standing consent
    (SPEC-022 TASK-038 D3: retrievals for the client admin who connected). Read fresh: None when
    the person no longer holds an active membership in the firm. Never carries an MFA time, so
    no fresh-MFA action passes; every caller acts only on behalf of the person whose consent
    applies, and each new caller needs the founder's approval."""
    found = [m for m in await active_memberships(user_id) if m.tenant_id == tenant_id]
    if not found:
        return None
    membership = found[0]
    return AuthContext(
        tenant=TenantContext(tenant_id, "human", str(user_id)),
        user_id=user_id,
        membership_id=membership.membership_id,
        firm_role=membership.firm_role,
        mfa_at=None,
    )


async def walled_from(tenant: TenantContext, user_id: UUID) -> frozenset[UUID]:
    """The clients a person is walled off from now (SPEC-025: the picker leaves them out)."""
    return await walled_clients(tenant, user_id)


async def firm_name(tenant_id: UUID) -> str:
    """The firm's name, for what goes out in its name (SPEC-025 AC-8: invitations)."""
    return await firm_name_of(tenant_id) or "Your auditor"
