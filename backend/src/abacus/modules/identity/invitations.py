"""Client invitations and client members (SPEC-015). PROTECTED.

An invitation stores no token. Communications asks for one when it sends the email
(`issue_invitation_token`), and only its SHA-256 is kept, in `invitation_tokens` (TASK-030 D1).
Acceptance needs only a verified identity with a verified email (D2). Users and client
memberships are created only through reviewed definer functions (D3). Every acceptance failure
gives the same answer.
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
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, UnitOfWork, uow
from abacus.modules.identity.authz import Forbidden
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import ClientInvitationIssued
from abacus.modules.identity.repository import (
    add_client_membership,
    client_contacts,
    engagement_role,
    extend_invitation,
    find_token,
    get_invitation,
    insert_engagement_member,
    insert_invitation,
    invitations_today,
    membership_kind,
    pending_invitation_for,
    provision_client_user,
    remove_client_member,
    set_invitation_status,
    set_token_hash,
)
from abacus.modules.identity.tokens import VerifiedIdentity

ClientRole = Literal["client_admin", "client_contributor"]
INVITATION_DAYS: Final = 7
DAILY_LIMIT: Final = 50
_PLATFORM = UUID(int=0)
_log = get_logger(__name__)


class InvitationLimit(DomainConflict):
    """50 invitations per engagement per day (SPEC-015 Q4)."""

    code = "invitation_limit"


class InvitationInvalid(DomainInvalid):
    code = "invitation_invalid"


class InvitationNotFound(NotFound):
    """The same answer for every failed acceptance (SPEC-015 AC-5)."""


@dataclass(frozen=True)
class IssuedInvitation:
    token: str
    email: str
    expires_at: datetime
    engagement_id: UUID
    invited_by: UUID


@dataclass(frozen=True)
class ContactView:
    kind: str  # member | invitation
    id: UUID
    role: str
    email: str | None
    expires_at: datetime | None


@dataclass(frozen=True)
class AcceptedInvitation:
    tenant_id: UUID
    engagement_id: UUID


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def _client_admin_limited(ctx: AuthContext, engagement_id: UUID, role: str) -> None:
    """A client admin acts on contributors only (SPEC-015 Q2)."""
    if await engagement_role(ctx.tenant, ctx.user_id, engagement_id) == "client_admin" and (
        role != "client_contributor"
    ):
        raise Forbidden("client_contact.invite", "role")


async def create_invitation(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, email: str, role: ClientRole
) -> UUID:
    """Inside the caller's unit of work, after `authorise(client_contact.invite)` (AC-1 to AC-3).
    A pending invitation for the same email and engagement is replaced."""
    email = email.strip()
    if not 3 <= len(email) <= 320 or "@" not in email:
        raise InvitationInvalid("email")
    await _client_admin_limited(ctx, engagement_id, role)
    if await invitations_today(tx.session, engagement_id) >= DAILY_LIMIT:
        raise InvitationLimit(str(engagement_id))
    replaced = await pending_invitation_for(tx.session, engagement_id, email)
    if replaced is not None:
        await set_invitation_status(tx.session, replaced, "revoked")
        await set_token_hash(tx.session, replaced, None)
        tx.record("client_invitation.revoked", target=Target("client_invitation", replaced))
    invitation_id = uuid4()
    await insert_invitation(
        tx.session,
        {
            "id": invitation_id,
            "tenant_id": ctx.tenant_id,
            "engagement_id": engagement_id,
            "email": email,
            "role": role,
            "invited_by": ctx.user_id,
            "days": INVITATION_DAYS,
        },
    )
    tx.record(
        "client_invitation.created",
        target=Target("client_invitation", invitation_id),
        after=Ref(engagement_id=engagement_id, email=_digest(email.casefold())),
    )
    tx.emit(ClientInvitationIssued(invitation_id=invitation_id))
    return invitation_id


async def revoke_invitation(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, invitation_id: UUID
) -> None:
    row = await get_invitation(tx.session, invitation_id, lock=True)
    if row is None or row["engagement_id"] != engagement_id or row["status"] != "pending":
        raise NotFound("client_invitation")
    await _client_admin_limited(ctx, engagement_id, str(row["role"]))
    await set_invitation_status(tx.session, invitation_id, "revoked")
    await set_token_hash(tx.session, invitation_id, None)
    tx.record("client_invitation.revoked", target=Target("client_invitation", invitation_id))


async def resend_invitation(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, invitation_id: UUID
) -> None:
    """AC-10: a new token at delivery (the old one stops working) and a fresh 7 days."""
    row = await get_invitation(tx.session, invitation_id, lock=True)
    if row is None or row["engagement_id"] != engagement_id or row["status"] != "pending":
        raise NotFound("client_invitation")
    await _client_admin_limited(ctx, engagement_id, str(row["role"]))
    await extend_invitation(tx.session, invitation_id, INVITATION_DAYS)
    tx.record("client_invitation.resent", target=Target("client_invitation", invitation_id))
    tx.emit(ClientInvitationIssued(invitation_id=invitation_id))


async def remove_client(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, user_id: UUID
) -> None:
    """AC-8: their next request on the engagement is refused."""
    target_role = await engagement_role(ctx.tenant, user_id, engagement_id)
    if target_role not in ("client_admin", "client_contributor"):
        raise NotFound("client_contact")
    await _client_admin_limited(ctx, engagement_id, str(target_role))
    if not await remove_client_member(tx.session, engagement_id, user_id):
        raise NotFound("client_contact")
    tx.record(
        "client_member.removed",
        target=Target("engagement", engagement_id),
        after=Ref(user_id=user_id),
    )


async def contacts(ctx: AuthContext, engagement_id: UUID) -> list[ContactView]:
    """After `authorise(client_contact.read)` (AC-9)."""
    async with tenant_session(ctx.tenant) as session:
        rows = await client_contacts(session, engagement_id)
    return [ContactView(r["kind"], r["id"], r["role"], r["email"], r["expires_at"]) for r in rows]


async def issue_invitation_token(tenant_id: UUID, invitation_id: UUID) -> IssuedInvitation | None:
    """For communications, at delivery: a fresh token whose hash replaces any earlier one. None
    when the invitation is no longer pending (revoked, accepted or expired)."""
    token = secrets.token_urlsafe(32)
    ctx = TenantContext(tenant_id, "system", f"invitation:{invitation_id}")
    try:
        async with uow(ctx) as tx:
            row = await get_invitation(tx.session, invitation_id, lock=True)
            if row is None or not row["live"]:
                return None
            await set_token_hash(tx.session, invitation_id, _digest(token))
            tx.record(
                "client_invitation.token_issued",
                target=Target("client_invitation", invitation_id),
            )
    except MissingAuditEvent:
        return None
    return IssuedInvitation(
        token, str(row["email"]), row["expires_at"], row["engagement_id"], row["invited_by"]
    )


async def accept_invitation(identity: VerifiedIdentity, token: str) -> AcceptedInvitation:
    """AC-4 to AC-6. `InvitationNotFound` for every failure: an unknown, used, revoked or
    expired token, another email, a staff member of the firm, or a locked-out identity."""
    if identity.email is None or not 20 <= len(token) <= 200:
        raise InvitationNotFound("invitation")
    attempt = _digest(f"{identity.issuer}#{identity.subject}")
    async with uow(TenantContext(_PLATFORM, "system", "invitations:accept")) as tx:
        found = await find_token(tx.session, _digest(token), attempt)
        tx.record(
            "client_invitation.accept_attempted",
            target=Target("client_invitation", found["invitation_id"] if found else _PLATFORM),
            after=Ref(identity=attempt),
        )
    if found is None:
        raise InvitationNotFound("invitation")
    tenant_id, invitation_id = found["tenant_id"], found["invitation_id"]
    ctx = TenantContext(tenant_id, "system", f"invitation:{invitation_id}")
    async with uow(ctx) as tx:
        row = await get_invitation(tx.session, invitation_id, lock=True)
        if (
            row is None
            or not row["live"]
            or str(row["email"]).casefold() != identity.email.casefold()
        ):
            raise InvitationNotFound("invitation")
        name = identity.email.split("@", 1)[0][:200] or "Client"
        user_id = await provision_client_user(
            tx.session, identity.issuer, identity.subject, identity.email, name
        )
        if await membership_kind(tx.session, user_id) == "staff":
            raise InvitationNotFound("invitation")  # Q5: never staff and client of one firm
        await add_client_membership(tx.session, user_id)
        engagement_id = row["engagement_id"]
        if await engagement_role(ctx, user_id, engagement_id) is None:
            await insert_engagement_member(
                tx.session, tenant_id, engagement_id, user_id, row["role"]
            )
        await set_invitation_status(tx.session, invitation_id, "accepted", user_id)
        await set_token_hash(tx.session, invitation_id, None)
        tx.record(
            "client_invitation.accepted",
            target=Target("client_invitation", invitation_id),
            after=Ref(user_id=user_id),
        )
    _log.info("client_invitation.accepted", tenant_id=tenant_id, invitation_id=invitation_id)
    return AcceptedInvitation(tenant_id, engagement_id)
