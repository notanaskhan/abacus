"""Break-glass support sessions (SPEC-012; ADR-028). PROTECTED.

Staff have no standing access. A staff member (staff token, a separate issuer) requests a session
for one firm; a firm admin with fresh MFA approves it, or, in an emergency, a second staff member
does (at most an hour, flagged to the firm until acknowledged). While it is active and unexpired
(database time), requests with the staff token and `X-Support-Session` act as a read-only support
role on that firm only, and each is audited in the firm's trail before it runs (fail closed).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Final, Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, audit_counts, uow
from abacus.modules.identity.authz import Resource, authorise
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import (
    SupportSessionEmergencyApproved,
    SupportSessionRequested,
)
from abacus.modules.identity.repository import (
    acknowledge_support_session,
    activate_support_session,
    close_support_session,
    firm_exists,
    get_support_session,
    insert_support_session,
    list_support_sessions,
)
from abacus.modules.identity.tokens import InvalidToken, VerifiedIdentity, staff_verifier

Scope = Literal["metadata", "content"]
MAX_MINUTES: Final = 240
EMERGENCY_MINUTES: Final = 60
SUPPORT_HEADER: Final = "X-Support-Session"
_log = get_logger(__name__)


class SupportSessionInvalid(DomainInvalid):
    """A reason of 20 to 1,000 characters, a scope, and 1 to 240 minutes (60 in an emergency)."""

    code = "support_session_invalid"


class SupportSessionConflict(DomainConflict):
    """Not in a state that allows this (already approved, ended, or one already open), or a
    staff member approving their own request."""

    code = "support_session_conflict"


class SupportSessionInactive(Exception):
    """Not active, expired, revoked, ended, unknown, or another staff member's (401)."""


@dataclass(frozen=True)
class Staff:
    id: UUID
    subject: str
    mfa_at: datetime | None


@dataclass(frozen=True)
class SupportSessionView:
    id: UUID
    staff_id: UUID
    staff_subject: str
    reason: str
    scope: str
    duration_minutes: int
    emergency: bool
    status: str  # requested | active | ended | revoked | expired
    approved_by_kind: str | None
    starts_at: datetime | None
    expires_at: datetime | None
    ended_at: datetime | None
    acknowledged: bool
    created_at: datetime
    requests: int = 0


def staff_from_token(authorization: str | None) -> Staff:
    """The staff member a bearer token proves (the staff issuer only), with MFA (Q4)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise InvalidToken("no bearer token")
    identity: VerifiedIdentity = staff_verifier().verify(authorization.removeprefix("Bearer "))
    if identity.mfa_at is None:
        raise InvalidToken("staff tokens need MFA")
    staff_id = uuid5(NAMESPACE_URL, f"{identity.issuer}#{identity.subject}")
    return Staff(staff_id, identity.subject, identity.mfa_at)


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
    )


async def request_session(
    staff: Staff, firm_id: UUID, reason: str, scope: Scope, minutes: int, emergency: bool
) -> SupportSessionView:
    """AC-1: recorded and audited in the firm's trail; nothing is accessible yet."""
    reason = reason.strip()
    limit = EMERGENCY_MINUTES if emergency else MAX_MINUTES
    if not 20 <= len(reason) <= 1000 or not 1 <= minutes <= limit:
        raise SupportSessionInvalid("reason or duration")
    tenant = _staff_tenant(firm_id, staff)
    session_id = uuid4()
    try:
        async with uow(tenant) as tx:
            if not await firm_exists(tx.session):
                raise NotFound("firm")
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
                    "emergency": emergency,
                },
            )
            tx.record(
                "support_session.requested",
                target=Target("support_session", session_id),
                after=Ref(staff_id=staff.id, minutes=minutes, emergency=int(emergency)),
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


async def emergency_approve(staff: Staff, firm_id: UUID, session_id: UUID) -> SupportSessionView:
    """AC-3: a second staff member approves an emergency request; never its requester."""
    tenant = _staff_tenant(firm_id, staff)
    async with uow(tenant) as tx:
        row = await get_support_session(tx.session, session_id, lock=True)
        if row is None:
            raise NotFound("support_session")
        if not row["emergency"] or row["status"] != "requested" or row["staff_id"] == staff.id:
            raise SupportSessionConflict("not an emergency request another staff member made")
        await activate_support_session(tx.session, session_id, "staff", staff.id)
        tx.record(
            "support_session.emergency_approved",
            target=Target("support_session", session_id),
            after=Ref(staff_id=staff.id),
        )
        tx.emit(SupportSessionEmergencyApproved(session_id=session_id))
    _log.warning("support.emergency_session", firm_id=firm_id, session_id=session_id)
    return await _read(tenant, session_id)


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
    return [replace(_view(row), requests=counts.get(row["id"], 0)) for row in rows]


async def _firm_change(ctx: AuthContext, session_id: UUID, change: str) -> SupportSessionView:
    await authorise(ctx, "support_session.manage", Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        row = await get_support_session(tx.session, session_id, lock=True)
        if row is None:
            raise NotFound("support_session")
        if change == "approve":
            if row["status"] != "requested":
                raise SupportSessionConflict("not awaiting approval")
            await activate_support_session(tx.session, session_id, "firm_admin", ctx.user_id)
            action = "support_session.approved"
        elif change == "revoke":
            if row["status"] not in ("requested", "active"):
                raise SupportSessionConflict("already closed")
            await close_support_session(tx.session, session_id, "revoked")
            action = "support_session.revoked"
        else:
            await acknowledge_support_session(tx.session, session_id)
            action = "support_session.acknowledged"
        tx.record(action, target=Target("support_session", session_id))
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
    return AuthContext(
        tenant=tenant,
        user_id=staff.id,
        membership_id=session_id,
        firm_role=role,
        mfa_at=staff.mfa_at,
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
