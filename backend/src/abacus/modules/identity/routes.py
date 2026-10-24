"""Identity routes. PROTECTED. TASK-007."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from typing import Annotated, Literal, cast
from urllib.parse import urlencode
from uuid import UUID

from fastapi import Cookie, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._statuses import MembershipStatus
from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext
from abacus.kernel.listing import ListPage
from abacus.kernel.text import SingleLineText
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.firm_settings import (
    AiClientDataView,
    autonomy,
    clock_view,
    read_agents_state,
    read_ai_client_data,
    read_drafted_guidance_setting,
    read_letter_policy,
    read_time_zone,
    set_ai_client_data_setting,
    set_autonomy,
    set_drafted_guidance_setting,
    set_firm_agents_paused,
    set_firm_time_zone,
    set_letter_policy,
)
from abacus.modules.identity.invitations import accept_invitation
from abacus.modules.identity.me import FirmFacts, firm_facts, me_details, set_default_office
from abacus.modules.identity.mfa_floor import mfa_required
from abacus.modules.identity.people import (
    InviteTerms,
    StaffFilters,
    change_template,
    invite,
    staff_page,
)
from abacus.modules.identity.portal_contract import MeMfaOut, MePortalOut
from abacus.modules.identity.portal_session import factor_enrolled
from abacus.modules.identity.repository import FirmRole
from abacus.modules.identity.routing import (
    IDENTITY,
    OWN,
    PRE_SESSION,
    SELF,
    STAFF,
    AbacusRouter,
    current_context,
    current_identity,
    current_member,
    current_signed_in,
    current_staff,
    requested_tenant,
)
from abacus.modules.identity.service import (
    SignedIn,
    WallView,
    create_wall,
    firm_members,
    list_walls,
    remove_wall_by_id,
)
from abacus.modules.identity.settings_contract import (
    Band,
    Level,
    RoleTemplate,
    ServiceLine,
    StaffRowV2Out,
    StaffTalliesOut,
    row_out,
    tallies_out,
)
from abacus.modules.identity.signup import sign_up
from abacus.modules.identity.staff import (
    accept_staff_invitation,
    change_role,
    resend,
)
from abacus.modules.identity.staff import revoke as revoke_staff
from abacus.modules.identity.staff import revoke_invitation as revoke_staff_invitation
from abacus.modules.identity.staff_session import (
    ABSOLUTE_SECONDS,
    COOKIE_NAME,
    CSRF_HEADER,
    MAX_RETURN_TO,
    SPA_CALLBACK_PATH,
    RefreshReused,
    SessionExpired,
    SignInRefused,
    begin_sign_in,
    complete_sign_in,
    refresh_session,
    web_origin,
)
from abacus.modules.identity.staff_session import end_session as end_staff_session
from abacus.modules.identity.support import (
    Staff,
    SupportSessionView,
    acknowledge_session,
    approve_session,
    emergency_approve,
    end_session,
    firm_sessions,
    request_session,
    revoke_session,
)
from abacus.modules.identity.tokens import VerifiedIdentity

router = AbacusRouter(prefix="/v1", tags=["identity"])


class FirmFactsOut(BaseModel):
    """P-01-T04 (SHL-03): what the firm switcher shows for a membership."""

    model_config = ConfigDict(frozen=True)

    region: Annotated[str, classified("internal")]
    time_zone: Annotated[str, classified("internal")]
    seats_total: Annotated[int | None, classified("internal")]  # None for a sandbox
    is_sandbox: Annotated[bool, classified("internal")]
    sandbox_of: Annotated[UUID | None, classified("internal")]


class MembershipOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: Annotated[UUID, classified("internal")]
    firm_name: Annotated[str, classified("confidential")]
    firm_role: Annotated[FirmRole | None, classified("internal")]
    # SPEC-015: `client` members use the client route tree (ADR-011); `staff` the firm's.
    kind: Annotated[Literal["staff", "client"], classified("internal")] = "staff"
    firm: Annotated[FirmFactsOut | None, classified("internal")] = None  # P-01-T04


class OfficeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("internal")]


class MeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    email: Annotated[str, classified("confidential")]
    display_name: Annotated[str, classified("confidential")]
    memberships: Annotated[list[MembershipOut], classified("internal")]
    # Set when the user has exactly one membership; otherwise the client picks one and sends it
    # as X-Abacus-Tenant.
    active_tenant_id: Annotated[UUID | None, classified("internal")]
    # F-04-T07 (ADR-143): business time for the active tenant, so the SPA can apply its offset.
    server_now: Annotated[datetime, classified("internal")]
    clock_mode: Annotated[Literal["real", "offset", "frozen"], classified("internal")]
    # P-01-T04 (v3; SHL-03): the person in the active tenant. None without an active tenant.
    initials: Annotated[str | None, classified("internal")] = None
    job_title: Annotated[str | None, classified("confidential")] = None
    default_office_id: Annotated[UUID | None, classified("internal")] = None
    offices: Annotated[list[OfficeOut], classified("internal")] = []
    # C5 v1.1 portal half (P-08-T01, additive): the portal shell and the second step, for client
    # users. Null until P-08-T07 (`portal`) and P-08-T17 (`mfa`) fill them.
    portal: Annotated[MePortalOut | None, classified("internal")] = None
    mfa: Annotated[MeMfaOut | None, classified("internal")] = None


def _firm_out(facts: FirmFacts | None) -> FirmFactsOut | None:
    return FirmFactsOut.model_validate(facts, from_attributes=True) if facts else None


@router.get("/me", action=SELF, response_model=MeOut)
async def me(
    signed_in: Annotated[SignedIn, Depends(current_signed_in)],
    asked: Annotated[UUID | None, Depends(requested_tenant)] = None,
) -> MeOut:
    memberships = signed_in.memberships
    user = str(signed_in.user.id)
    held = {m.tenant_id for m in memberships}
    # The active tenant: the one asked for when the person holds it, or their only one.
    active = asked if asked in held else (memberships[0].tenant_id if len(held) == 1 else None)
    tenant = TenantContext(active, "human", user) if active is not None else None
    view = await clock_view(tenant)
    details = await me_details(tenant, signed_in.user.id) if tenant is not None else None
    # P-08-T17: a client person's second step in the active firm (never a factor or a code).
    mfa = None
    if active is not None and any(
        m.tenant_id == active and m.kind == "client" for m in memberships
    ):
        mfa = MeMfaOut(
            enrolled=await factor_enrolled(signed_in.user.id),
            required=await mfa_required(active, signed_in.user.id),
        )
    return MeOut(
        user_id=signed_in.user.id,
        email=signed_in.user.email,
        display_name=signed_in.user.display_name,
        memberships=[
            MembershipOut(
                tenant_id=m.tenant_id,
                firm_name=m.firm_name,
                firm_role=m.firm_role,
                kind="client" if m.kind == "client" else "staff",
                firm=_firm_out(await firm_facts(TenantContext(m.tenant_id, "human", user))),
            )
            for m in memberships
        ],
        active_tenant_id=active,
        server_now=view.server_now,
        clock_mode=view.clock_mode,
        initials=details.initials if details else None,
        job_title=details.job_title if details else None,
        default_office_id=details.default_office_id if details else None,
        offices=[OfficeOut(id=o.id, name=o.name) for o in details.offices] if details else [],
        mfa=mfa,
    )


class PreferencesIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    default_office_id: Annotated[UUID | None, classified("internal")]


class PreferencesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    default_office_id: Annotated[UUID | None, classified("internal")]


@router.put("/me/preferences", action=OWN, response_model=PreferencesOut)
async def set_preferences_route(
    body: PreferencesIn, ctx: Annotated[AuthContext, Depends(current_member)]
) -> PreferencesOut:
    """AC 2.1.3: the default office filter (an office of the active firm, or none); audited."""
    details = await set_default_office(ctx, body.default_office_id)
    return PreferencesOut(default_office_id=details.default_office_id)


# --- Ethical walls (SPEC-002): firm admins, fresh MFA; the matrix decides ---------------------

Ctx = Annotated[AuthContext, Depends(current_context)]


class WallIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]


class WallOut(BaseModel):
    """Who is walled off from which client is itself sensitive (conflicts of interest)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("confidential")]
    client_id: Annotated[UUID, classified("confidential")]
    status: Annotated[Literal["active", "removed"], classified("internal")]
    created_by: Annotated[UUID, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]
    removed_by: Annotated[UUID | None, classified("internal")]
    removed_at: Annotated[datetime | None, classified("internal")]


