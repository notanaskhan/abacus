"""Identity routes. PROTECTED. TASK-007."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.firm_settings import (
    autonomy,
    read_agents_state,
    read_letter_policy,
    read_time_zone,
    set_autonomy,
    set_firm_agents_paused,
    set_firm_time_zone,
    set_letter_policy,
)
from abacus.modules.identity.invitations import accept_invitation
from abacus.modules.identity.repository import FirmRole
from abacus.modules.identity.routing import (
    IDENTITY,
    SELF,
    STAFF,
    AbacusRouter,
    current_context,
    current_identity,
    current_signed_in,
    current_staff,
)
from abacus.modules.identity.service import (
    SignedIn,
    WallView,
    create_wall,
    firm_members,
    list_walls,
    remove_wall_by_id,
)
from abacus.modules.identity.signup import sign_up
from abacus.modules.identity.staff import (
    accept_staff_invitation,
    change_role,
    invite,
    resend,
    staff,
)
from abacus.modules.identity.staff import revoke as revoke_staff
from abacus.modules.identity.staff import revoke_invitation as revoke_staff_invitation
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


class MembershipOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: Annotated[UUID, classified("internal")]
    firm_name: Annotated[str, classified("confidential")]
    firm_role: Annotated[FirmRole | None, classified("internal")]
    # SPEC-015: `client` members use the client route tree (ADR-011); `staff` the firm's.
    kind: Annotated[Literal["staff", "client"], classified("internal")] = "staff"


class MeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    email: Annotated[str, classified("confidential")]
    display_name: Annotated[str, classified("confidential")]
    memberships: Annotated[list[MembershipOut], classified("internal")]
    # Set when the user has exactly one membership; otherwise the client picks one and sends it
    # as X-Abacus-Tenant.
    active_tenant_id: Annotated[UUID | None, classified("internal")]


@router.get("/me", action=SELF, response_model=MeOut)
async def me(signed_in: Annotated[SignedIn, Depends(current_signed_in)]) -> MeOut:
    memberships = signed_in.memberships
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
            )
            for m in memberships
        ],
        active_tenant_id=memberships[0].tenant_id if len(memberships) == 1 else None,
    )


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

StaffRole = Literal["firm_admin", "practice_leader", "quality_partner"]


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


class StaffListOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    members: Annotated[list[StaffMemberOut], classified("confidential")]
    invitations: Annotated[list[StaffInvitationOut], classified("confidential")]


class StaffInviteIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    email: Annotated[str, Field(min_length=3, max_length=320), classified("confidential")]
    firm_role: Annotated[StaffRole | None, classified("internal")] = None


class FirmRoleIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    firm_role: Annotated[StaffRole | None, classified("internal")]


class StaffInvitedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]


class JoinedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: Annotated[UUID, classified("internal")]


@router.get("/firm/staff", action="firm.manage_users", response_model=StaffListOut)
async def staff_route(ctx: Ctx) -> StaffListOut:
    """SPEC-024: the firm's staff and pending invitations (firm administrators)."""
    found = await staff(ctx)
    return StaffListOut(
        members=[StaffMemberOut.model_validate(asdict(m)) for m in found.members],
        invitations=[StaffInvitationOut.model_validate(asdict(i)) for i in found.invitations],
    )


@router.post(
    "/firm/staff/invitations",
    action="firm.manage_users",
    response_model=StaffInvitedOut,
    status_code=201,
)
async def invite_staff_route(body: StaffInviteIn, ctx: Ctx) -> StaffInvitedOut:
    """SPEC-024 AC-3: a single-use, expiring link by email."""
    return StaffInvitedOut(id=await invite(ctx, body.email, body.firm_role))


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
    """SPEC-024 AC-4: applies on their next request; never the last administrator."""
    await change_role(ctx, user_id, body.firm_role)
    return StaffInvitedOut(id=user_id)


@router.post(
    "/firm/staff/{user_id}/revoke",
    action="firm.manage_users",
    response_model=StaffInvitedOut,
    errors=(409,),
)
async def revoke_staff_route(user_id: UUID, ctx: Ctx) -> StaffInvitedOut:
    """SPEC-024 AC-4: their next request is refused; never the last administrator."""
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
