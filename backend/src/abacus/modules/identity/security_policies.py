"""The firm's security policies and their enforcement (G-02-T14; SPEC-349 AC-15 to AC-20, AC-26,
AC-28 to AC-30; DEC-22, DEC-34, DEC-35, DEC-72; DEC-524 to DEC-528). PROTECTED (red).

What ADM-06's identity half reads and changes, over `security_policies` (one row per firm, the
defaults without one), P-08's `portal_security_policies` and the staff sessions behind the BFF:

- **Sign-in** (fieldset A): Require SSO, only once an admin of the firm has a verified SSO sign-in
  (409 `sso_not_verified`); session limits shorter than the platform's only (422
  `policy_loosening_refused` over a maximum, 422 `session_limit_out_of_range` under the floor);
  the "IdP enforces MFA" attestation. MFA itself has no switch (DEC-22).
- **SSO-exempt account** (AC-18): one current member holding a hardware key (a passkey sign-in on
  record, DEC-525; 409 `sso_exempt_needs_hardware_key`), never the person designating it (409
  `sso_exempt_not_self`).
- **Portal floor** (fieldset B): the portal session length, shorter than 8 hours only; the floors
  are locked and have no field.
- **Sessions** (AC-20): the live sessions of current staff; "Sign out of" this firm records a
  per-firm revocation (`auth_session_tenant_revocations`) and ends nothing elsewhere.
- **Unlock** (AC-20): through `StaffLockPort`, which no adapter in the repository implements
  (DEC-526): the lock stands and ends by itself (DEC-35's timed unlock).
- **Support switch** (AC-28): read in front of every SPEC-012 request (`support_requests_allowed`).
- **Posture** (AC-30): identity's facts plus the open incidents and Pub 4557 items other modules
  register (`register_posture_source`).

And what the BFF enforces from them (`staff_session`): the strictest session limits and the SSO
requirement of the person's firms at sign-in and every refresh (DEC-524), the exempt account's
"last tested" stamp, and per-request refusal of a session signed out of the chosen firm.

Every change is a live person's (the matrix, `_human`, and the tables' triggers), against its
version (409 `stale_version`), and audited with identifier-only references.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Final, Literal, Protocol, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio import activity

from abacus.kernel import request_context
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, platform_transaction, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.listing import Position, clamp_limit, decode_cursor, encode_cursor
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, last_request_context, uow
from abacus.modules.identity.authz import Forbidden, Resource, allowed_actions, authorise
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import AccessChanged
from abacus.modules.identity.governance_errors import (
    SecurityPolicyLoosened,
    SsoExemptNeedsHardwareKey,
    SsoNotVerified,
    SupportRequestsDisabled,
)
from abacus.modules.identity.repository import (
    active_memberships,
    close_support_session,
    display_names,
    list_support_sessions,
)

# The platform maxima the stricter-only check uses (G-02 §4.9; AC-17, AC-19), and the floors
# that keep a firm from making its own sign-in unusable (the tables' CHECKs hold both).
PLATFORM_MAX_SESSION_MINUTES: Final = 720
PLATFORM_MAX_IDLE_MINUTES: Final = 30
PLATFORM_MAX_PORTAL_SESSION_MINUTES: Final = 480
MIN_SESSION_MINUTES: Final = 60
MIN_IDLE_MINUTES: Final = 5
MIN_PORTAL_SESSION_MINUTES: Final = 15
# The portal floor (DEC-34, DEC-35): fixed, shown locked.
PORTAL_FAILED_CODE_LIMIT: Final = 3
PORTAL_LOCKOUT_MINUTES: Final = 15
# The actions of the family, for the overview's `actions` (the viewer's, AC-29).
SECURITY_ACTIONS: Final = (
    "security.read",
    "security.manage",
    "session.end",
    "staff.unlock",
    "support_session.read",
    "support_session.manage",
    "incident.read",
    "incident.manage",
    "incident.decide",
    "firm_export.read",
    "firm_export.request",
    "firm_export.approve",
    "firm_export.schedule",
)
AuthMethod = Literal["sso", "email_code", "passkey", "totp"]
AUTH_METHODS: Final[frozenset[str]] = frozenset({"sso", "email_code", "passkey", "totp"})
_ADMIN_ROLES: Final = frozenset({"firm_admin", "security_admin"})
_SESSIONS_RESOURCE: Final = "security_sessions"
_log = get_logger(__name__)


# The policy changed since it was read: read it again. No docstring: the error catalogue keeps
# the shared `stale_version` summary.
class StalePolicy(DomainConflict):
    code = "stale_version"


class _Unchanged(Exception):
    """Nothing to change: the unit of work rolls back unwritten (it would refuse to commit
    without an audit event, and there is nothing to audit)."""


class SessionLimitOutOfRange(DomainInvalid):
    """A session limit under the floor (60 minutes absolute, 5 idle, 15 for the portal), which
    would leave the firm's people unable to work; `facts.field` names the field."""

    code = "session_limit_out_of_range"


class SsoExemptNotSelf(DomainConflict):
    """Nobody designates themselves the SSO-exempt (break-glass) account (AC-18, DEC-525)."""

    code = "sso_exempt_not_self"


# --- read models ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class UserRef:
    user_id: UUID
    display_name: str


