"""The security-center contract, v1: ADM-06's identity half (G-02-T11 stub; SPEC-349 §5.4 to
§5.9, §8; ADR-139, P-36). Contract: `docs/contracts/security-center.md`.

Behind `security_center.v1`: off, every route here answers 404; on, G-02-T14 serves them all
(`identity/security_policies.py`: sign-in and portal policies, the SSO-exempt account, sessions,
unlock, the support switch, the overview and the posture). The incident read side and the
safeguards program are platform's (`platform/security_center_contract.py`, T18 and T20); the
export schedule is evidence's (`evidence/firm_export_schedule_contract.py`, T19): identity
imports no other module, so each stub lives where its implementation will (DEC-432).

Rules the shapes carry (DEC-22, DEC-34, DEC-35, DEC-72, INV-1, INV-4):

- **Stricter only.** A firm may shorten its session limits below the platform maxima, never
  lengthen them: a request over a maximum answers 422 `policy_loosening_refused` (the models
  bound nothing above, so the refusal is the service's code, not a validation error).
- **Locked floors have no field.** No input can turn MFA off (DEC-22), turn the portal's
  passwordless code or its MFA floor off (DEC-34, DF-17), or change the lockout (DEC-35): the
  inputs forbid extra fields, so a body that tries answers 422 before any handler runs.
- **Require SSO needs a verified admin SSO sign-in first** (409 `sso_not_verified`, AC-15).
- **One SSO-exempt account** in v1, holding a hardware-key factor (409
  `sso_exempt_needs_hardware_key`, AC-18).
- **Sessions are this firm's members' only**; signing one out ends it in this firm alone.
- **Authorisation comes first** (security review L1): a client principal gets 404 (INV-4); the
  agent, the system and anyone without the action (a stale second factor included) get 403,
  before the flag is read.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import SECURITY_CENTER_V1
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.identity import security_policies as service
from abacus.modules.identity.authz import Resource, authorise
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.routing import AbacusRouter, current_context
from abacus.modules.identity.security_policies import (
    PLATFORM_MAX_IDLE_MINUTES,
    PLATFORM_MAX_PORTAL_SESSION_MINUTES,
    PLATFORM_MAX_SESSION_MINUTES,
    PORTAL_FAILED_CODE_LIMIT,
    PORTAL_LOCKOUT_MINUTES,
    SECURITY_ACTIONS,
)

Ctx = Annotated[AuthContext, Depends(current_context)]

__all__ = [
    "PLATFORM_MAX_IDLE_MINUTES",
    "PLATFORM_MAX_PORTAL_SESSION_MINUTES",
    "PLATFORM_MAX_SESSION_MINUTES",
    "SECURITY_ACTIONS",
]

SessionAuthMethod = Literal["sso", "email_code", "passkey", "totp"]
ExemptFactor = Literal["hardware_key"]


class SecurityPersonOut(BaseModel):
    """A person named on the security center; the id links to the ADM-02 user drawer."""

    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]


class SsoExemptAccountOut(BaseModel):
    """The one break-glass account ("1 · hardware key · last tested Aug 3, 2026"). Who designated
    it, and when, is the audit log's (`sso_exempt_account.designated`)."""

    model_config = ConfigDict(frozen=True)

    person: Annotated[SecurityPersonOut, classified("internal")]
    factor: Annotated[ExemptFactor, classified("internal")]
    # Stamped when the account signs in (AC-18); null until it first does.
    last_tested_at: Annotated[datetime | None, classified("internal")] = None


class SignInPolicyOut(BaseModel):
    """ADM-06 fieldset A: the firm's staff sign-in (AC-15 to AC-18)."""

    model_config = ConfigDict(frozen=True)

    # The identity provider's name as the SSO connection reports it ("Microsoft Entra ID").
    identity_provider: Annotated[str | None, classified("internal")] = None
    # A verified SSO sign-in by an admin of this firm exists: Require SSO may be turned on.
    sso_verified: Annotated[bool, classified("internal")]
    require_sso: Annotated[bool, classified("internal")]
    sso_enforced_at: Annotated[datetime | None, classified("internal")] = None
    sso_enforced_by: Annotated[SecurityPersonOut | None, classified("internal")] = None
    # "IdP enforces MFA" (R-29): only after it is recorded do SSO users count by the IdP's claim.
    idp_mfa_attested_at: Annotated[datetime | None, classified("internal")] = None
    idp_mfa_attested_by: Annotated[SecurityPersonOut | None, classified("internal")] = None
    session_absolute_minutes: Annotated[int, Field(ge=1), classified("internal")]
    session_idle_minutes: Annotated[int, Field(ge=1), classified("internal")]
    platform_max_absolute_minutes: Annotated[int, classified("internal")] = (
        PLATFORM_MAX_SESSION_MINUTES
    )
    platform_max_idle_minutes: Annotated[int, classified("internal")] = PLATFORM_MAX_IDLE_MINUTES
    sso_exempt_account: Annotated[SsoExemptAccountOut | None, classified("internal")] = None
    version: Annotated[int, Field(ge=0), classified("internal")]