def _wall_out(wall: WallView) -> WallOut:
    return WallOut.model_validate(wall, from_attributes=True)


@router.post("/walls", action="wall.create", response_model=WallOut, status_code=201)
async def create_wall_route(body: WallIn, ctx: Ctx) -> WallOut:
    return _wall_out(await create_wall(ctx, user_id=body.user_id, client_id=body.client_id))


@router.post("/walls/{wall_id}/remove", action="wall.remove", response_model=WallOut, errors=[409])
async def remove_wall_route(wall_id: UUID, ctx: Ctx) -> WallOut:
    """Walls are never deleted: removing one returns it, marked removed."""
    return _wall_out(await remove_wall_by_id(ctx, wall_id))


@router.get("/walls", action="wall.list", response_model=list[WallOut])
async def list_walls_route(ctx: Ctx) -> list[WallOut]:
    return [_wall_out(wall) for wall in await list_walls(ctx)]


class FirmMemberOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]


@router.get("/firm/members", action="wall.create", response_model=list[FirmMemberOut])
async def firm_members_route(ctx: Ctx) -> list[FirmMemberOut]:
    """SPEC-019 Q4: the firm's staff, for the wall picker."""
    return [
        FirmMemberOut(user_id=m.user_id, display_name=m.display_name)
        for m in await firm_members(ctx)
    ]