@dataclass(frozen=True)
class ExemptAccount:
    person: UserRef
    last_tested_at: datetime | None


@dataclass(frozen=True)
class SignInPolicy:
    identity_provider: str | None
    sso_verified: bool
    require_sso: bool
    sso_enforced_at: datetime | None
    sso_enforced_by: UserRef | None
    idp_mfa_attested_at: datetime | None
    idp_mfa_attested_by: UserRef | None
    session_absolute_minutes: int
    session_idle_minutes: int
    sso_exempt_account: ExemptAccount | None
    version: int


@dataclass(frozen=True)
class MfaSummary:
    enrolled: int
    seats: int
    idp_claim_counted: bool


@dataclass(frozen=True)
class PortalFloor:
    session_minutes: int
    version: int


@dataclass(frozen=True)
class Residency:
    region: str
    storage_primary_region: str
    storage_backup_region: str
    logs_region: str


@dataclass(frozen=True)
class SupportAccess:
    allow_support_requests: bool
    updated_at: datetime | None
    updated_by: UserRef | None
    version: int


@dataclass(frozen=True)
class Overview:
    sign_in: SignInPolicy
    mfa: MfaSummary
    portal: PortalFloor
    residency: Residency
    support: SupportAccess
    actions: tuple[str, ...]


@dataclass(frozen=True)
class Posture:
    sso_enforced: bool
    mfa_enrolled: int
    mfa_seats: int
    residency_region: str
    open_incidents: int
    pub4557_open: int


@dataclass(frozen=True)
class SecuritySession:
    id: UUID
    person: UserRef
    started_at: datetime
    last_seen_at: datetime
    mfa_at: datetime | None
    auth_method: AuthMethod | None
    ip: str | None
    device_label: str | None
    current: bool


@dataclass(frozen=True)
class SessionPage:
    items: tuple[SecuritySession, ...]
    next_cursor: str | None
    total: int


@dataclass(frozen=True)
class SignedOut:
    session_id: UUID
    signed_out_at: datetime
    signed_out_by: UserRef


@dataclass(frozen=True)
class StaffLock:
    user_id: UUID
    locked: bool
    unlocks_at: datetime | None
    cleared: bool


# --- the unlock port (DEC-526) -------------------------------------------------------------------


class StaffLockPort(Protocol):
    """The identity provider's staff sign-in lock: when it ends (None: not locked, or the
    provider can't say) and whether it can be cleared now."""

    async def locked_until(self, user_id: UUID) -> datetime | None: ...

    async def clear(self, user_id: UUID) -> bool: ...


class NoStaffLocks:
    """No adapter in the repository reads or clears a staff lock (the WorkOS staff adapter is
    Q-01-T17's): nothing is reported locked and nothing is cleared, so a lock at the provider
    ends by itself (DEC-35)."""

    async def locked_until(self, user_id: UUID) -> datetime | None:
        return None

    async def clear(self, user_id: UUID) -> bool:
        return False


_locks: list[StaffLockPort] = [NoStaffLocks()]


def configure_staff_locks(port: StaffLockPort | None) -> None:
    """Local runs and tests only: a provider fake (None resets to `NoStaffLocks`)."""
    if settings().environment not in ("local", "test"):
        raise RuntimeError("configure_staff_locks is for local runs and tests only")
    _locks[0] = port if port is not None else NoStaffLocks()


# --- posture sources (AC-30) ---------------------------------------------------------------------

PostureFact = Literal["open_incidents", "pub4557_open"]
PostureSource = Callable[[TenantContext], Awaitable[int]]
_POSTURE: dict[str, PostureSource] = {}


def register_posture_source(fact: PostureFact, source: PostureSource) -> None:
    """The module that owns a posture fact counts it (platform: incidents; T20: Pub 4557). An
    unregistered fact counts 0: nothing of it is recorded."""
    known = _POSTURE.get(fact)
    if known is not None and (known.__module__, known.__qualname__) != (
        source.__module__,
        source.__qualname__,
    ):
        raise ValueError(f"posture fact {fact!r} is already registered")
    _POSTURE[fact] = source


# --- reads ---------------------------------------------------------------------------------------

_POLICY = text(
    "SELECT require_sso, sso_enforced_at, sso_enforced_by, idp_mfa_attested_at, "
    "idp_mfa_attested_by, session_absolute_minutes, session_idle_minutes, sso_exempt_user_id, "
    "sso_exempt_tested_at, allow_support_requests, support_updated_at, support_updated_by, "
    "version, support_version, sso_connection_org, identity_provider FROM security_policies"
)
_POLICY_FOR_UPDATE = text(
    "SELECT require_sso, sso_enforced_at, sso_enforced_by, idp_mfa_attested_at, "
    "idp_mfa_attested_by, session_absolute_minutes, session_idle_minutes, sso_exempt_user_id, "
    "sso_exempt_tested_at, allow_support_requests, support_updated_at, support_updated_by, "
    "version, support_version, sso_connection_org, identity_provider "
    "FROM security_policies FOR UPDATE"
)
_PORTAL = text("SELECT portal_session_minutes, version FROM portal_security_policies")
_PORTAL_FOR_UPDATE = text(
    "SELECT portal_session_minutes, version FROM portal_security_policies FOR UPDATE"
)
_METHODS = text("SELECT user_id, mfa, sso, passkey FROM security_sign_in_methods()")
_SEATS = text(
    "SELECT user_id, firm_role FROM memberships WHERE kind = 'staff' AND status = 'active'"
)


