"""Firm-side portal recovery (P-08-T21; SPEC-320 AC-18, AC-19; epic Stories 7.1, 7.2): clearing a
client's second-step lock with the sign-in lock, resetting a lost second factor, and a
recipient's renewal of an expired invitation (AC-14).

The callers (organisations' contact routes) authorise `contact.unlock` or `contact.mfa_reset` on
the contact's client first (walls answer 404) and pass the bound person. Both act only on a
client of the session's firm (the definers refuse anyone else) and are human-only (INV-1).

**MFA reset.** Only for a person with an active client membership here. A firm ends what is
its own: the person's trusted devices in this firm (revoked as `mfa_reset`) and their portal
sessions here, so their next sign-in here asks for the second step again, in the caller's unit of
work with `portal_mfa.reset` naming what was cleared; the notice email follows through the
outbox. The factor and its backup codes are the person's, one across firms (DEC-250): no firm
deletes them. The person resets them (POR-12 re-enrolment and recovery) or platform support
does. The answer is the same whatever other firms the person belongs to, so it says nothing
about them (DEC-329). Unlock clears only the firm's sign-in lock (`contact_access`).

**Invitation renewal.** An expired, never-accepted invitation found by its token on its own
firm's host is renewed at most twice (`renewal_count`): a fresh 14 days, the old token void, the
new one issued at delivery to the address it was sent to. Revoked or accepted ones never are.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, platform_transaction
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, UnitOfWork, uow
from abacus.modules.identity.contact_access import (
    _human,  # pyright: ignore[reportPrivateUsage] -- the module's one INV-1 check
)
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import ClientInvitationIssued, PortalMfaResetNoticeRequested
from abacus.modules.identity.invitations import INVITATION_DAYS
from abacus.modules.identity.repository import (
    count_invitation_renewal,
    extend_invitation,
    get_invitation,
    set_token_hash,
)

MAX_RENEWALS = 2
_log = get_logger(__name__)


@dataclass(frozen=True)
class MfaReset:
    devices_revoked: int
    sessions_ended: int


async def reset_portal_mfa(
    tx: UnitOfWork, ctx: AuthContext, *, client_id: UUID, contact_id: UUID, user_id: UUID | None
) -> MfaReset:
    """Story 7.2, after the caller authorised `contact.mfa_reset` for this client: this firm's
    trusted devices and portal sessions of the person end. Audited either way."""
    _human(ctx, "contact.mfa_reset")
    kinds: list[str] = []
    if user_id is not None:
        rows = await tx.session.execute(
            text("SELECT kind, ref FROM portal_mfa_reset(:user)"), {"user": user_id}
        )
        kinds = [str(r.kind) for r in rows]
    done = MfaReset(devices_revoked=kinds.count("device"), sessions_ended=kinds.count("session"))
    tx.record(
        "portal_mfa.reset",
        target=Target("client", client_id),
        after=Ref(
            contact_id=contact_id, devices=done.devices_revoked, sessions=done.sessions_ended
        ),
    )
    if user_id is not None:
        tx.emit(PortalMfaResetNoticeRequested(user_id=user_id))
    return done


async def renew_invitation(host: str, token_sha256: str) -> bool:
    """AC-14: a recipient renews an expired, never-accepted invitation by its token, on its own
    firm's host. False for anything else (no oracle: the route answers 202 either way)."""
    async with platform_transaction("portal:links") as conn:
        found = (
            await conn.execute(
                text("SELECT * FROM portal_invitation_find(:host, :token)"),
                {"host": host, "token": token_sha256},
            )
        ).first()
    if found is None:
        return False
    return await renew_invitation_by_id(UUID(str(found.tenant_id)), UUID(str(found.invitation_id)))


async def renew_invitation_by_id(tenant_id: UUID, invitation_id: UUID) -> bool:
    """The invitation's own rules decide (a portal email's `invitation` link defers here): only
    an expired, pending invitation, at most twice (`renewal_count`): a fresh 14 days, the old
    token void, the new one issued at delivery to the invitation's address."""
    ctx = TenantContext(tenant_id, "system", f"invitation:{invitation_id}")
    try:
        async with uow(ctx) as tx:
            row = await get_invitation(tx.session, invitation_id, lock=True)
            if row is None or row["status"] != "pending" or row["live"]:
                return False
            renewals = await count_invitation_renewal(tx.session, invitation_id, MAX_RENEWALS)
            if renewals is None:
                return False
            await extend_invitation(tx.session, invitation_id, INVITATION_DAYS)
            await set_token_hash(tx.session, invitation_id, None)
            tx.record(
                "client_invitation.renewed",
                target=Target("client_invitation", invitation_id),
                after=Ref(renewals=renewals),
            )
            tx.emit(ClientInvitationIssued(invitation_id=invitation_id))
    except MissingAuditEvent:
        return False  # refused before anything was written
    return True
