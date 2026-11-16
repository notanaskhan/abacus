"""Break-glass support sessions (SPEC-012, amended by SPEC-681; ADR-028; DEC-72). PROTECTED.

Staff have no standing access. A staff member (staff token, a separate issuer) requests a session
for one firm; only the firm decides: a `firm_admin` or `security_admin` with fresh MFA approves
it, or declines it (SPEC-681). There is no staff approval of any kind (OQ-1, DEC-5200): the
emergency second-staff path is removed. A session lasts at most 120 minutes; a content session
names one work item or engagement and reads nothing else (404, `authz` support scope); a content
session on a tenant holding TRI needs the requester's US-location attestation. While it is active
and unexpired (database time), requests with the staff token and `X-Support-Session` act as a
read-only support role on that firm only, and each is audited in the firm's trail before it runs
(fail closed).
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Final, Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError

from abacus.kernel._flags import SUPPORT_PANEL_V2
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainForbidden, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, audit_counts, uow
from abacus.modules.identity.authz import Resource, authorise
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import SupportSessionDeclined, SupportSessionRequested
from abacus.modules.identity.repository import (
    acknowledge_support_session,
    activate_support_session,
    close_support_session,
    decline_support_session,
    firm_exists,
    get_support_session,
    insert_support_session,
    list_support_sessions,
)
from abacus.modules.identity.security_policies import require_support_requests_allowed
from abacus.modules.identity.tokens import InvalidToken, VerifiedIdentity, staff_verifier

Scope = Literal["metadata", "content", "integration_settings"]
ScopeRefKind = Literal["work_item", "engagement"]
MAX_MINUTES: Final = 120  # SPEC-681 AC-22 (new rows; historic rows keep theirs)
APPROVER_ROLES: Final = frozenset({"firm_admin", "security_admin"})  # SPEC-681 AC-19, AC-20
SUPPORT_HEADER: Final = "X-Support-Session"
_SCOPE_LABELS: Final = {
    "metadata": "Metadata only",
    "integration_settings": "Integration settings only",
    "work_item": "Content · 1 work item",
    "engagement": "Content · 1 engagement",
}
_log = get_logger(__name__)


class SupportSessionInvalid(DomainInvalid):
    """A reason of 20 to 1,000 characters, a scope, 1 to 120 minutes, and one object for a
    content session (none for any other scope)."""

    code = "support_session_invalid"


class SupportSessionConflict(DomainConflict):
    """Not in a state that allows this (already approved, declined, ended, or one already
    open)."""

    code = "support_session_conflict"


class StaffLocationRequired(DomainForbidden):
    """A content session on a tenant holding TRI is run only by US-located staff (SPEC-681
    AC-23; D-OPS-21, RK-26): the staff token carries no `us_located` attestation."""

    code = "staff_location_required"


class SupportSessionInactive(Exception):
    """Not active, expired, revoked, ended, unknown, or another staff member's (401)."""


@dataclass(frozen=True)
class Staff:
    id: UUID
    subject: str
    mfa_at: datetime | None
    # G-04-T05 (SPEC-681 AC-23; DEC-5201): from the staff token's claims.
    us_located: bool = False
    platform_roles: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ScopeRef:
    kind: ScopeRefKind
    id: UUID


@dataclass(frozen=True)
class SupportSessionView:
    id: UUID
    staff_id: UUID
    staff_subject: str
    reason: str
    scope: str
    duration_minutes: int
    emergency: bool
    status: str  # requested | active | declined | ended | revoked | expired
    approved_by_kind: str | None  # firm_admin | security_admin (historic: staff)
    starts_at: datetime | None
    expires_at: datetime | None
    ended_at: datetime | None
    acknowledged: bool
    created_at: datetime
    requests: int = 0
    # G-04-T05 (SPEC-681): the one object, the thread, the decline and the attestation.
    scope_ref_kind: str | None = None
    scope_ref_id: UUID | None = None
    conversation_id: UUID | None = None
    declined_by: UUID | None = None
    declined_at: datetime | None = None
    staff_us_located: bool = False
    scope_label: str = ""