@dataclass(frozen=True)
class _Stored:
    require_sso: bool = False
    sso_enforced_at: datetime | None = None
    sso_enforced_by: UUID | None = None
    idp_mfa_attested_at: datetime | None = None
    idp_mfa_attested_by: UUID | None = None
    session_absolute_minutes: int = PLATFORM_MAX_SESSION_MINUTES
    session_idle_minutes: int = PLATFORM_MAX_IDLE_MINUTES
    sso_exempt_user_id: UUID | None = None
    sso_exempt_tested_at: datetime | None = None
    allow_support_requests: bool = True
    support_updated_at: datetime | None = None
    support_updated_by: UUID | None = None
    version: int = 0  # 0: no row yet (the defaults)
    support_version: int = 0
    # The firm's SSO connection (provisioning sets it; the app never writes it).
    sso_connection_org: str | None = None
    identity_provider: str | None = None


def _stored(row: RowMapping | None) -> _Stored:
    if row is None:
        return _Stored()
    return _Stored(**{k: row[k] for k in _Stored.__dataclass_fields__})


async def _policy_row(session: AsyncSession, *, lock: bool = False) -> _Stored:
    return _stored(
        (await session.execute(_POLICY_FOR_UPDATE if lock else _POLICY)).mappings().first()
    )


async def _people(ids: Sequence[UUID | None]) -> dict[UUID, UserRef]:
    wanted = sorted({i for i in ids if i is not None}, key=str)
    names = await display_names(wanted)
    return {u: UserRef(u, names[u]) for u in wanted if u in names}


@dataclass(frozen=True)
class _Methods:
    mfa: bool = False
    sso: bool = False
    passkey: bool = False


async def _methods(session: AsyncSession) -> dict[UUID, _Methods]:
    rows = (await session.execute(_METHODS)).mappings().all()
    return {
        cast(UUID, r["user_id"]): _Methods(bool(r["mfa"]), bool(r["sso"]), bool(r["passkey"]))
        for r in rows
    }


async def _seats(session: AsyncSession) -> dict[UUID, str | None]:
    rows = (await session.execute(_SEATS)).mappings().all()
    return {cast(UUID, r["user_id"]): cast(str | None, r["firm_role"]) for r in rows}


def _sso_verified(seats: dict[UUID, str | None], methods: dict[UUID, _Methods]) -> bool:
    """An admin of this firm (firm or security admin) has signed in through SSO (AC-15)."""
    return any(
        role in _ADMIN_ROLES and methods.get(user, _Methods()).sso for user, role in seats.items()
    )


def _sign_in(stored: _Stored, people: dict[UUID, UserRef], *, sso_verified: bool) -> SignInPolicy:
    exempt = None
    if stored.sso_exempt_user_id is not None and stored.sso_exempt_user_id in people:
        exempt = ExemptAccount(people[stored.sso_exempt_user_id], stored.sso_exempt_tested_at)
    return SignInPolicy(
        identity_provider=stored.identity_provider,
        sso_verified=sso_verified,
        require_sso=stored.require_sso,
        sso_enforced_at=stored.sso_enforced_at if stored.require_sso else None,
        sso_enforced_by=people.get(stored.sso_enforced_by) if stored.sso_enforced_by else None,
        idp_mfa_attested_at=stored.idp_mfa_attested_at,
        idp_mfa_attested_by=(
            people.get(stored.idp_mfa_attested_by) if stored.idp_mfa_attested_by else None
        ),
        session_absolute_minutes=stored.session_absolute_minutes,
        session_idle_minutes=stored.session_idle_minutes,
        sso_exempt_account=exempt,
        version=stored.version,
    )


async def _read_sign_in(session: AsyncSession, stored: _Stored) -> SignInPolicy:
    seats, methods = await _seats(session), await _methods(session)
    people = await _people(
        [stored.sso_enforced_by, stored.idp_mfa_attested_by, stored.sso_exempt_user_id]
    )
    return _sign_in(stored, people, sso_verified=_sso_verified(seats, methods))


def _mfa(
    seats: dict[UUID, str | None], methods: dict[UUID, _Methods], stored: _Stored
) -> MfaSummary:
    """Enrolled: active staff who have signed in with a second factor (a session is refused
    without one, DEC-22); until the WorkOS staff adapter reads factors, the sign-ins are the
    record (DEC-527)."""
    enrolled = sum(1 for user in seats if methods.get(user, _Methods()).mfa)
    return MfaSummary(enrolled, len(seats), stored.idp_mfa_attested_at is not None)


def _residency(region: str) -> Residency:
    s = settings()
    return Residency(region, s.kms_region, s.kms_replica_region, region)


async def _region(session: AsyncSession) -> str:
    found = await session.scalar(text("SELECT region FROM firms"))
    return str(found) if found is not None else "us"


async def _support(stored: _Stored) -> SupportAccess:
    people = await _people([stored.support_updated_by])
    return SupportAccess(
        stored.allow_support_requests,
        stored.support_updated_at,
        people.get(stored.support_updated_by) if stored.support_updated_by else None,
        stored.support_version,
    )


