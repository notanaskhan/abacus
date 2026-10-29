"""Day-12 notice for client invitations about to lapse (P-07-T47; P-07 §4.8; DEC-540, DEC-1000).

A client invitation lives 14 days (DEC-35). P-07 §4.5 derives expiry at read time and has no
schedule of its own, so the notice rides the hourly identity pass on `access_end:platform`
(`access_end.sweep_access_ends_activity`): no new Schedule, workflow or history. For each firm,
every pending, unused invitation whose `expires_at` falls within the next two days gets one
`invitation.expiring` event (C16 `invitation_expiring`, to the firm admins; walls apply at read
time through the invitation's engagement) and one `client_invitation.expiry_notified` audit row,
once per invitation and expiry (`invitation_expiry_notices`). A resend or extension moves the
expiry, so the new end is noticed again; an invitation accepted, revoked or already expired is
never noticed.

Expiry is the database clock's, as `client_invitations.expires_at` is set and read
(`clock_timestamp()`), never the firm's demo clock. Firms are listed through the identity role and
each is read inside its own session (row-level security); one firm's failure is logged at error
(`invitation_expiry.firm_failed`), counted, and never stops the others or the access-end pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.events import InvitationExpiring
from abacus.modules.identity.repository import firm_tenant_ids

NOTICE_HOURS: Final = 48  # day 12 of 14 (P-07 §4.8)
_ACTOR: Final = "identity:invitation_expiry"
_log = get_logger(__name__)
_firm_failures = meter(__name__).create_counter(
    "abacus.invitation_expiry.firm_failed",
    description="Firms an invitation-expiry pass could not sweep",
)

_EXPIRING = text(
    "SELECT ci.id, ci.engagement_id, ci.expires_at FROM client_invitations ci "
    "WHERE ci.status = 'pending' AND ci.used_at IS NULL "
    "AND ci.expires_at > clock_timestamp() "
    "AND ci.expires_at <= clock_timestamp() + make_interval(hours => :hours) "
    "AND NOT EXISTS (SELECT 1 FROM invitation_expiry_notices n "
    "WHERE n.invitation_id = ci.id AND n.expires_at = ci.expires_at) "
    "ORDER BY ci.expires_at, ci.id"
)


@dataclass(frozen=True)
class ExpirySweep:
    firms: int
    notices: int
    failed_firms: int = 0


class _Skip(Exception):
    """Told already, or no longer pending: the unit of work rolls back."""


async def _notice(
    tenant_id: UUID, invitation_id: UUID, engagement_id: UUID, ends: datetime
) -> bool:
    try:
        async with uow(TenantContext(tenant_id, "system", _ACTOR)) as tx:
            # Re-read under a row lock: accepted, revoked or resent since the list was read.
            still = await tx.session.scalar(
                text(
                    "SELECT 1 FROM client_invitations WHERE id = :id AND status = 'pending' "
                    "AND used_at IS NULL AND expires_at = :ends "
                    "AND expires_at > clock_timestamp() FOR UPDATE"
                ),
                {"id": invitation_id, "ends": ends},
            )
            if still is None:
                raise _Skip
            inserted = await tx.session.scalar(
                text(
                    "INSERT INTO invitation_expiry_notices (tenant_id, invitation_id, expires_at) "
                    "VALUES (:tenant, :id, :ends) "
                    "ON CONFLICT (tenant_id, invitation_id, expires_at) DO NOTHING "
                    "RETURNING invitation_id"
                ),
                {"tenant": tenant_id, "id": invitation_id, "ends": ends},
            )
            if inserted is None:
                raise _Skip
            tx.record(
                "client_invitation.expiry_notified",
                target=Target("client_invitation", invitation_id),
                after=Ref(expires_at=int(ends.timestamp())),  # epoch seconds: refs hold no text
            )
            tx.emit(
                InvitationExpiring(
                    invitation_id=invitation_id, engagement_id=engagement_id, expires_at=ends
                )
            )
    except _Skip:
        return False
    return True


async def sweep_firm(tenant_id: UUID) -> int:
    """One firm's pass: the notices sent."""
    system = TenantContext(tenant_id, "system", _ACTOR)
    async with tenant_session(system) as session:
        rows = [
            (cast(UUID, r[0]), cast(UUID, r[1]), cast(datetime, r[2]))
            for r in (await session.execute(_EXPIRING, {"hours": NOTICE_HOURS})).all()
        ]
    notices = 0
    for invitation_id, engagement_id, ends in rows:
        if await _notice(tenant_id, invitation_id, engagement_id, ends):
            notices += 1
    return notices


async def sweep_invitation_expiry() -> ExpirySweep:
    """One pass over every firm; idempotent."""
    firms = await firm_tenant_ids()
    notices = failed = 0
    for tenant_id in firms:
        try:
            notices += await sweep_firm(tenant_id)
        except Exception as exc:  # one firm's failure never stops the others
            failed += 1
            _firm_failures.add(1)
            _log.error(
                "invitation_expiry.firm_failed", tenant_id=tenant_id, error=type(exc).__name__
            )
    _log.info("invitation_expiry.swept", firms=len(firms), notices=notices, failed_firms=failed)
    return ExpirySweep(len(firms), notices, failed)