# --- Break-glass support sessions (SPEC-012 §8) -------------------------------------------------

StaffDep = Annotated[Staff, Depends(current_staff)]
SupportCtx = Ctx


class SupportSessionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    staff_id: Annotated[UUID, classified("internal")]
    staff_subject: Annotated[str, classified("internal")]
    reason: Annotated[str, classified("confidential")]
    scope: Annotated[Literal["metadata", "content"], classified("internal")]
    duration_minutes: Annotated[int, classified("internal")]
    emergency: Annotated[bool, classified("internal")]
    status: Annotated[
        Literal["requested", "active", "ended", "revoked", "expired"], classified("internal")
    ]
    approved_by_kind: Annotated[str | None, classified("internal")]
    starts_at: Annotated[datetime | None, classified("internal")]
    expires_at: Annotated[datetime | None, classified("internal")]
    ended_at: Annotated[datetime | None, classified("internal")]
    acknowledged: Annotated[bool, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]
    requests: Annotated[int, classified("internal")]


class SupportSessionIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    firm_id: Annotated[UUID, classified("internal")]
    reason: Annotated[str, Field(min_length=20, max_length=1000), classified("confidential")]
    scope: Annotated[Literal["metadata", "content"], classified("internal")]
    duration_minutes: Annotated[int, Field(ge=1, le=240), classified("internal")]
    emergency: Annotated[bool, classified("internal")] = False


class FirmRefIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    firm_id: Annotated[UUID, classified("internal")]


def _session_out(view: SupportSessionView) -> SupportSessionOut:
    return SupportSessionOut.model_validate(asdict(view))


staff_router = AbacusRouter(prefix="/v1/support/sessions", tags=["support"])


@staff_router.post(
    "", action=STAFF, response_model=SupportSessionOut, status_code=201, errors=(409,)
)
async def request_support_session_route(
    body: SupportSessionIn, staff: StaffDep
) -> SupportSessionOut:
    view = await request_session(
        staff, body.firm_id, body.reason, body.scope, body.duration_minutes, body.emergency
    )
    return _session_out(view)


@staff_router.post(
    "/{session_id}/approve", action=STAFF, response_model=SupportSessionOut, errors=(409,)
)
async def emergency_approve_route(
    session_id: UUID, body: FirmRefIn, staff: StaffDep
) -> SupportSessionOut:
    return _session_out(await emergency_approve(staff, body.firm_id, session_id))


@staff_router.post(
    "/{session_id}/end", action=STAFF, response_model=SupportSessionOut, errors=(409,)
)
async def end_support_session_route(
    session_id: UUID, body: FirmRefIn, staff: StaffDep
) -> SupportSessionOut:
    return _session_out(await end_session(staff, body.firm_id, session_id))


firm_support_router = AbacusRouter(prefix="/v1/support-sessions", tags=["support"])


@firm_support_router.get("", action="support_session.read", response_model=list[SupportSessionOut])
async def list_support_sessions_route(ctx: SupportCtx) -> list[SupportSessionOut]:
    return [_session_out(v) for v in await firm_sessions(ctx)]


@firm_support_router.post(
    "/{session_id}/approve",
    action="support_session.manage",
    response_model=SupportSessionOut,
    errors=(409,),
)
async def approve_support_session_route(session_id: UUID, ctx: SupportCtx) -> SupportSessionOut:
    return _session_out(await approve_session(ctx, session_id))