def staff_from_token(authorization: str | None) -> Staff:
    """The staff member a bearer token proves (the staff issuer only), with MFA (Q4)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise InvalidToken("no bearer token")
    identity: VerifiedIdentity = staff_verifier().verify(authorization.removeprefix("Bearer "))
    if identity.mfa_at is None:
        raise InvalidToken("staff tokens need MFA")
    staff_id = uuid5(NAMESPACE_URL, f"{identity.issuer}#{identity.subject}")
    return Staff(
        staff_id,
        identity.subject,
        identity.mfa_at,
        us_located=identity.us_located,
        platform_roles=identity.platform_roles,
    )


def _staff_tenant(firm_id: UUID, staff: Staff) -> TenantContext:
    return TenantContext(firm_id, "support", f"staff:{staff.id}")


def _view(row: RowMapping) -> SupportSessionView:
    status = str(row["status"])
    if status == "active" and not row["live"]:
        status = "expired"
    return SupportSessionView(
        row["id"],
        row["staff_id"],
        row["staff_subject"],
        row["reason"],
        row["scope"],
        row["duration_minutes"],
        row["emergency"],
        status,
        row["approved_by_kind"],
        row["starts_at"],
        row["expires_at"],
        row["ended_at"],
        row["acknowledged_at"] is not None,
        row["created_at"],
        scope_ref_kind=row["scope_ref_kind"],
        scope_ref_id=row["scope_ref_id"],
        conversation_id=row["conversation_id"],
        declined_by=row["declined_by"],
        declined_at=row["declined_at"],
        staff_us_located=bool(row["staff_us_located"]),
        scope_label=_SCOPE_LABELS.get(str(row["scope_ref_kind"] or row["scope"]), ""),
    )


# --- Hooks other modules register (identity imports no module) ----------------------------------

# Whether a tenant holds TRI (SPEC-681 AC-23): `platform` registers its entitlement read (a
# `tax` module). Unregistered, every tenant counts as holding TRI (fail closed).
HoldsTri = Callable[[TenantContext], Awaitable[bool]]
_holds_tri: HoldsTri | None = None
# The firm-side label of a content session's object, resolved in the firm's context and never
# returned to staff (SPEC-681 AC-17, AC-18); `engagements` registers it. Unregistered, the
# generic scope label stands.
ScopeLabeler = Callable[[TenantContext, str, UUID], Awaitable[str | None]]
_scope_labeler: ScopeLabeler | None = None


def register_tri_holder(check: HoldsTri) -> None:
    global _holds_tri
    _holds_tri = check


def register_scope_labeler(labeler: ScopeLabeler) -> None:
    global _scope_labeler
    _scope_labeler = labeler


async def _tenant_holds_tri(tenant: TenantContext) -> bool:
    if _holds_tri is None:
        return True
    try:
        return await _holds_tri(tenant)
    except Exception:  # fail closed: treat the tenant as holding TRI
        _log.warning("support.tri_check_failed", firm_id=tenant.tenant_id)
        return True


async def request_session(
    staff: Staff,
    firm_id: UUID,
    reason: str,
    scope: Scope,
    minutes: int,
    scope_ref: ScopeRef | None = None,
    conversation_id: UUID | None = None,
) -> SupportSessionView:
    """AC-1 (SPEC-012), AC-14, AC-22, AC-23 (SPEC-681): recorded and audited in the firm's trail;
    nothing is accessible until the firm approves."""
    reason = reason.strip()
    if not 20 <= len(reason) <= 1000 or not 1 <= minutes <= MAX_MINUTES:
        raise SupportSessionInvalid("reason or duration")
    if (scope == "content") != (scope_ref is not None):
        raise SupportSessionInvalid("a content session names one object; no other scope does")
    tenant = _staff_tenant(firm_id, staff)
    # SPEC-681 §6: the new scope and the thread link are firm-side v2 behaviour, per firm.
    if (scope == "integration_settings" or conversation_id is not None) and not (
        await flag_enabled(tenant, SUPPORT_PANEL_V2)
    ):
        raise SupportSessionInvalid("not available for this firm")
    if scope == "content" and not staff.us_located and await _tenant_holds_tri(tenant):
        raise StaffLocationRequired("content on a TRI tenant")
    session_id = uuid4()
    try:
        async with uow(tenant) as tx:
            if not await firm_exists(tx.session):
                raise NotFound("firm")
            # G-02-T14 (AC-28, DEC-72): the firm's "Allow support session requests"; off, a new
            # request answers 409 and sessions already granted keep their expiry.
            await require_support_requests_allowed(tx.session)
            await insert_support_session(
                tx.session,
                {
                    "id": session_id,
                    "tenant_id": firm_id,
                    "staff_id": staff.id,
                    "staff_subject": staff.subject,
                    "reason": reason,
                    "scope": scope,
                    "duration_minutes": minutes,
                    "emergency": False,
                    "scope_ref_kind": scope_ref.kind if scope_ref else None,
                    "scope_ref_id": scope_ref.id if scope_ref else None,
                    "conversation_id": conversation_id,
                    "staff_us_located": staff.us_located,
                },
            )
            tx.record(
                "support_session.requested",
                target=Target("support_session", session_id),
                after=Ref(staff_id=staff.id, minutes=minutes),
            )
            tx.emit(SupportSessionRequested(session_id=session_id))
    except IntegrityError:
        raise SupportSessionConflict("a session is already open") from None
    return await _read(tenant, session_id)


async def _read(tenant: TenantContext, session_id: UUID) -> SupportSessionView:
    async with tenant_session(tenant) as session:
        row = await get_support_session(session, session_id)
    if row is None:
        raise NotFound("support_session")
    return _view(row)


async def end_session(staff: Staff, firm_id: UUID, session_id: UUID) -> SupportSessionView:
    tenant = _staff_tenant(firm_id, staff)
    async with uow(tenant) as tx:
        row = await get_support_session(tx.session, session_id, lock=True)
        if row is None or row["staff_id"] != staff.id:
            raise NotFound("support_session")
        if row["status"] not in ("requested", "active"):
            raise SupportSessionConflict("already closed")
        await close_support_session(tx.session, session_id, "ended")
        tx.record("support_session.ended", target=Target("support_session", session_id))
    return await _read(tenant, session_id)


# --- Firm admins (AC-2, AC-9) ------------------------------------------------------------------


async def firm_sessions(ctx: AuthContext) -> list[SupportSessionView]:
    await authorise(ctx, "support_session.read", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        rows = await list_support_sessions(session)
        counts = await audit_counts(
            session, "support.request", "support_session", [row["id"] for row in rows]
        )
    views = [replace(_view(row), requests=counts.get(row["id"], 0)) for row in rows]
    return [await _labelled(ctx.tenant, view) for view in views]


async def _labelled(tenant: TenantContext, view: SupportSessionView) -> SupportSessionView:
    """The firm-side name of a content session's object (AC-18); never on a staff route."""
    if _scope_labeler is None or view.scope_ref_kind is None or view.scope_ref_id is None:
        return view
    try:
        label = await _scope_labeler(tenant, view.scope_ref_kind, view.scope_ref_id)
    except Exception:  # the generic label stands
        _log.warning("support.scope_label_failed", session_id=view.id)
        return view
    return replace(view, scope_label=label) if label else view