async def _authorised(ctx: AuthContext, action: str) -> None:
    """L1: a client principal gets 404 (INV-4); everyone else is authorised at the firm."""
    if ctx.client:
        raise NotFound("security_center")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))


def _human(ctx: AuthContext, action: str) -> None:
    """INV-1 behind the matrix: only a signed-in person of the firm changes these."""
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


async def overview(ctx: AuthContext) -> Overview:
    """ADM-06 a, e, f (AC-16, AC-19, AC-26, AC-29)."""
    await _authorised(ctx, "security.read")
    async with tenant_session(ctx.tenant) as session:
        stored = await _policy_row(session)
        seats, methods = await _seats(session), await _methods(session)
        portal = (await session.execute(_PORTAL)).mappings().first()
        region = await _region(session)
    people = await _people(
        [stored.sso_enforced_by, stored.idp_mfa_attested_by, stored.sso_exempt_user_id]
    )
    actions = await allowed_actions(ctx, Resource.firm(ctx.tenant_id), SECURITY_ACTIONS)
    return Overview(
        sign_in=_sign_in(stored, people, sso_verified=_sso_verified(seats, methods)),
        mfa=_mfa(seats, methods, stored),
        portal=PortalFloor(
            min(int(portal["portal_session_minutes"]), PLATFORM_MAX_PORTAL_SESSION_MINUTES)
            if portal is not None
            else PLATFORM_MAX_PORTAL_SESSION_MINUTES,
            int(portal["version"]) if portal is not None else 0,
        ),
        residency=_residency(region),
        support=await _support(stored),
        actions=tuple(a for a in SECURITY_ACTIONS if a in actions),
    )


async def posture(ctx: AuthContext) -> Posture:
    """AC-30: the same facts the fieldsets show."""
    await _authorised(ctx, "security.read")
    async with tenant_session(ctx.tenant) as session:
        stored = await _policy_row(session)
        mfa = _mfa(await _seats(session), await _methods(session), stored)
        region = await _region(session)
    counts: dict[str, int] = {}
    for fact in ("open_incidents", "pub4557_open"):
        source = _POSTURE.get(fact)
        counts[fact] = max(0, int(await source(ctx.tenant))) if source is not None else 0
    return Posture(
        stored.require_sso,
        mfa.enrolled,
        mfa.seats,
        region,
        counts["open_incidents"],
        counts["pub4557_open"],
    )


@dataclass(frozen=True)
class OperatorPosture:
    """The firm's identity facts the operator's go-live check reads (Q-04-T009): no person's
    names, no session, counts and switches only."""

    sso_enforced: bool
    sso_exempt_designated: bool
    mfa_enrolled: int
    mfa_seats: int
    firm_admins: int
    security_admins: int
    support_requests_allowed: bool
    residency_region: str


async def operator_posture(tenant: TenantContext) -> OperatorPosture:
    """For an operator tool in the firm's tenant context as the platform (`make go-live-check`,
    Q-04-T009): the same MFA and SSO facts `posture` shows a security admin, without a person's
    authorisation (an ops task has none). Read-only; callers are `abacus_tools` operator CLIs."""
    async with tenant_session(tenant) as session:
        stored = await _policy_row(session)
        seats = await _seats(session)
        mfa = _mfa(seats, await _methods(session), stored)
        region = await _region(session)
    roles = list(seats.values())
    return OperatorPosture(
        sso_enforced=stored.require_sso,
        sso_exempt_designated=stored.sso_exempt_user_id is not None,
        mfa_enrolled=mfa.enrolled,
        mfa_seats=mfa.seats,
        firm_admins=roles.count("firm_admin"),
        security_admins=roles.count("security_admin"),
        support_requests_allowed=stored.allow_support_requests,
        residency_region=region,
    )


# --- fieldset A: sign-in -------------------------------------------------------------------------


def _limits(absolute: int, idle: int) -> None:
    if absolute > PLATFORM_MAX_SESSION_MINUTES:
        raise SecurityPolicyLoosened(facts={"field": "session_absolute_minutes"})
    if idle > PLATFORM_MAX_IDLE_MINUTES:
        raise SecurityPolicyLoosened(facts={"field": "session_idle_minutes"})
    if absolute < MIN_SESSION_MINUTES:
        raise SessionLimitOutOfRange(facts={"field": "session_absolute_minutes"})
    if idle < MIN_IDLE_MINUTES:
        raise SessionLimitOutOfRange(facts={"field": "session_idle_minutes"})


_INSERT = text(
    "INSERT INTO security_policies (tenant_id, require_sso, sso_enforced_at, sso_enforced_by, "
    "idp_mfa_attested_at, idp_mfa_attested_by, session_absolute_minutes, session_idle_minutes, "
    "sso_exempt_user_id, allow_support_requests, support_updated_at, support_updated_by, "
    "support_version, updated_by) VALUES (:tenant, :require_sso, :sso_enforced_at, "
    ":sso_enforced_by, :idp_mfa_attested_at, :idp_mfa_attested_by, :absolute, :idle, :exempt, "
    ":allow, :support_at, :support_by, :support_version, :by)"
)
_UPDATE = text(
    "UPDATE security_policies SET require_sso = :require_sso, sso_enforced_at = :sso_enforced_at, "
    "sso_enforced_by = :sso_enforced_by, idp_mfa_attested_at = :idp_mfa_attested_at, "
    "idp_mfa_attested_by = :idp_mfa_attested_by, session_absolute_minutes = :absolute, "
    "session_idle_minutes = :idle, sso_exempt_user_id = :exempt, "
    "allow_support_requests = :allow, support_updated_at = :support_at, "
    "support_updated_by = :support_by, support_version = :support_version, "
    "version = :version, updated_by = :by, updated_at = clock_timestamp()"
)


