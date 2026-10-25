"""Sign-in and the request context (ADR-002, ADR-029). PROTECTED. TASK-007 design §4.

1. Verify the bearer token (401 if not valid).
2. Resolve the user by issuer and subject (403 if unknown).
3. Load the user's active memberships, fresh on every request.
4. Choose the active tenant: the only membership, or the one named in `X-Abacus-Tenant`, which
   counts only if it matches an active membership. A member's header naming a tenant they do not
   hold, real or not, is 404 (P-01 AC 2.1.4, DEC-304). No memberships at all (SPEC-000 AC-2), no
   header with several, or a header that is not a tenant id, is 403.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.identity.authz import Forbidden, Resource, authorise
from abacus.modules.identity.context import AuthContext, NoActiveTenant, TenantNotHeld
from abacus.modules.identity.events import EngagementMemberAdded, EngagementMemberSelfJoined
from abacus.modules.identity.member_hooks import member_added
from abacus.modules.identity.offshore import assert_assignable, offshore_consented
from abacus.modules.identity.repository import (
    EngagementRole,
    MembershipRecord,
    UserRecord,
    active_firm_admins,
    active_memberships,
    active_partner_members,
    active_security_admins,
    active_staff_ids,
    client_admin_ids,
    display_names,
    earliest_partner_of,
    emails_of,
    engagement_members_of,
    engagement_role,
    find_user,
    firm_name_of,
    insert_engagement_member,
    my_engagement_roles,
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
        if not chosen and memberships:  # her own memberships only: the firm is never read
            raise TenantNotHeld("tenant not held")
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
        client=membership.kind == "client",
    )


def portal_member_context(
    user_id: UUID, membership: MembershipRecord, session_id: UUID
) -> AuthContext:
    """P-08-T10 (ADR-168): a portal person's context from their validated, active client
    membership in the firm their session is pinned to. No second step yet (P-08-T17)."""
    return AuthContext(
        tenant=TenantContext(membership.tenant_id, "human", str(user_id)),
        user_id=user_id,
        membership_id=membership.membership_id,
        firm_role=None,
        mfa_at=None,
        client=True,
        portal_session_id=session_id,
    )


@dataclass(frozen=True)
class TeamMember:
    user_id: UUID
    display_name: str
    role: EngagementRole


async def add_creator_as_partner(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, client_id: UUID
) -> None:
    """The creator of an engagement becomes its engagement partner (AC-4; TASK-008 Q2), inside the
    creating unit of work, after `engagement.create` was authorised. The only way to add a member
    until `engagement.member_add` has its own route; who and which role are not the caller's to
    choose. An offshore creator needs the client's offshore-disclosure consent (409
    `offshore_consent_required`; DEC-52, TASK-1207 review), as anyone joining a team."""
    await assert_assignable(ctx.tenant, ctx.user_id, client_id)
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
    consented = await offshore_consented(tenant, client_id)
    async with tenant_session(tenant) as session:
        return frozenset(
            await team_candidate_ids(session, uuid4(), client_id, offshore_consented=consented)
        )


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
    person is re-checked: active staff, not walled from the client, not already on the team, and
    not offshore without the client's consent (409; TASK-1207 review)."""
    await assert_assignable(ctx.tenant, user_id, client_id)
    if user_id not in await team_candidate_ids(
        tx.session,
        engagement_id,
        client_id,
        offshore_consented=await offshore_consented(ctx.tenant, client_id),
    ):
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


async def add_self_joined_admin(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, client_id: UUID
) -> None:
    """ADR-024: a firm admin joins to see content, as `reviewer` (content reads, no decisions;
    TASK-028 D1), inside the caller's unit of work after `authorise(engagement.self_join)`. The
    `notify: engagement_team` obligation is met by the event emitted here (SPEC-013 AC-8). An
    offshore admin needs the client's consent (409; TASK-1207 review)."""
    await assert_assignable(ctx.tenant, ctx.user_id, client_id)
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


async def security_admins(tenant_id: UUID) -> list[UUID]:
    """Q-02-T33: recipients for the incident register's notifications (the firm's QI)."""
    return await active_security_admins(TenantContext(tenant_id, "system", "notifications"))


async def partner_members(tenant_id: UUID) -> list[UUID]:
    """Q-02-T33: the firm's partner-level staff, for `incident_recorded` (Q-02 §4.8)."""
    return await active_partner_members(TenantContext(tenant_id, "system", "notifications"))


async def team_of(tenant_id: UUID, engagement_id: UUID) -> list[tuple[UUID, EngagementRole]]:
    """An engagement's members and roles, for notification recipients (SPEC-013)."""
    return await engagement_members_of(
        TenantContext(tenant_id, "system", "notifications"), engagement_id
    )


