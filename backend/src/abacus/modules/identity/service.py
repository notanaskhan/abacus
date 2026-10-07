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

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity.authz import Resource, authorise
from abacus.modules.identity.context import AuthContext, NoActiveTenant
from abacus.modules.identity.repository import (
    EngagementRole,
    MembershipRecord,
    UserRecord,
    WallRecord,
    active_memberships,
    all_walls,
    display_names,
    engagement_members_of,
    find_user,
    get_wall,
    insert_engagement_member,
    insert_wall,
    remove_wall,
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


async def engagement_team(ctx: AuthContext, engagement_id: UUID) -> list[TeamMember]:
    members = await engagement_members_of(ctx.tenant, engagement_id)
    names = await display_names([user_id for user_id, _ in members])
    return [TeamMember(user_id, names.get(user_id, ""), role) for user_id, role in members]


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
        if wall is not None and wall.user_id == ctx.user_id:
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