class MfaSummaryOut(BaseModel):
    """ "Enforced · 46 of 46 enrolled" (AC-16). `enforced` and `locked` are always true: no
    route turns MFA off (DEC-22)."""

    model_config = ConfigDict(frozen=True)

    enforced: Annotated[bool, classified("internal")]
    locked: Annotated[bool, classified("internal")]
    enrolled: Annotated[int, Field(ge=0), classified("internal")]
    seats: Annotated[int, Field(ge=0), classified("internal")]
    # True once "IdP enforces MFA" is recorded and SSO users count by the IdP's claim.
    idp_claim_counted: Annotated[bool, classified("internal")] = False


class PortalSignInFloorOut(BaseModel):
    """ADM-06 fieldset B (AC-19): the passwordless code and the MFA floor are on and locked
    (DEC-34, DF-17), the lockout is "3 codes · 15 minutes" and locked (DEC-35); only the session
    length may change, and only shorter than 8 hours."""

    model_config = ConfigDict(frozen=True)

    passwordless_email_code: Annotated[bool, classified("internal")]
    passwordless_locked: Annotated[bool, classified("internal")]
    # Owners, signers, approvers and anyone who can see tax return information (P-08's floor).
    mfa_floor: Annotated[bool, classified("internal")]
    mfa_floor_locked: Annotated[bool, classified("internal")]
    failed_code_limit: Annotated[int, Field(ge=1), classified("internal")]
    lockout_minutes: Annotated[int, Field(ge=1), classified("internal")]
    lockout_locked: Annotated[bool, classified("internal")]
    session_minutes: Annotated[int, Field(ge=1), classified("internal")]
    platform_max_session_minutes: Annotated[int, classified("internal")] = (
        PLATFORM_MAX_PORTAL_SESSION_MINUTES
    )
    version: Annotated[int, Field(ge=0), classified("internal")]


class ResidencyOut(BaseModel):
    """ADM-06 fieldset E (AC-26): from `firms.region` and settings, every row locked."""

    model_config = ConfigDict(frozen=True)

    region: Annotated[str, classified("internal")]
    storage_primary_region: Annotated[str | None, classified("internal")] = None
    storage_backup_region: Annotated[str | None, classified("internal")] = None
    ai_inference: Annotated[Literal["us_only"], classified("internal")]
    logs_region: Annotated[str, classified("internal")]
    encryption_at_rest: Annotated[Literal["aes_256"], classified("internal")]
    encryption_in_transit: Annotated[Literal["tls_1_3"], classified("internal")]
    locked: Annotated[bool, classified("internal")]


class SupportAccessOut(BaseModel):
    """The support card's switch, "Allow support session requests" (AC-28). The sessions
    themselves are SPEC-012's `GET /v1/support-sessions`."""

    model_config = ConfigDict(frozen=True)

    allow_support_requests: Annotated[bool, classified("internal")]
    updated_at: Annotated[datetime | None, classified("internal")] = None
    updated_by: Annotated[SecurityPersonOut | None, classified("internal")] = None
    version: Annotated[int, Field(ge=0), classified("internal")]


class SecurityOverviewOut(BaseModel):
    """ADM-06 a: identity's fieldsets and cards. Incidents, safeguards, the export card and
    retention have their own reads from the modules that own them (DEC-432)."""

    model_config = ConfigDict(frozen=True)

    sign_in: Annotated[SignInPolicyOut, classified("internal")]
    mfa: Annotated[MfaSummaryOut, classified("internal")]
    portal: Annotated[PortalSignInFloorOut, classified("internal")]
    residency: Annotated[ResidencyOut, classified("internal")]
    support: Annotated[SupportAccessOut, classified("internal")]
    # The viewer's allowed actions among `SECURITY_ACTIONS`: without `security.manage` the screen
    # is read-only with the T12 banner and locks (AC-29).
    actions: Annotated[list[str], classified("internal")] = Field(default_factory=list[str])


