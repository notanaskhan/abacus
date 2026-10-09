"""Staff invitations, firm roles and revocation (SPEC-024 AC-3, AC-4; TASK-041). PROTECTED.

Every action, reading the list included, is `firm.manage_users` (fresh MFA). Invitations store no
token: communications asks for one at delivery and only its SHA-256 is kept. Memberships change
only through reviewed definer functions, which keep at least one active firm administrator.
Revocation applies on the person's next request (memberships are read fresh).
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal
from uuid import UUID, uuid4

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, uow
from abacus.modules.identity.authz import Resource, authorise
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import StaffInvitationIssued
from abacus.modules.identity.repository import (
    add_staff_membership,
    extend_staff_invitation,
    find_staff_token,
    get_staff_invitation,
    insert_staff_invitation,
    pending_staff_invitation_for,
    pending_staff_invitations,
    provision_client_user,
    revoke_membership,
    set_firm_role,
    set_staff_invitation_status,
    set_staff_token_hash,
    staff_memberships,
    user_contacts,
)
from abacus.modules.identity.tokens import VerifiedIdentity

FirmRole = Literal["firm_admin", "practice_leader", "quality_partner"]
INVITATION_DAYS: Final = 14
# For audit references (integers only, never text); 0 is no firm role.
_ROLE_INDEX: Final = {"firm_admin": 1, "practice_leader": 2, "quality_partner": 3}
_PLATFORM: Final = UUID(int=0)
_log = get_logger(__name__)


class StaffInvitationInvalid(DomainInvalid):
    code = "staff_invitation_invalid"


class StaffInvitationNotFound(NotFound):
    """The same answer for every failed acceptance (as SPEC-015 AC-5)."""


class LastAdmin(DomainConflict):
    """The firm must keep at least one active firm administrator (SPEC-024 AC-4)."""

    code = "last_admin"


class ClientContact(DomainConflict):
    """Someone who is a client contact of this firm can't also be its staff (SPEC-015 Q5)."""

    code = "client_contact"


@dataclass(frozen=True)
class StaffMember:
    user_id: UUID
    display_name: str
    email: str
    firm_role: str | None
    status: str


@dataclass(frozen=True)
class StaffInvitation:
    id: UUID
    email: str
    firm_role: str | None
    expires_at: datetime
    created_at: datetime


@dataclass(frozen=True)
class StaffList:
    members: list[StaffMember]
    invitations: list[StaffInvitation]


@dataclass(frozen=True)
class IssuedStaffInvitation:
    token: str
    email: str
    expires_at: datetime
    tenant_id: UUID


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def _manage(ctx: AuthContext) -> None:
    await authorise(ctx, "firm.manage_users", Resource.firm(ctx.tenant_id))


async def staff(ctx: AuthContext) -> StaffList:
    """The firm's staff (active and revoked) and pending invitations."""
    await _manage(ctx)
    async with tenant_session(ctx.tenant) as session:
        members = await staff_memberships(session)
        pending = await pending_staff_invitations(session)
    contacts = await user_contacts([m["user_id"] for m in members])
    return StaffList(
        [
            StaffMember(
                m["user_id"],
                contacts.get(m["user_id"], ("", ""))[0],
                contacts.get(m["user_id"], ("", ""))[1],
                m["firm_role"],
                m["status"],
            )
            for m in members
        ],
        [
            StaffInvitation(p["id"], p["email"], p["firm_role"], p["expires_at"], p["created_at"])
            for p in pending
        ],
    )


async def invite(ctx: AuthContext, email: str, firm_role: FirmRole | None) -> UUID:
    """AC-3: a single-use, expiring link by email; a pending one for the same email is replaced."""
    await _manage(ctx)
    email = email.strip()
    if not 3 <= len(email) <= 320 or "@" not in email:
        raise StaffInvitationInvalid("email")
    invitation_id = uuid4()
    async with uow(ctx.tenant) as tx:
        replaced = await pending_staff_invitation_for(tx.session, email)
        if replaced is not None:
            await set_staff_invitation_status(tx.session, replaced, "revoked")
            await set_staff_token_hash(tx.session, replaced, None)
            tx.record("staff_invitation.revoked", target=Target("staff_invitation", replaced))
        await insert_staff_invitation(
            tx.session,
            {
                "id": invitation_id,
                "tenant_id": ctx.tenant_id,
                "email": email,
                "firm_role": firm_role,
                "invited_by": ctx.user_id,
                "days": INVITATION_DAYS,
            },
        )
        tx.record(
            "staff_invitation.created",
            target=Target("staff_invitation", invitation_id),
            after=Ref(email=_digest(email.casefold())),
        )
        tx.emit(StaffInvitationIssued(invitation_id=invitation_id))
    return invitation_id