async def _write(session: AsyncSession, ctx: AuthContext, before: _Stored, after: _Stored) -> None:
    values = {
        "tenant": ctx.tenant_id,
        "require_sso": after.require_sso,
        "sso_enforced_at": after.sso_enforced_at,
        "sso_enforced_by": after.sso_enforced_by,
        "idp_mfa_attested_at": after.idp_mfa_attested_at,
        "idp_mfa_attested_by": after.idp_mfa_attested_by,
        "absolute": after.session_absolute_minutes,
        "idle": after.session_idle_minutes,
        "exempt": after.sso_exempt_user_id,
        "allow": after.allow_support_requests,
        "support_at": after.support_updated_at,
        "support_by": after.support_updated_by,
        "support_version": after.support_version,
        "version": after.version,
        "by": ctx.user_id,
    }
    await session.execute(_INSERT if before.version == 0 else _UPDATE, values)


def _minutes_ref(policy: _Stored) -> Ref:
    return Ref(
        require_sso=int(policy.require_sso),
        session_absolute_minutes=policy.session_absolute_minutes,
        session_idle_minutes=policy.session_idle_minutes,
        idp_mfa_attested=int(policy.idp_mfa_attested_at is not None),
        version=policy.version,
    )


async def _now(session: AsyncSession) -> datetime:
    return cast(datetime, await session.scalar(text("SELECT clock_timestamp()")))


async def put_sign_in(
    ctx: AuthContext,
    *,
    require_sso: bool,
    session_absolute_minutes: int,
    session_idle_minutes: int,
    idp_mfa_attested: bool,
    version: int,
) -> SignInPolicy:
    """AC-15, AC-17: Require SSO, the session limits and the IdP-MFA attestation."""
    await _authorised(ctx, "security.manage")
    _human(ctx, "security.manage")
    _limits(session_absolute_minutes, session_idle_minutes)
    async with uow(ctx.tenant) as tx:
        before = await _policy_row(tx.session, lock=True)
        if before.version != version:
            raise StalePolicy(facts={"version": before.version})
        enforcing = require_sso and not before.require_sso
        if enforcing and not _sso_verified(await _seats(tx.session), await _methods(tx.session)):
            # M1: SSO counts only through this firm's own connection; a firm without one has
            # no verified sign-in to enforce (DEC-535).
            if before.sso_connection_org is None:
                raise SsoNotVerified(facts={"reason": "connection_missing"})
            raise SsoNotVerified
        now = await _now(tx.session)
        attesting = idp_mfa_attested and before.idp_mfa_attested_at is None
        after = replace(
            before,
            require_sso=require_sso,
            sso_enforced_at=now
            if enforcing
            else (before.sso_enforced_at if require_sso else None),
            sso_enforced_by=ctx.user_id
            if enforcing
            else (before.sso_enforced_by if require_sso else None),
            idp_mfa_attested_at=now
            if attesting
            else (before.idp_mfa_attested_at if idp_mfa_attested else None),
            idp_mfa_attested_by=ctx.user_id
            if attesting
            else (before.idp_mfa_attested_by if idp_mfa_attested else None),
            session_absolute_minutes=session_absolute_minutes,
            session_idle_minutes=session_idle_minutes,
            version=before.version + 1,
        )
        await _write(tx.session, ctx, before, after)
        target = Target("security_policy", ctx.tenant_id)
        tx.record(
            "security_policy.updated",
            target=target,
            before=_minutes_ref(before) if before.version else None,
            after=_minutes_ref(after),
        )
        if enforcing:
            tx.record(
                "security_policy.sso_enforced", target=target, after=Ref(version=after.version)
            )
        if attesting:
            tx.record(
                "security_policy.idp_mfa_attested", target=target, after=Ref(version=after.version)
            )
        policy = await _read_sign_in(tx.session, after)
    return policy


async def put_exempt(ctx: AuthContext, *, user_id: UUID | None, version: int) -> SignInPolicy:
    """AC-18: designate (replacing any other) or clear the one SSO-exempt account."""
    await _authorised(ctx, "security.manage")
    _human(ctx, "security.manage")
    if user_id is not None and user_id == ctx.user_id:
        raise SsoExemptNotSelf
    try:
        return await _designate(ctx, user_id, version)
    except _Unchanged:
        async with tenant_session(ctx.tenant) as session:
            return await _read_sign_in(session, await _policy_row(session))