class PostureOut(BaseModel):
    """The Posture card's five facts (AC-30); the same read feeds ADM-01's At a glance and the
    M9 checklist. Counts agree with the fieldsets by construction."""

    model_config = ConfigDict(frozen=True)

    sso_enforced: Annotated[bool, classified("internal")]
    mfa_enrolled: Annotated[int, Field(ge=0), classified("internal")]
    mfa_seats: Annotated[int, Field(ge=0), classified("internal")]
    residency_region: Annotated[str, classified("internal")]
    open_incidents: Annotated[int, Field(ge=0), classified("internal")]
    pub4557_open: Annotated[int, Field(ge=0), classified("internal")]


class SignInPolicyIn(BaseModel):
    """Fieldset A's Save. Shorter limits only: over a platform maximum answers 422
    `policy_loosening_refused` (`facts.field`). There is no MFA field (DEC-22)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    require_sso: Annotated[bool, classified("internal")]
    session_absolute_minutes: Annotated[int, Field(ge=1), classified("internal")]
    session_idle_minutes: Annotated[int, Field(ge=1), classified("internal")]
    idp_mfa_attested: Annotated[bool, classified("internal")] = False
    version: Annotated[int, Field(ge=0), classified("internal")]


class PortalSignInFloorIn(BaseModel):
    """Fieldset B's one editable row: the portal session, at most 8 hours (422
    `policy_loosening_refused` over it). The floors have no field (DEC-34, DEC-35)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    session_minutes: Annotated[int, Field(ge=1), classified("internal")]
    version: Annotated[int, Field(ge=0), classified("internal")]


class SsoExemptAccountIn(BaseModel):
    """Designate the one SSO-exempt account, or clear it with `user_id: null`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: Annotated[UUID | None, classified("internal")]
    version: Annotated[int, Field(ge=0), classified("internal")]


class SupportAccessIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allow_support_requests: Annotated[bool, classified("internal")]
    version: Annotated[int, Field(ge=0), classified("internal")]


class SecuritySessionOut(BaseModel):
    """One active session of a current member (AC-20): person, device, IP, started, last seen,
    MFA time. The IP and device are personal data."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    person: Annotated[SecurityPersonOut, classified("internal")]
    started_at: Annotated[datetime, classified("internal")]
    last_seen_at: Annotated[datetime, classified("internal")]
    mfa_at: Annotated[datetime | None, classified("internal")] = None
    auth_method: Annotated[SessionAuthMethod | None, classified("internal")] = None
    ip: Annotated[str | None, classified("confidential")] = None
    device_label: Annotated[str | None, classified("confidential")] = None
    # The viewer's own session: it signs out through the shell, not here.
    current: Annotated[bool, classified("internal")] = False


class SecuritySessionPageOut(ListPage[SecuritySessionOut]):
    """The P-36 envelope over the sessions drawer, newest last-seen first."""


class SessionSignedOutOut(BaseModel):
    """ "Sign out of Brightwater Hale": the session can no longer act in this firm; its other
    firms are unaffected."""

    model_config = ConfigDict(frozen=True)

    session_id: Annotated[UUID, classified("internal")]
    signed_out_at: Annotated[datetime, classified("internal")]
    signed_out_by: Annotated[SecurityPersonOut, classified("internal")]


class StaffLockOut(BaseModel):
    """A staff sign-in lock after Unlock: `cleared` when the identity provider let it be
    cleared; otherwise still `locked` with `unlocks_at` ("Unlocks automatically at 9:39 AM",
    DEC-35; SPEC-349 Q7)."""

    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    locked: Annotated[bool, classified("internal")]
    unlocks_at: Annotated[datetime | None, classified("internal")] = None
    cleared: Annotated[bool, classified("internal")]


security_router = AbacusRouter(prefix="/v1/firm/security", tags=["security center"])
staff_unlock_router = AbacusRouter(prefix="/v1/firm/staff", tags=["security center"])
support_access_router = AbacusRouter(prefix="/v1/firm/support-access", tags=["security center"])


async def _authorised(ctx: AuthContext, action: str) -> None:
    """L1: the matrix first. A client principal gets 404 (INV-4); everyone else is authorised at
    the firm, so the agent, the system, a person without the action and a stale second factor
    are refused (403) whatever the flag."""
    if ctx.client:
        raise NotFound("security_center")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))


async def _gate(ctx: AuthContext, action: str) -> None:
    """The matrix, then the flag: off, the family answers 404."""
    await _authorised(ctx, action)
    if not await flag_enabled(ctx.tenant, SECURITY_CENTER_V1):
        raise NotFound("security_center.v1")


def _person(p: service.UserRef) -> SecurityPersonOut:
    return SecurityPersonOut(user_id=p.user_id, display_name=p.display_name)