async def resend(ctx: AuthContext, invitation_id: UUID) -> None:
    await _manage(ctx)
    async with uow(ctx.tenant) as tx:
        row = await get_staff_invitation(tx.session, invitation_id, lock=True)
        if row is None or row["status"] != "pending":
            raise NotFound("staff_invitation")
        await extend_staff_invitation(tx.session, invitation_id, INVITATION_DAYS)
        tx.record("staff_invitation.resent", target=Target("staff_invitation", invitation_id))
        tx.emit(StaffInvitationIssued(invitation_id=invitation_id))


async def revoke_invitation(ctx: AuthContext, invitation_id: UUID) -> None:
    await _manage(ctx)
    async with uow(ctx.tenant) as tx:
        row = await get_staff_invitation(tx.session, invitation_id, lock=True)
        if row is None or row["status"] != "pending":
            raise NotFound("staff_invitation")
        await set_staff_invitation_status(tx.session, invitation_id, "revoked")
        await set_staff_token_hash(tx.session, invitation_id, None)
        tx.record("staff_invitation.revoked", target=Target("staff_invitation", invitation_id))


async def change_role(ctx: AuthContext, user_id: UUID, firm_role: FirmRole | None) -> None:
    """AC-4: applies on their next request; never the last administrator."""
    await _manage(ctx)
    async with uow(ctx.tenant) as tx:
        outcome = await set_firm_role(tx.session, user_id, firm_role)
        if outcome == "not_found":
            raise NotFound("staff_member")
        if outcome == "last_admin":
            raise LastAdmin("firm_admin")
        tx.record(
            "membership.role_changed",
            target=Target("user", user_id),
            after=Ref(role=_ROLE_INDEX.get(firm_role or "", 0)),
        )


async def revoke(ctx: AuthContext, user_id: UUID) -> None:
    """AC-4: their next request is refused; never the last administrator."""
    await _manage(ctx)
    async with uow(ctx.tenant) as tx:
        outcome = await revoke_membership(tx.session, user_id)
        if outcome == "not_found":
            raise NotFound("staff_member")
        if outcome == "last_admin":
            raise LastAdmin("firm_admin")
        tx.record("membership.revoked", target=Target("user", user_id))


async def issue_staff_invitation_token(
    tenant_id: UUID, invitation_id: UUID
) -> IssuedStaffInvitation | None:
    """For communications, at delivery: a fresh token whose hash replaces any earlier one."""
    token = secrets.token_urlsafe(32)
    ctx = TenantContext(tenant_id, "system", f"staff_invitation:{invitation_id}")
    try:
        async with uow(ctx) as tx:
            row = await get_staff_invitation(tx.session, invitation_id, lock=True)
            if row is None or not row["live"]:
                return None
            await set_staff_token_hash(tx.session, invitation_id, _digest(token))
            tx.record(
                "staff_invitation.token_issued", target=Target("staff_invitation", invitation_id)
            )
    except MissingAuditEvent:
        return None
    return IssuedStaffInvitation(token, str(row["email"]), row["expires_at"], tenant_id)


async def accept_staff_invitation(identity: VerifiedIdentity, token: str) -> UUID:
    """The invited person joins the firm's staff with the invitation's firm role. Every failure
    is the same `StaffInvitationNotFound` (unknown, used, revoked or expired token, another
    email, a locked-out identity), except a client contact of the firm (`ClientContact`)."""
    if identity.email is None or not 20 <= len(token) <= 200:
        raise StaffInvitationNotFound("staff_invitation")
    attempt = _digest(f"{identity.issuer}#{identity.subject}")
    async with uow(TenantContext(_PLATFORM, "system", "staff_invitations:accept")) as tx:
        found = await find_staff_token(tx.session, _digest(token), attempt)
        tx.record(
            "staff_invitation.accept_attempted",
            target=Target("staff_invitation", found["invitation_id"] if found else _PLATFORM),
            after=Ref(identity=attempt),
        )
    if found is None:
        raise StaffInvitationNotFound("staff_invitation")
    tenant_id, invitation_id = found["tenant_id"], found["invitation_id"]
    ctx = TenantContext(tenant_id, "system", f"staff_invitation:{invitation_id}")
    async with uow(ctx) as tx:
        row = await get_staff_invitation(tx.session, invitation_id, lock=True)
        if (
            row is None
            or not row["live"]
            or str(row["email"]).casefold() != identity.email.casefold()
        ):
            raise StaffInvitationNotFound("staff_invitation")
        name = identity.email.split("@", 1)[0][:200] or "Staff"
        user_id = await provision_client_user(
            tx.session, identity.issuer, identity.subject, identity.email, name
        )
        if await add_staff_membership(tx.session, user_id, row["firm_role"]) == "client_contact":
            raise ClientContact("staff_invitation")
        await set_staff_invitation_status(tx.session, invitation_id, "accepted", user_id)
        await set_staff_token_hash(tx.session, invitation_id, None)
        tx.record(
            "staff_invitation.accepted",
            target=Target("staff_invitation", invitation_id),
            after=Ref(user_id=user_id),
        )
    _log.info("staff_invitation.accepted", tenant_id=tenant_id, invitation_id=invitation_id)
    return tenant_id
