"""Firm-side portal recovery (P-08-T21; SPEC-320 AC-18, AC-19; epic Stories 7.1, 7.2): clearing a
client's second-step lock with the sign-in lock, resetting a lost second factor, and a
recipient's renewal of an expired invitation (AC-14).

The callers (organisations' contact routes) authorise `contact.unlock` or `contact.mfa_reset` on
the contact's client first (walls answer 404) and pass the bound person. Both act only on a
client of the session's firm (the definers refuse anyone else) and are human-only (INV-1).

**MFA reset.** The person's factor and backup codes are removed (the factor is the person's,
one across firms, DEC-250, so their next sign-in in any firm enrols again: two-step setup), their
trusted devices in this firm revoked as `mfa_reset` and their portal sessions here ended, in the
caller's unit of work with `portal_mfa.reset`; the notice email follows through the outbox. The
factor is removed at the identity provider after the commit, best effort: the row that names it is
already gone, so it can never be used again.

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
from abacus.modules.identity.portal_idp import PortalIdpUnavailable, portal_idp
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
    had_factor: bool
    devices_revoked: int
    sessions_ended: int
    factor_ref: str | None  # for the provider, after the commit; never returned to a caller


async def reset_portal_mfa(
    tx: UnitOfWork, ctx: AuthContext, *, client_id: UUID, contact_id: UUID, user_id: UUID | None
) -> MfaReset:
    """Story 7.2, after the caller authorised `contact.mfa_reset` for this client. A contact
    nobody has signed in as has nothing to reset; the reset is audited either way."""
    _human(ctx, "contact.mfa_reset")
    kinds: list[tuple[str, str]] = []
    if user_id is not None:
        rows = await tx.session.execute(
            text("SELECT kind, ref FROM portal_mfa_reset(:user)"), {"user": user_id}
        )
        kinds = [(str(r.kind), str(r.ref)) for r in rows]
    factor = next((ref for kind, ref in kinds if kind in ("factor", "pending_factor")), None)
    done = MfaReset(
        had_factor=any(kind == "factor" for kind, _ in kinds),
        devices_revoked=sum(kind == "device" for kind, _ in kinds),
        sessions_ended=sum(kind == "session" for kind, _ in kinds),
        factor_ref=factor,
    )
    tx.record(
        "portal_mfa.reset",
        target=Target("client", client_id),
        after=Ref(
            contact_id=contact_id,
            factor=int(done.had_factor),
            devices=done.devices_revoked,
            sessions=done.sessions_ended,
        ),
    )
    if user_id is not None:
        tx.emit(PortalMfaResetNoticeRequested(user_id=user_id))
    return done


async def remove_provider_factor(factor_ref: str | None) -> None:
    """After the reset commits: the factor at the identity provider. A failure is logged; the
    factor is already unusable (no row names it)."""
    if factor_ref is None:
        return
    try:
        await portal_idp().remove_factor(factor_ref)
    except PortalIdpUnavailable:
        _log.warning("portal_mfa.provider_factor_kept")


async def unlock_portal_mfa(tx: UnitOfWork, ctx: AuthContext, user_id: UUID | None) -> bool:
    """Story 7.1, beside the sign-in lock: the second-step lock on the person's factor (set by
    their third wrong TOTP or backup code). Whether there was one."""
    _human(ctx, "contact.unlock")
    if user_id is None:
        return False
    found = await tx.session.execute(text("SELECT portal_mfa_unlock(:user)"), {"user": user_id})
    return bool(found.scalar_one())


async def renew_invitation(host: str, token_sha256: str) -> bool:
    """AC-14: a recipient renews an expired, never-accepted invitation, at most twice. False for
    anything else (no oracle: the route answers 202 either way)."""
    async with platform_transaction("portal:links") as conn:
        found = (
            await conn.execute(
                text("SELECT * FROM portal_invitation_find(:host, :token)"),
                {"host": host, "token": token_sha256},
            )
        ).first()
    if found is None:
        return False
    tenant_id, invitation_id = UUID(str(found.tenant_id)), UUID(str(found.invitation_id))
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