def _maybe(p: service.UserRef | None) -> SecurityPersonOut | None:
    return _person(p) if p is not None else None


def _sign_in_out(p: service.SignInPolicy) -> SignInPolicyOut:
    exempt = p.sso_exempt_account
    return SignInPolicyOut(
        identity_provider=p.identity_provider,
        sso_verified=p.sso_verified,
        require_sso=p.require_sso,
        sso_enforced_at=p.sso_enforced_at,
        sso_enforced_by=_maybe(p.sso_enforced_by),
        idp_mfa_attested_at=p.idp_mfa_attested_at,
        idp_mfa_attested_by=_maybe(p.idp_mfa_attested_by),
        session_absolute_minutes=p.session_absolute_minutes,
        session_idle_minutes=p.session_idle_minutes,
        sso_exempt_account=(
            SsoExemptAccountOut(
                person=_person(exempt.person),
                factor="hardware_key",
                last_tested_at=exempt.last_tested_at,
            )
            if exempt is not None
            else None
        ),
        version=p.version,
    )


def _portal_out(p: service.PortalFloor) -> PortalSignInFloorOut:
    return PortalSignInFloorOut(
        passwordless_email_code=True,
        passwordless_locked=True,
        mfa_floor=True,
        mfa_floor_locked=True,
        failed_code_limit=PORTAL_FAILED_CODE_LIMIT,
        lockout_minutes=PORTAL_LOCKOUT_MINUTES,
        lockout_locked=True,
        session_minutes=p.session_minutes,
        version=p.version,
    )


def _support_out(s: service.SupportAccess) -> SupportAccessOut:
    return SupportAccessOut(
        allow_support_requests=s.allow_support_requests,
        updated_at=s.updated_at,
        updated_by=_maybe(s.updated_by),
        version=s.version,
    )


@security_router.get("", action="security.read", response_model=SecurityOverviewOut)
async def security_overview_route(ctx: Ctx) -> SecurityOverviewOut:
    """ADM-06 a, e, f: sign-in, MFA summary, portal floor, residency and the support switch, with
    the viewer's actions (read-only without `security.manage`, AC-29)."""
    await _gate(ctx, "security.read")
    found = await service.overview(ctx)
    return SecurityOverviewOut(
        sign_in=_sign_in_out(found.sign_in),
        mfa=MfaSummaryOut(
            enforced=True,
            locked=True,
            enrolled=found.mfa.enrolled,
            seats=found.mfa.seats,
            idp_claim_counted=found.mfa.idp_claim_counted,
        ),
        portal=_portal_out(found.portal),
        residency=ResidencyOut(
            region=found.residency.region,
            storage_primary_region=found.residency.storage_primary_region,
            storage_backup_region=found.residency.storage_backup_region,
            ai_inference="us_only",
            logs_region=found.residency.logs_region,
            encryption_at_rest="aes_256",
            encryption_in_transit="tls_1_3",
            locked=True,
        ),
        support=_support_out(found.support),
        actions=list(found.actions),
    )


@security_router.put(
    "/sign-in", action="security.manage", response_model=SignInPolicyOut, errors=(409,)
)
async def put_sign_in_policy_route(body: SignInPolicyIn, ctx: Ctx) -> SignInPolicyOut:
    """Fieldset A (AC-15, AC-17): 409 `sso_not_verified` when Require SSO is turned on before an
    admin's verified SSO sign-in; 422 `policy_loosening_refused` over a platform maximum and
    `session_limit_out_of_range` under the floor; 409 `stale_version`. Audited
    `security_policy.updated` (and `security_policy.sso_enforced`,
    `security_policy.idp_mfa_attested`)."""
    await _gate(ctx, "security.manage")
    return _sign_in_out(
        await service.put_sign_in(
            ctx,
            require_sso=body.require_sso,
            session_absolute_minutes=body.session_absolute_minutes,
            session_idle_minutes=body.session_idle_minutes,
            idp_mfa_attested=body.idp_mfa_attested,
            version=body.version,
        )
    )


@security_router.put(
    "/portal-sign-in",
    action="security.manage",
    response_model=PortalSignInFloorOut,
    errors=(409,),
)
async def put_portal_sign_in_policy_route(
    body: PortalSignInFloorIn, ctx: Ctx
) -> PortalSignInFloorOut:
    """Fieldset B (AC-19): the portal session, shorter only (422 `policy_loosening_refused`); 409
    `stale_version`. Audited `portal_security_policy.updated`."""
    await _gate(ctx, "security.manage")
    return _portal_out(
        await service.put_portal(ctx, session_minutes=body.session_minutes, version=body.version)
    )