async def _firm_change(ctx: AuthContext, session_id: UUID, change: str) -> SupportSessionView:
    await authorise(ctx, "support_session.manage", Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        row = await get_support_session(tx.session, session_id, lock=True)
        if row is None:
            raise NotFound("support_session")
        if change == "approve":
            if row["status"] != "requested":
                raise SupportSessionConflict("not awaiting approval")
            # SPEC-681 AC-20: the firm's two approver roles; the role is recorded.
            if ctx.firm_role not in APPROVER_ROLES:
                raise SupportSessionConflict("only a firm admin or IT/Security approves")
            # G-02-T14 (security review M2): switched off, nothing pending is granted.
            await require_support_requests_allowed(tx.session)
            await activate_support_session(tx.session, session_id, str(ctx.firm_role), ctx.user_id)
            action = "support_session.approved"
        elif change == "revoke":
            if row["status"] not in ("requested", "active"):
                raise SupportSessionConflict("already closed")
            await close_support_session(tx.session, session_id, "revoked")
            action = "support_session.revoked"
        else:
            await acknowledge_support_session(tx.session, session_id)
            action = "support_session.acknowledged"
        tx.record(
            action,
            target=Target("support_session", session_id),
        )
    return await _read(ctx.tenant, session_id)


async def decline_session(ctx: AuthContext, session_id: UUID) -> SupportSessionView:
    """SPEC-681 AC-19: a `firm_admin` or `security_admin` declines a request (terminal)."""
    await authorise(ctx, "support_session.decline", Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, SUPPORT_PANEL_V2):
        raise NotFound(SUPPORT_PANEL_V2.name)
    async with uow(ctx.tenant) as tx:
        row = await get_support_session(tx.session, session_id, lock=True)
        if row is None:
            raise NotFound("support_session")
        if row["status"] != "requested":
            raise SupportSessionConflict("not awaiting approval")
        await decline_support_session(tx.session, session_id, ctx.user_id)
        tx.record("support_session.declined", target=Target("support_session", session_id))
        tx.emit(SupportSessionDeclined(session_id=session_id, declined_by=ctx.user_id))
    return await _read(ctx.tenant, session_id)


async def approve_session(ctx: AuthContext, session_id: UUID) -> SupportSessionView:
    return await _firm_change(ctx, session_id, "approve")


async def revoke_session(ctx: AuthContext, session_id: UUID) -> SupportSessionView:
    return await _firm_change(ctx, session_id, "revoke")


async def acknowledge_session(ctx: AuthContext, session_id: UUID) -> SupportSessionView:
    return await _firm_change(ctx, session_id, "acknowledge")


# --- Using a session (AC-4 to AC-8) ------------------------------------------------------------


async def support_context(
    authorization: str | None, firm: str | None, session: str | None
) -> AuthContext:
    """The read-only support context for an active session the token's staff member holds."""
    try:
        staff = staff_from_token(authorization)
        firm_id, session_id = UUID(str(firm)), UUID(str(session))
    except (InvalidToken, ValueError):
        raise SupportSessionInactive("no usable staff token or session") from None
    tenant = TenantContext(firm_id, "support", f"support:{session_id}")
    async with tenant_session(tenant) as db:
        row = await get_support_session(db, session_id)
    if row is None or row["staff_id"] != staff.id:
        raise SupportSessionInactive("not this staff member's session")
    if not row["live"]:
        if row["status"] == "active":
            await _mark_expired(tenant, session_id)
        raise SupportSessionInactive("session not active")
    role = "platform_support_content" if row["scope"] == "content" else "platform_support"
    # SPEC-681 AC-21: a content session reads its one object only (`authz` support scope).
    # A historic content session without one keeps SPEC-012's firm-wide content reads.
    scope_ref = (
        (str(row["scope_ref_kind"]), row["scope_ref_id"])
        if row["scope"] == "content" and row["scope_ref_id"] is not None
        else None
    )
    return AuthContext(
        tenant=tenant,
        user_id=staff.id,
        membership_id=session_id,
        firm_role=role,
        mfa_at=staff.mfa_at,
        support_scope=scope_ref,
    )


async def _mark_expired(tenant: TenantContext, session_id: UUID) -> None:
    try:
        async with uow(tenant) as tx:
            row = await get_support_session(tx.session, session_id, lock=True)
            if row is not None and row["status"] == "active" and not row["live"]:
                await close_support_session(tx.session, session_id, "expired")
                tx.record("support_session.expired", target=Target("support_session", session_id))
    except MissingAuditEvent:
        pass  # closed meanwhile: nothing to commit


async def audit_support_request(ctx: AuthContext, route: str, method: str) -> None:
    """AC-8: before the handler runs; a failure refuses the request (the caller raises)."""
    fingerprint = hashlib.sha256(f"{method} {route}".encode()).hexdigest()
    async with uow(ctx.tenant) as tx:
        tx.record(
            "support.request",
            target=Target("support_session", ctx.membership_id),
            after=Ref(route=fingerprint, staff_id=ctx.user_id),
        )
    _log.info("support.request", session_id=ctx.membership_id, method=method, route=route)