async def _designate(ctx: AuthContext, user_id: UUID | None, version: int) -> SignInPolicy:
    async with uow(ctx.tenant) as tx:
        before = await _policy_row(tx.session, lock=True)
        if before.version != version:
            raise StalePolicy(facts={"version": before.version})
        if user_id is not None:
            if user_id not in await _seats(tx.session):
                raise NotFound("member")
            if not (await _methods(tx.session)).get(user_id, _Methods()).passkey:
                raise SsoExemptNeedsHardwareKey
        if user_id == before.sso_exempt_user_id:
            raise _Unchanged  # nothing changes: nothing to write or log
        after = replace(before, sso_exempt_user_id=user_id, version=before.version + 1)
        await _write(tx.session, ctx, before, after)
        target = Target("security_policy", ctx.tenant_id)
        if user_id is None:
            tx.record(
                "sso_exempt_account.cleared",
                target=target,
                before=Ref(user_id=cast(UUID, before.sso_exempt_user_id), version=before.version),
                after=Ref(version=after.version),
            )
        else:
            tx.record(
                "sso_exempt_account.designated",
                target=target,
                before=(
                    Ref(user_id=before.sso_exempt_user_id, version=before.version)
                    if before.sso_exempt_user_id is not None
                    else None
                ),
                after=Ref(user_id=user_id, version=after.version),
            )
        policy = await _read_sign_in(tx.session, after)
    return policy


# --- fieldset B: the portal session --------------------------------------------------------------


async def put_portal(ctx: AuthContext, *, session_minutes: int, version: int) -> PortalFloor:
    """AC-19: the portal session, shorter than 8 hours only."""
    await _authorised(ctx, "security.manage")
    _human(ctx, "security.manage")
    if session_minutes > PLATFORM_MAX_PORTAL_SESSION_MINUTES:
        raise SecurityPolicyLoosened(facts={"field": "session_minutes"})
    if session_minutes < MIN_PORTAL_SESSION_MINUTES:
        raise SessionLimitOutOfRange(facts={"field": "session_minutes"})
    async with uow(ctx.tenant) as tx:
        row = (await tx.session.execute(_PORTAL_FOR_UPDATE)).mappings().first()
        current = int(row["version"]) if row is not None else 0
        before_minutes = (
            int(row["portal_session_minutes"])
            if row is not None
            else PLATFORM_MAX_PORTAL_SESSION_MINUTES
        )
        if current != version:
            raise StalePolicy(facts={"version": current})
        if row is None:
            await tx.session.execute(
                text(
                    "INSERT INTO portal_security_policies (tenant_id, portal_session_minutes, "
                    "updated_by) VALUES (:tenant, :minutes, :by)"
                ),
                {"tenant": ctx.tenant_id, "minutes": session_minutes, "by": ctx.user_id},
            )
            after_version = 1
        else:
            await tx.session.execute(
                text(
                    "UPDATE portal_security_policies SET portal_session_minutes = :minutes, "
                    "version = version + 1, updated_by = :by, updated_at = clock_timestamp()"
                ),
                {"minutes": session_minutes, "by": ctx.user_id},
            )
            after_version = current + 1
        tx.record(
            "portal_security_policy.updated",
            target=Target("portal_security_policy", ctx.tenant_id),
            before=Ref(session_minutes=before_minutes, version=current)
            if row is not None
            else None,
            after=Ref(session_minutes=session_minutes, version=after_version),
        )
    return PortalFloor(session_minutes, after_version)


async def portal_session_seconds(tenant_id: UUID) -> int:
    """The firm's portal session length for a new portal session (AC-19); the 8-hour maximum
    when it set none. An unreadable policy fails closed to the shortest length a firm may set
    (security review L5)."""
    try:
        async with tenant_session(TenantContext(tenant_id, "system", "portal:session")) as s:
            found = await s.scalar(
                text("SELECT portal_session_minutes FROM portal_security_policies")
            )
    except Exception as exc:
        _log.warning("portal_session.policy_failed", error=type(exc).__name__)
        return MIN_PORTAL_SESSION_MINUTES * 60
    minutes = int(found) if found is not None else PLATFORM_MAX_PORTAL_SESSION_MINUTES
    return min(minutes, PLATFORM_MAX_PORTAL_SESSION_MINUTES) * 60


# --- sessions ------------------------------------------------------------------------------------


_SESSIONS = text(
    "SELECT id, user_id, created_at, last_seen_at, mfa_at, auth_method FROM security_sessions()"
)


def _current_session_cookie() -> str | None:
    found = request_context.current()
    return found.session_cookie_sha256 if found is not None else None


async def _viewer_session(ctx: AuthContext) -> UUID | None:
    cookie = _current_session_cookie()
    if cookie is None:
        return None
    async with platform_transaction(f"user:{ctx.user_id}") as conn:
        row = (
            await conn.execute(
                text("SELECT session_id FROM audit_request_session(:cookie, :user)"),
                {"cookie": cookie, "user": ctx.user_id},
            )
        ).first()
    return cast(UUID, row[0]) if row is not None else None