@security_router.put(
    "/sso-exempt-account",
    action="security.manage",
    response_model=SignInPolicyOut,
    errors=(409,),
)
async def put_sso_exempt_account_route(body: SsoExemptAccountIn, ctx: Ctx) -> SignInPolicyOut:
    """AC-18: designate (replacing any other) or clear the one SSO-exempt account; 409
    `sso_exempt_needs_hardware_key` without a hardware-key factor, 409 `sso_exempt_not_self` for
    the caller, 409 `stale_version`; 404 for someone who is not a current member. Audited
    `sso_exempt_account.designated` or `.cleared`."""
    await _gate(ctx, "security.manage")
    return _sign_in_out(await service.put_exempt(ctx, user_id=body.user_id, version=body.version))


@security_router.get("/sessions", action="security.read", response_model=SecuritySessionPageOut)
async def list_security_sessions_route(
    ctx: Ctx,
    cursor: Annotated[str | None, Query(max_length=1024)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SecuritySessionPageOut:
    """AC-20: active sessions of current members only; a former member's or another firm's
    person's session is never listed."""
    await _gate(ctx, "security.read")
    page = await service.sessions(ctx, cursor=cursor, limit=limit)
    return SecuritySessionPageOut(
        items=[
            SecuritySessionOut(
                id=s.id,
                person=_person(s.person),
                started_at=s.started_at,
                last_seen_at=s.last_seen_at,
                mfa_at=s.mfa_at,
                auth_method=s.auth_method,
                ip=s.ip,
                device_label=s.device_label,
                current=s.current,
            )
            for s in page.items
        ],
        next_cursor=page.next_cursor,
        total=page.total,
    )


@security_router.post(
    "/sessions/{session_id}/sign-out", action="session.end", response_model=SessionSignedOutOut
)
async def sign_out_session_route(session_id: UUID, ctx: Ctx) -> SessionSignedOutOut:
    """AC-20: the session can no longer act in this firm (`access.changed` closes its streams and
    caches); its other firms are unaffected. 404 for a session that is not a current member's.
    Audited `session.signed_out`."""
    await _gate(ctx, "session.end")
    done = await service.sign_out(ctx, session_id)
    return SessionSignedOutOut(
        session_id=done.session_id,
        signed_out_at=done.signed_out_at,
        signed_out_by=_person(done.signed_out_by),
    )


@security_router.get("/posture", action="security.read", response_model=PostureOut)
async def security_posture_route(ctx: Ctx) -> PostureOut:
    """AC-30: SSO enforced, MFA enrolled of seats, residency, open incidents and open Pub 4557
    items, as the fieldsets show them."""
    await _gate(ctx, "security.read")
    p = await service.posture(ctx)
    return PostureOut(
        sso_enforced=p.sso_enforced,
        mfa_enrolled=p.mfa_enrolled,
        mfa_seats=p.mfa_seats,
        residency_region=p.residency_region,
        open_incidents=p.open_incidents,
        pub4557_open=p.pub4557_open,
    )


@staff_unlock_router.post("/{user_id}/unlock", action="staff.unlock", response_model=StaffLockOut)
async def unlock_staff_route(user_id: UUID, ctx: Ctx) -> StaffLockOut:
    """AC-20: clear a staff sign-in lock where the identity provider allows it; otherwise the
    lock stands and `unlocks_at` says when it ends. 404 for someone not a current member.
    Audited `staff.unlocked` when cleared."""
    await _gate(ctx, "staff.unlock")
    lock = await service.unlock(ctx, user_id)
    return StaffLockOut(
        user_id=lock.user_id, locked=lock.locked, unlocks_at=lock.unlocks_at, cleared=lock.cleared
    )


@support_access_router.get("", action="support_session.read", response_model=SupportAccessOut)
async def support_access_route(ctx: Ctx) -> SupportAccessOut:
    """The support card's switch."""
    await _gate(ctx, "support_session.read")
    return _support_out(await service.support_access(ctx))


@support_access_router.put(
    "", action="support_session.manage", response_model=SupportAccessOut, errors=(409,)
)
async def put_support_access_route(body: SupportAccessIn, ctx: Ctx) -> SupportAccessOut:
    """AC-28: off, a new support-session request answers 409 `support_requests_disabled`;
    sessions already granted keep their expiry. 409 `stale_version`. Audited
    `support_access.updated`."""
    await _gate(ctx, "support_session.manage")
    return _support_out(
        await service.put_support_access(
            ctx, allow=body.allow_support_requests, version=body.version
        )
    )