@firm_support_router.post(
    "/{session_id}/revoke",
    action="support_session.manage",
    response_model=SupportSessionOut,
    errors=(409,),
)
async def revoke_support_session_route(session_id: UUID, ctx: SupportCtx) -> SupportSessionOut:
    return _session_out(await revoke_session(ctx, session_id))


@firm_support_router.post(
    "/{session_id}/acknowledge",
    action="support_session.manage",
    response_model=SupportSessionOut,
    errors=(409,),
)
async def acknowledge_support_session_route(
    session_id: UUID, ctx: SupportCtx
) -> SupportSessionOut:
    return _session_out(await acknowledge_session(ctx, session_id))


# --- Accepting a client invitation (SPEC-015 §8) -------------------------------------------------

invitation_router = AbacusRouter(prefix="/v1/invitations", tags=["invitations"])


class AcceptInvitationIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    token: Annotated[str, Field(min_length=20, max_length=200), classified("restricted")]


class AcceptedInvitationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]


@invitation_router.post("/accept", action=IDENTITY, response_model=AcceptedInvitationOut)
async def accept_invitation_route(
    body: AcceptInvitationIn, identity: Annotated[VerifiedIdentity, Depends(current_identity)]
) -> AcceptedInvitationOut:
    """A passwordlessly signed-in person accepts (TASK-030 D2): no account is needed yet."""
    accepted = await accept_invitation(identity, body.token)
    return AcceptedInvitationOut(
        tenant_id=accepted.tenant_id, engagement_id=accepted.engagement_id
    )


# --- Self-serve sign-up (SPEC-024 AC-1; TASK-040) ----------------------------------------------

signup_router = AbacusRouter(prefix="/v1/signup", tags=["signup"])


class SignupIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: Annotated[str, Field(min_length=8, max_length=200), classified("restricted")]
    firm_name: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]


class SignupOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: Annotated[UUID, classified("internal")]


@signup_router.post("", action=IDENTITY, response_model=SignupOut, status_code=201, errors=(409,))
async def signup_route(
    body: SignupIn,
    request: Request,
    identity: Annotated[VerifiedIdentity, Depends(current_identity)],
) -> SignupOut:
    """A signed-in person with a founder-issued code creates their firm (no membership yet)."""
    address = request.client.host if request.client is not None else "unknown"
    tenant_id = await sign_up(identity, code=body.code, firm_name=body.firm_name, address=address)
    return SignupOut(tenant_id=tenant_id)


# --- Staff: invitations, firm roles, revocation (SPEC-024 AC-3, AC-4; TASK-041) ---------------

# The catalogue's four firm roles, P-10's `security_admin` included (DEC-21; ED-009).
StaffRole = Literal["firm_admin", "practice_leader", "quality_partner", "security_admin"]


class StaffMemberOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]
    email: Annotated[str, classified("confidential")]
    firm_role: Annotated[StaffRole | None, classified("internal")]
    status: Annotated[Literal["active", "revoked"], classified("internal")]


class StaffInvitationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    email: Annotated[str, classified("confidential")]
    firm_role: Annotated[StaffRole | None, classified("internal")]
    expires_at: Annotated[datetime, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


class StaffListOut(ListPage[StaffRowV2Out]):
    """ADM-02a on the list envelope (G-01-T05): `items` in bands, `counts` per band over the
    filters, firm-wide `tallies`. `members` and `invitations` are SPEC-024's shape, kept for the
    legacy people screen until G-01-T17 retires it (unfiltered)."""

    model_config = ConfigDict(frozen=True)

    tallies: Annotated[StaffTalliesOut, classified("internal")]
    members: Annotated[list[StaffMemberOut], classified("confidential")]
    invitations: Annotated[list[StaffInvitationOut], classified("confidential")]


class StaffInviteIn(BaseModel):
    """SPEC-024's invitation, grown for ADM-02c (G-01-T05): the template and what the membership
    takes on acceptance. A seasonal invite needs `access_ends_on` (422 `access_ends_required`)."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    email: Annotated[str, Field(min_length=3, max_length=320), classified("confidential")]
    firm_role: Annotated[StaffRole | None, classified("internal")] = None
    role_template: Annotated[RoleTemplate | None, classified("internal")] = None
    level: Annotated[Level | None, classified("internal")] = None
    office_id: Annotated[UUID | None, classified("internal")] = None
    team_ids: Annotated[list[UUID], Field(max_length=20), classified("internal")] = []
    service_lines: Annotated[list[ServiceLine], Field(max_length=4), classified("internal")] = []
    access_ends_on: Annotated[date | None, classified("internal")] = None
    offshore: Annotated[bool, classified("internal")] = False
    display_name: Annotated[
        SingleLineText | None, Field(default=None, max_length=200), classified("confidential")
    ]
    title: Annotated[
        SingleLineText | None, Field(default=None, max_length=120), classified("confidential")
    ]


class FirmRoleIn(BaseModel):
    """SPEC-024's firm role; with `role_template` (G-01-T05, AC4.2) the template, its level and
    the firm role it carries change together (`firm_role` is then a partner's oversight role)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    firm_role: Annotated[StaffRole | None, classified("internal")] = None
    role_template: Annotated[RoleTemplate | None, classified("internal")] = None
    level: Annotated[Level | None, classified("internal")] = None


class StaffInvitedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]


class JoinedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: Annotated[UUID, classified("internal")]


@router.get("/firm/staff", action="firm.manage_users", response_model=StaffListOut)
async def staff_route(
    ctx: Ctx,
    q: Annotated[str | None, Query(max_length=100)] = None,
    role_template: RoleTemplate | None = None,
    office_id: UUID | None = None,
    team_id: UUID | None = None,
    status: Annotated[MembershipStatus | None, Query()] = None,
    band: Band | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> StaffListOut:
    """ADM-02a (G-01-T05; AC3.1, AC3.2): staff and pending invitations in bands, searched by name
    or email (the term travels in the query string, never a path). Still `firm.manage_users`
    with fresh MFA (SPEC-024 AC-3's tests hold it there); G-01 section 4.3's move to
    `firm.read_people` waits on DEC-286."""
    page = await staff_page(
        ctx,
        StaffFilters(
            q=q,
            role_template=role_template,
            office_id=office_id,
            team_id=team_id,
            status=None if status is None else status.value,
            band=band,
            cursor=cursor,
            limit=limit,
        ),
        legacy=True,
    )
    everyone = await staff_page(ctx, StaffFilters(limit=200), legacy=True)
    return StaffListOut(
        items=[row_out(r) for r in page.items],
        next_cursor=page.next_cursor,
        total=page.total,
        counts=page.counts,
        tallies=tallies_out(page.tallies),
        members=[
            StaffMemberOut(
                user_id=r.user_id,
                display_name=r.display_name,
                email=r.email,
                firm_role=cast(StaffRole | None, r.firm_role),
                status="active" if r.status == "active" else "revoked",
            )
            for r in everyone.items
            if r.user_id is not None
        ],
        invitations=[
            StaffInvitationOut(
                id=r.invitation_id,
                email=r.email,
                firm_role=cast(StaffRole | None, r.firm_role),
                expires_at=cast(datetime, r.invitation_expires_at),
                created_at=cast(datetime, r.invited_at),
            )
            for r in everyone.items
            if r.invitation_id is not None
        ],
    )


@router.post(
    "/firm/staff/invitations",
    action="firm.manage_users",
    response_model=StaffInvitedOut,
    status_code=201,
    errors=(409,),
)
async def invite_staff_route(body: StaffInviteIn, ctx: Ctx) -> StaffInvitedOut:
    """SPEC-024 AC-3 and ADM-02c: a single-use, 14-day link by email; 409 `seats_full`,
    `already_member`; 422 `access_ends_required`."""
    terms = InviteTerms(
        email=body.email,
        firm_role=body.firm_role,
        role_template=body.role_template,
        level=body.level,
        office_id=body.office_id,
        team_ids=list(body.team_ids),
        service_lines=list(body.service_lines),
        access_ends_on=body.access_ends_on,
        offshore=body.offshore,
        display_name=body.display_name,
        title=body.title,
    )
    return StaffInvitedOut(id=await invite(ctx, terms))


@router.post(
    "/firm/staff/invitations/{invitation_id}/resend",
    action="firm.manage_users",
    response_model=StaffInvitedOut,
)
async def resend_staff_invitation_route(invitation_id: UUID, ctx: Ctx) -> StaffInvitedOut:
    await resend(ctx, invitation_id)
    return StaffInvitedOut(id=invitation_id)


@router.post(
    "/firm/staff/invitations/{invitation_id}/revoke",
    action="firm.manage_users",
    response_model=StaffInvitedOut,
)
async def revoke_staff_invitation_route(invitation_id: UUID, ctx: Ctx) -> StaffInvitedOut:
    await revoke_staff_invitation(ctx, invitation_id)
    return StaffInvitedOut(id=invitation_id)


@router.put(
    "/firm/staff/{user_id}/role",
    action="firm.manage_users",
    response_model=StaffInvitedOut,
    errors=(409,),
)
async def change_firm_role_route(user_id: UUID, body: FirmRoleIn, ctx: Ctx) -> StaffInvitedOut:
    """SPEC-024 AC-4: applies on their next request; never the last administrator. With a
    template (AC4.2): fresh MFA, one unit of work, "Role changed by <person>"."""
    if body.role_template is None:
        await change_role(ctx, user_id, body.firm_role)
    else:
        await change_template(ctx, user_id, body.role_template, body.level, body.firm_role)
    return StaffInvitedOut(id=user_id)


@router.post(
    "/firm/staff/{user_id}/revoke",
    action="firm.manage_users",
    response_model=StaffInvitedOut,
    errors=(409,),
)
async def revoke_staff_route(user_id: UUID, ctx: Ctx) -> StaffInvitedOut:
    """SPEC-024 AC-4: their next request is refused; never the last administrator. Deactivate's
    alias for one release (G-01-T05)."""
    await revoke_staff(ctx, user_id)
    return StaffInvitedOut(id=user_id)


@invitation_router.post("/staff/accept", action=IDENTITY, response_model=JoinedOut, errors=(409,))
async def accept_staff_invitation_route(
    body: AcceptInvitationIn, identity: Annotated[VerifiedIdentity, Depends(current_identity)]
) -> JoinedOut:
    """The invited person joins the firm's staff (they need no account yet)."""
    return JoinedOut(tenant_id=await accept_staff_invitation(identity, body.token))


# --- Autonomy (SPEC-024 AC-5; TASK-042) --------------------------------------------------------


class AutonomyOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: Annotated[int, Field(ge=0, le=3), classified("internal")]
    set_at: Annotated[datetime | None, classified("internal")]


class AutonomyIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    level: Annotated[int, Field(ge=0, le=3), classified("internal")]


@router.get("/firm/autonomy", action="firm.read_settings", response_model=AutonomyOut)
async def autonomy_route(ctx: Ctx) -> AutonomyOut:
    view = await autonomy(ctx)
    return AutonomyOut(level=view.level, set_at=view.set_at)


@router.put(
    "/firm/autonomy", action="autonomy_policy.update", response_model=AutonomyOut, errors=(409,)
)
async def set_autonomy_route(body: AutonomyIn, ctx: Ctx) -> AutonomyOut:
    """ADR-061: Advise (0) or Routine (1) for now; Manage and Portfolio come later."""
    view = await set_autonomy(ctx, body.level)
    return AutonomyOut(level=view.level, set_at=view.set_at)


# --- The letter before client data (SPEC-025 Q4; TASK-044) -------------------------------------


class LetterPolicyOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    required: Annotated[bool, classified("internal")]


class DraftedGuidanceIO(BaseModel):
    """SPEC-035 (TASK-073): whether approved drafted guidance is shown to clients."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    shown: Annotated[bool, classified("internal")]


@router.get(
    "/firm/drafted-guidance", action="firm.read_settings", response_model=DraftedGuidanceIO
)
async def drafted_guidance_route(ctx: Ctx) -> DraftedGuidanceIO:
    return DraftedGuidanceIO(shown=await read_drafted_guidance_setting(ctx))


@router.put(
    "/firm/drafted-guidance",
    action="firm.manage_settings",
    response_model=DraftedGuidanceIO,
    errors=(409,),
)
async def set_drafted_guidance_route(body: DraftedGuidanceIO, ctx: Ctx) -> DraftedGuidanceIO:
    return DraftedGuidanceIO(shown=await set_drafted_guidance_setting(ctx, body.shown))


class AssistantOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    agent_id: Annotated[str, classified("internal")]
    purpose: Annotated[str, classified("internal")]
    stage: Annotated[Literal["shadow", "live", "off"], classified("internal")]


class RetentionExceptionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    purpose: Annotated[str, classified("internal")]
    max_days: Annotated[int, classified("internal")]


class DisclosureOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: Annotated[str, classified("internal")]
    region: Annotated[str, classified("internal")]
    retention_exceptions: Annotated[list[RetentionExceptionOut], classified("internal")]
    subprocessors: Annotated[list[str], classified("internal")]
    review_by: Annotated[date, classified("internal")]
    letter_wording: Annotated[str, classified("internal")]


class AiClientDataOut(BaseModel):
    """SPEC-036 (TASK-076): the firm's opt-in, the disclosure and each assistant's stage."""

    model_config = ConfigDict(frozen=True)

    available: Annotated[bool, classified("internal")]
    opted_in_at: Annotated[datetime | None, classified("internal")] = None
    opted_in_by: Annotated[UUID | None, classified("internal")] = None
    current: Annotated[bool, classified("internal")]
    lapsed: Annotated[bool, classified("internal")]
    disclosure: Annotated[DisclosureOut | None, classified("internal")] = None
    assistants: Annotated[list[AssistantOut], classified("internal")]


class AiClientDataIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    on: Annotated[bool, classified("internal")]


def _ai_out(view: AiClientDataView) -> AiClientDataOut:
    d = view.disclosure
    return AiClientDataOut(
        available=view.available,
        opted_in_at=view.opted_in_at,
        opted_in_by=view.opted_in_by,
        current=view.current,
        lapsed=view.lapsed,
        disclosure=DisclosureOut(
            provider=d.provider,
            region=d.region,
            retention_exceptions=[
                RetentionExceptionOut(purpose=p, max_days=n) for p, n in d.retention_exceptions
            ],
            subprocessors=list(d.subprocessors),
            review_by=d.review_by,
            letter_wording=d.letter_wording,
        )
        if d is not None
        else None,
        assistants=[
            AssistantOut(
                agent_id=a.agent_id,
                purpose=a.purpose,
                stage=cast(Literal["shadow", "live", "off"], a.stage),
            )
            for a in view.assistants
        ],
    )


@router.get("/firm/ai-client-data", action="firm.read_settings", response_model=AiClientDataOut)
async def ai_client_data_route(ctx: Ctx) -> AiClientDataOut:
    return _ai_out(await read_ai_client_data(ctx))


@router.put(
    "/firm/ai-client-data",
    action="firm.ai_client_data",
    response_model=AiClientDataOut,
    errors=(409,),
)
async def set_ai_client_data_route(body: AiClientDataIn, ctx: Ctx) -> AiClientDataOut:
    """SPEC-036 AC-3: opt in (against the disclosure) or out; firm administrator, fresh MFA."""
    return _ai_out(await set_ai_client_data_setting(ctx, body.on))


@router.get("/firm/letter-policy", action="firm.read_settings", response_model=LetterPolicyOut)
async def letter_policy_route(ctx: Ctx) -> LetterPolicyOut:
    return LetterPolicyOut(required=await read_letter_policy(ctx))


class TimeZoneIO(BaseModel):
    """SPEC-027 (TASK-051): the firm's time zone (IANA name), for the agent's daily tick."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    time_zone: Annotated[str, Field(min_length=1, max_length=64), classified("internal")]


@router.get("/firm/time-zone", action="firm.read_settings", response_model=TimeZoneIO)
async def time_zone_route(ctx: Ctx) -> TimeZoneIO:
    return TimeZoneIO(time_zone=await read_time_zone(ctx))


@router.put("/firm/time-zone", action="firm.manage_settings", response_model=TimeZoneIO)
async def set_time_zone_route(body: TimeZoneIO, ctx: Ctx) -> TimeZoneIO:
    return TimeZoneIO(time_zone=await set_firm_time_zone(ctx, body.time_zone))


class AgentsStateOut(BaseModel):
    """SPEC-027 (TASK-050): the firm-wide switch for every engagement agent."""

    model_config = ConfigDict(frozen=True)

    paused_at: Annotated[datetime | None, classified("internal")]


@router.get("/firm/agents", action="firm.read_settings", response_model=AgentsStateOut)
async def firm_agents_route(ctx: Ctx) -> AgentsStateOut:
    return AgentsStateOut(paused_at=(await read_agents_state(ctx)).paused_at)


@router.post("/firm/agents/pause", action="firm_agents.pause", response_model=AgentsStateOut)
async def pause_firm_agents_route(ctx: Ctx) -> AgentsStateOut:
    return AgentsStateOut(paused_at=(await set_firm_agents_paused(ctx, True)).paused_at)


@router.post("/firm/agents/resume", action="firm_agents.pause", response_model=AgentsStateOut)
async def resume_firm_agents_route(ctx: Ctx) -> AgentsStateOut:
    return AgentsStateOut(paused_at=(await set_firm_agents_paused(ctx, False)).paused_at)


@router.put("/firm/letter-policy", action="firm.manage_settings", response_model=LetterPolicyOut)
async def set_letter_policy_route(body: LetterPolicyOut, ctx: Ctx) -> LetterPolicyOut:
    return LetterPolicyOut(required=await set_letter_policy(ctx, body.required))


# --- Staff session BFF (P-01-T09; ADR-141, ADR-165; DEC-140) -----------------------------------

auth_router = AbacusRouter(prefix="/v1/auth", tags=["auth"])


class AuthRedirectOut(BaseModel):
    """What the sign-in routes answer: a redirect. The browser follows `Location`."""

    model_config = ConfigDict(frozen=True)

    location: Annotated[str, classified("internal")]


class SessionTokenOut(BaseModel):
    """AC 5.1.4: an access token for memory only, never web storage."""

    model_config = ConfigDict(frozen=True)

    access_token: Annotated[str, classified("restricted")]
    expires_in: Annotated[int, classified("internal")]


class SignedOutOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    ended: Annotated[bool, classified("internal")]


def _set_session_cookie(response: Response, value: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        value,
        max_age=ABSOLUTE_SECONDS,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="strict")


def _no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    return response


@auth_router.get(
    "/sign-in", action=PRE_SESSION, response_model=AuthRedirectOut, status_code=302, errors=(503,)
)
async def sign_in_route(
    return_to: Annotated[str | None, Query(max_length=MAX_RETURN_TO)] = None,
    reauthenticate: bool = False,
) -> Response:
    """AC 5.1.2: to the provider's authorize page with server-side state and PKCE (10 min)."""
    return _no_store(
        RedirectResponse(
            await begin_sign_in(return_to, reauthenticate=reauthenticate), status_code=302
        )
    )


@auth_router.get(
    "/callback", action=PRE_SESSION, response_model=AuthRedirectOut, status_code=302, errors=(503,)
)
async def callback_route(
    code: Annotated[str | None, Query(max_length=2048)] = None,
    state: Annotated[str | None, Query(max_length=256)] = None,
    previous: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> Response:
    """AC 5.1.2: start the session, set the cookie and land on SHL-06g with the safe path; a
    refusal lands there with its error code instead (the T15 error state)."""
    landing = web_origin() + SPA_CALLBACK_PATH
    try:
        started = await complete_sign_in(code, state, previous_cookie=previous)
    except SignInRefused as refused:
        response = RedirectResponse(
            f"{landing}?{urlencode({'error': refused.code})}", status_code=302
        )
        _clear_session_cookie(response)
        return _no_store(response)
    response = RedirectResponse(f"{landing}?{urlencode({'to': started.return_to})}", 302)
    _set_session_cookie(response, started.cookie)
    return _no_store(response)


def _refusal(detail: str, status: int = 401) -> JSONResponse:
    response = JSONResponse({"detail": detail}, status_code=status)
    _clear_session_cookie(response)
    return cast(JSONResponse, _no_store(response))


@auth_router.post("/refresh", action=PRE_SESSION, response_model=SessionTokenOut, errors=(503,))
async def refresh_route(
    cookie: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    csrf: Annotated[str | None, Header(alias=CSRF_HEADER)] = None,
    origin: Annotated[str | None, Header()] = None,
) -> Response:
    """AC 5.1.4: cookie-authenticated, with the CSRF header and the app's own Origin."""
    if csrf != "1" or origin is None or origin.rstrip("/") != web_origin():
        return _no_store(JSONResponse({"detail": "forbidden"}, status_code=403))
    try:
        refreshed = await refresh_session(cookie)
    except RefreshReused:
        return _refusal("session_refresh_reused")
    except SessionExpired:
        return _refusal("session_expired")
    body = SessionTokenOut(access_token=refreshed.access_token, expires_in=refreshed.expires_in)
    response = JSONResponse(body.model_dump())
    _set_session_cookie(response, refreshed.cookie)
    return _no_store(response)


@auth_router.post("/sign-out", action=OWN, response_model=SignedOutOut)
async def sign_out_route(
    ctx: Annotated[AuthContext, Depends(current_member)],
    cookie: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> Response:
    """AC 2.1.6: end the caller's own session and clear the cookie; the old value no longer
    refreshes."""
    ended = await end_staff_session(ctx.user_id, cookie)
    response = JSONResponse(SignedOutOut(ended=ended).model_dump())
    _clear_session_cookie(response)
    return _no_store(response)