async def sessions(ctx: AuthContext, *, cursor: str | None, limit: int | None) -> SessionPage:
    """AC-20: the live sessions of current members, newest last-seen first."""
    await _authorised(ctx, "security.read")
    size = clamp_limit(limit)
    async with tenant_session(ctx.tenant) as session:
        rows = list((await session.execute(_SESSIONS)).mappings().all())
        # The IP and device a session last acted from in this firm, from this firm's own
        # audit trail (DEC-528): never another firm's; `auth_sessions` keeps neither.
        seen = await last_request_context(session, [cast(UUID, r["id"]) for r in rows])
    total = len(rows)
    if cursor is not None:
        at = decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=_SESSIONS_RESOURCE, query="")
        key = datetime.fromisoformat(str(at.key))
        rows = [
            r
            for r in rows
            if cast(datetime, r["last_seen_at"]) < key
            or (cast(datetime, r["last_seen_at"]) == key and str(r["id"]) > at.id)
        ]
    page, more = rows[:size], len(rows) > size
    people = await _people([cast(UUID, r["user_id"]) for r in page])
    mine = await _viewer_session(ctx)
    items = tuple(
        SecuritySession(
            id=cast(UUID, r["id"]),
            person=people.get(cast(UUID, r["user_id"]), UserRef(cast(UUID, r["user_id"]), "")),
            started_at=cast(datetime, r["created_at"]),
            last_seen_at=cast(datetime, r["last_seen_at"]),
            mfa_at=cast(datetime | None, r["mfa_at"]),
            auth_method=cast(AuthMethod | None, r["auth_method"]),
            ip=seen.get(cast(UUID, r["id"]), (None, None))[0],
            device_label=seen.get(cast(UUID, r["id"]), (None, None))[1],
            current=r["id"] == mine,
        )
        for r in page
    )
    next_cursor = None
    if more and page:
        last = page[-1]
        next_cursor = encode_cursor(
            Position(cast(datetime, last["last_seen_at"]).isoformat(), str(last["id"])),
            tenant_id=ctx.tenant_id,
            resource=_SESSIONS_RESOURCE,
            query="",
        )
    return SessionPage(items, next_cursor, total)


async def sign_out(ctx: AuthContext, session_id: UUID) -> SignedOut:
    """AC-20: the session can no longer act in this firm; its other firms are unaffected."""
    await _authorised(ctx, "session.end")
    _human(ctx, "session.end")
    async with uow(ctx.tenant) as tx:
        owner = await tx.session.scalar(
            text("SELECT security_session_member(:id)"), {"id": session_id}
        )
        if owner is None:
            raise NotFound("auth_session")
        at = cast(
            datetime,
            await tx.session.scalar(
                text(
                    "INSERT INTO auth_session_tenant_revocations (tenant_id, session_id, user_id, "
                    "revoked_by) VALUES (:tenant, :id, :user, :by) RETURNING revoked_at"
                ),
                {"tenant": ctx.tenant_id, "id": session_id, "user": owner, "by": ctx.user_id},
            ),
        )
        tx.record(
            "session.signed_out",
            target=Target("auth_session", session_id),
            after=Ref(user_id=cast(UUID, owner)),
        )
        tx.emit(AccessChanged(user_id=cast(UUID, owner)))
    people = await _people([ctx.user_id])
    return SignedOut(session_id, at, people.get(ctx.user_id, UserRef(ctx.user_id, "")))


async def unlock(ctx: AuthContext, user_id: UUID) -> StaffLock:
    """AC-20: clear a staff sign-in lock where the provider allows it (DEC-526)."""
    await _authorised(ctx, "staff.unlock")
    _human(ctx, "staff.unlock")
    async with tenant_session(ctx.tenant) as session:
        if user_id not in await _seats(session):
            raise NotFound("member")
    port = _locks[0]
    until = await port.locked_until(user_id)
    if until is None:
        return StaffLock(user_id, locked=False, unlocks_at=None, cleared=False)
    if not await port.clear(user_id):
        return StaffLock(user_id, locked=True, unlocks_at=until, cleared=False)
    async with uow(ctx.tenant) as tx:
        tx.record("staff.unlocked", target=Target("user", user_id))
    return StaffLock(user_id, locked=False, unlocks_at=None, cleared=True)


# --- the support switch (AC-28) ------------------------------------------------------------------


async def support_access(ctx: AuthContext) -> SupportAccess:
    await _authorised(ctx, "support_session.read")
    async with tenant_session(ctx.tenant) as session:
        stored = await _policy_row(session)
    return await _support(stored)


async def put_support_access(ctx: AuthContext, *, allow: bool, version: int) -> SupportAccess:
    """AC-28: off, new support-session requests answer 409 `support_requests_disabled`; granted
    sessions keep their expiry."""
    await _authorised(ctx, "support_session.manage")
    _human(ctx, "support_session.manage")
    try:
        return await _switch_support(ctx, allow, version)
    except _Unchanged:
        async with tenant_session(ctx.tenant) as session:
            return await _support(await _policy_row(session))


async def _switch_support(ctx: AuthContext, allow: bool, version: int) -> SupportAccess:
    async with uow(ctx.tenant) as tx:
        before = await _policy_row(tx.session, lock=True)
        if before.support_version != version:
            raise StalePolicy(facts={"version": before.support_version})
        if allow == before.allow_support_requests:
            raise _Unchanged
        now = await _now(tx.session)
        after = replace(
            before,
            allow_support_requests=allow,
            support_updated_at=now,
            support_updated_by=ctx.user_id,
            support_version=before.support_version + 1,
            version=before.version + 1,
        )
        await _write(tx.session, ctx, before, after)
        tx.record(
            "support_access.updated",
            target=Target("security_policy", ctx.tenant_id),
            before=Ref(allow=int(before.allow_support_requests), version=before.support_version),
            after=Ref(allow=int(allow), version=after.support_version),
        )
        if not allow:
            # M2: switched off, requests still waiting for the firm are closed with it; a granted
            # session keeps its expiry (AC-28).
            for row in await list_support_sessions(tx.session):
                if row["status"] == "requested":
                    await close_support_session(tx.session, row["id"], "revoked")
                    tx.record(
                        "support_session.revoked",
                        target=Target("support_session", row["id"]),
                    )
    return await _support(after)