LEAD_ROLES: frozenset[EngagementRole] = frozenset({"engagement_partner", "manager"})
PARTNER_ROLES: frozenset[EngagementRole] = frozenset({"engagement_partner"})


async def engagement_leads(tenant_id: UUID, engagement_id: UUID) -> list[UUID]:
    """The engagement's partner and managers (SPEC-013 recipients)."""
    return [user for user, role in await team_of(tenant_id, engagement_id) if role in LEAD_ROLES]


async def engagement_partners(tenant_id: UUID, engagement_id: UUID) -> list[UUID]:
    """SPEC-305 (TASK-306): the engagement partner(s), who alone decide reserved matters."""
    team = await team_of(tenant_id, engagement_id)
    return sorted({user for user, role in team if role in PARTNER_ROLES})


EQR_ROLES: frozenset[EngagementRole] = frozenset({"reviewer"})


async def engagement_eqrs(tenant_id: UUID, engagement_id: UUID) -> list[UUID]:
    """SPEC-314 (TASK-332): the engagement quality reviewer(s), who alone concur (G6)."""
    team = await team_of(tenant_id, engagement_id)
    return sorted({user for user, role in team if role in EQR_ROLES})


async def earliest_partner(tenant: TenantContext, engagement_id: UUID) -> UUID | None:
    """SPEC-027 (TASK-051): whom the engagement agent acts for (ADR-025)."""
    async with tenant_session(tenant) as session:
        return await earliest_partner_of(session, engagement_id)


async def client_admins(tenant: TenantContext, engagement_id: UUID) -> list[UUID]:
    async with tenant_session(tenant) as session:
        return await client_admin_ids(session, engagement_id)


async def contact_emails(user_ids: list[UUID]) -> dict[UUID, str]:
    """For communications' reminders, after the caller authorised `follow_up.send`."""
    return await emails_of(user_ids)


async def engagement_team(ctx: AuthContext, engagement_id: UUID) -> list[TeamMember]:
    members = await engagement_members_of(ctx.tenant, engagement_id)
    names = await display_names([user_id for user_id, _ in members])
    return [TeamMember(user_id, names.get(user_id, ""), role) for user_id, role in members]


async def could(ctx: AuthContext, user_id: UUID, action: str, resource: Resource) -> bool:
    """Whether another active member of the caller's firm may `action` on `resource` now, by the
    same `authorise` (roles, walls, attributes). For giving work to someone who can do it
    (TASK-019 security review M2): never a grant for the caller. Fresh-MFA actions answer False,
    since only the person themself can have signed in recently."""
    return await member_could(ctx.tenant_id, user_id, action, resource)


async def member_could(
    tenant_id: UUID,
    user_id: UUID,
    action: str,
    resource: Resource,
    *,
    waive_fresh_mfa: bool = False,
) -> bool:
    """`could` for a firm and a person, with no caller: an invitation's acceptance asks whether
    its inviter may still invite (P-08-T18, DEC-277). Fresh-MFA actions answer False, unless
    `waive_fresh_mfa`: the person can't step up because they aren't here (a contact invitation's
    acceptance re-checks `client_access.grant`, DEC-303), so only the recency of a second factor
    is set aside; walls, roles, independence, conditions and the archived rule all still hold."""
    found = [m for m in await active_memberships(user_id) if m.tenant_id == tenant_id]
    if not found:
        return False
    other = AuthContext(
        tenant=TenantContext(tenant_id, "human", str(user_id)),
        user_id=user_id,
        membership_id=found[0].membership_id,
        firm_role=found[0].firm_role,
        mfa_at=system_now() if waive_fresh_mfa else None,
        client=found[0].kind == "client",
    )
    try:
        await authorise(other, action, resource)
    except Forbidden:
        return False
    return True


async def is_active_member(tenant_id: UUID, user_id: UUID) -> bool:
    """Whether this person has an active membership in this firm now."""
    return any(m.tenant_id == tenant_id for m in await active_memberships(user_id))


# --- Ethical walls (SPEC-002; ADR-026): `walls.py` (G-01-T09) -------------------------------


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


async def my_engagements(ctx: AuthContext) -> dict[UUID, EngagementRole]:
    """TASK-102: the caller's own engagements and firm role on each, for "waiting on you"."""
    return await my_engagement_roles(ctx.tenant, ctx.user_id)


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


async def role_codes(ctx: AuthContext, engagement_id: UUID | None = None) -> tuple[str, ...]:
    """F-03-T30: the person's role codes here, for labels: the firm role and the engagement role
    on `engagement_id` (or every engagement role they hold in the firm)."""
    codes: set[str] = {ctx.firm_role} if ctx.firm_role else set()
    held = await my_engagement_roles(ctx.tenant, ctx.user_id)
    if engagement_id is not None:
        role = held.get(engagement_id)
        if role is not None:
            codes.add(role)
    else:
        codes |= set(held.values())
    return tuple(sorted(codes))