async def require_support_requests_allowed(session: AsyncSession) -> None:
    """SPEC-012's request and approval paths, in their own transaction: off answers 409; a firm
    without a row allows them (the default). Any failure to read refuses (the transaction
    aborts)."""
    allowed = await session.scalar(text("SELECT allow_support_requests FROM security_policies"))
    if allowed is not None and not bool(allowed):
        raise SupportRequestsDisabled


# --- the BFF's enforcement (DEC-524) -------------------------------------------------------------


@dataclass(frozen=True)
class StaffLimits:
    """The strictest of the person's firms: session limits in seconds; the firms that require
    SSO with the organisation of their connection (None: none yet); and the firms whose
    SSO-exempt account this person is."""

    idle_seconds: int = PLATFORM_MAX_IDLE_MINUTES * 60
    absolute_seconds: int = PLATFORM_MAX_SESSION_MINUTES * 60
    sso_firms: frozenset[tuple[UUID, str | None]] = field(
        default_factory=frozenset[tuple[UUID, str | None]]
    )
    exempt_in: frozenset[UUID] = field(default_factory=frozenset[UUID])

    def refuses(self, method: str | None, org: str | None = None) -> bool:
        """With SSO required, each such firm passes only an SSO sign-in through its own
        connection (M1, DEC-535), or its exempt account's hardware-key (passkey) sign-in
        (AC-18). An unknown method or organisation never passes (fail closed)."""
        for firm, connection in self.sso_firms:
            through_own = method == "sso" and connection is not None and org == connection
            exempt = firm in self.exempt_in and method == "passkey"
            if not (through_own or exempt):
                return True
        return False


async def staff_limits(user_id: UUID) -> StaffLimits:
    """Read in each of the person's active staff firms under its own row-level security."""
    idle, absolute = PLATFORM_MAX_IDLE_MINUTES, PLATFORM_MAX_SESSION_MINUTES
    sso: set[tuple[UUID, str | None]] = set()
    exempt: set[UUID] = set()
    for member in await active_memberships(user_id):
        if member.kind != "staff":
            continue
        tenant = TenantContext(member.tenant_id, "system", "auth:policy")
        async with tenant_session(tenant) as session:
            stored = await _policy_row(session)
        idle = min(idle, stored.session_idle_minutes)
        absolute = min(absolute, stored.session_absolute_minutes)
        if stored.require_sso:
            sso.add((member.tenant_id, stored.sso_connection_org))
        if stored.sso_exempt_user_id == user_id:
            exempt.add(member.tenant_id)
    return StaffLimits(idle * 60, absolute * 60, frozenset(sso), frozenset(exempt))


async def signed_out_everywhere(user_id: UUID, session_id: UUID) -> bool:
    """H1: the session was signed out of every firm the person is staff of, so a refresh has
    nothing left to mint a token for. A person with no staff firm is not this check's."""
    firms = [m.tenant_id for m in await active_memberships(user_id) if m.kind == "staff"]
    if not firms:
        return False
    for tenant_id in firms:
        tenant = TenantContext(tenant_id, "system", "auth:refresh")
        async with tenant_session(tenant) as session:
            revoked = await session.scalar(
                text("SELECT 1 FROM auth_session_tenant_revocations WHERE session_id = :id"),
                {"id": session_id},
            )
        if revoked is None:
            return False
    return True


async def record_exempt_sign_in(user_id: UUID, firms: frozenset[UUID]) -> None:
    """AC-18: the exempt account signed in: stamp "last tested" in each firm it is exempt in, and
    log it in that firm's trail as the person."""
    for tenant_id in sorted(firms, key=str):
        async with uow(TenantContext(tenant_id, "human", str(user_id))) as tx:
            await tx.session.execute(
                text(
                    "UPDATE security_policies SET sso_exempt_tested_at = clock_timestamp() "
                    "WHERE sso_exempt_user_id = :user"
                ),
                {"user": user_id},
            )
            tx.record(
                "sso_exempt_account.tested",
                target=Target("security_policy", tenant_id),
                after=Ref(user_id=user_id),
            )


async def refused_here(tenant: TenantContext, user_id: UUID) -> bool:
    """AC-20, H1 (DEC-528): once the person was signed out of this firm, a request here needs the
    BFF cookie of a live session of theirs that was not; a bearer token alone is refused."""
    async with tenant_session(tenant) as session:
        return bool(
            await session.scalar(
                text("SELECT auth_session_refused_here(:cookie, :user)"),
                {"cookie": _current_session_cookie(), "user": user_id},
            )
        )


async def purge_auth_sessions() -> int:
    """`auth_sessions` ended more than a year ago, and their cookies (P-01 hand-off)."""
    async with platform_transaction("system:auth_session_purge") as conn:
        return int(await conn.scalar(text("SELECT auth_session_purge()")) or 0)


@activity.defn(name="identity.purge_auth_sessions")
async def purge_auth_sessions_activity() -> int:
    purged = await purge_auth_sessions()
    _log.info("auth_session.purged", count=purged)
    return purged
