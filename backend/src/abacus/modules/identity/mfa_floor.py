"""The portal's MFA floor (P-08-T17; DEC-34, ADR-146; SPEC-320 AC-10). PROTECTED.

Whether a client person must pass a second step to sign in to a firm's portal. Owners register
predicates with `register_mfa_requirement`: identity's `owner_grant` (an active `owner` grant),
engagements' `engagement_designation` (an `approver_of_record`, `signing_officer` or
`ske_designee` designation, DEC-63), and engagements' `tri_scope` (a grant on a K-1 package, a
`tax_return` work item or an engagement holding one; T-01-T12, C19). The floor fails closed:
a predicate that raises or takes longer than `PREDICATE_SECONDS`, an unregistered floor predicate,
or an unreadable firm policy all require the second step.

The firm's `portal_security_policies` row can only make the floor stricter: every client user
(`mfa_for_all_client_users`), and fewer trusted-device days than the 30-day ceiling. No setting
excludes anyone a predicate covers.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.logging import get_logger
from abacus.modules.identity.repository import active_grants

MfaRequirement = Callable[[TenantContext, UUID], Awaitable[bool]]
# The floor DEC-34 fixes today; each must be registered or the floor can't be checked.
FLOOR: Final = frozenset({"owner_grant", "engagement_designation", "tri_scope"})
PREDICATE_SECONDS: Final = 2.0
TRUSTED_DEVICE_DAYS: Final = 30  # the ceiling (DEC-35); a firm may set fewer, never more
_REQUIREMENTS: dict[str, MfaRequirement] = {}
_POLICY = text(
    "SELECT mfa_for_all_client_users, trusted_device_days FROM portal_security_policies"
)
_log = get_logger(__name__)


@dataclass(frozen=True)
class PortalSecurityPolicy:
    mfa_for_all_client_users: bool = False
    trusted_device_days: int = TRUSTED_DEVICE_DAYS


def register_mfa_requirement(name: str, predicate: MfaRequirement) -> None:
    """(tenant, user id) -> whether that person must pass the second step in that firm. The same
    function may register twice (a reloaded `api.py`); another under a taken name may not."""
    known = _REQUIREMENTS.get(name)
    if known is not None and (known.__module__, known.__qualname__) != (
        predicate.__module__,
        predicate.__qualname__,
    ):
        raise ValueError(f"MFA requirement {name!r} is already registered")
    _REQUIREMENTS[name] = predicate


def _context(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "portal:mfa")


async def portal_security_policy(tenant_id: UUID) -> PortalSecurityPolicy:
    """The firm's extension of the floor; the defaults when it has set none."""
    async with tenant_session(_context(tenant_id)) as session:
        row = (await session.execute(_POLICY)).first()
    if row is None:
        return PortalSecurityPolicy()
    return PortalSecurityPolicy(
        bool(row.mfa_for_all_client_users),
        min(int(cast(int, row.trusted_device_days)), TRUSTED_DEVICE_DAYS),
    )


async def _holds(name: str, predicate: MfaRequirement, tenant: TenantContext, user: UUID) -> bool:
    try:
        async with asyncio.timeout(PREDICATE_SECONDS):
            return bool(await predicate(tenant, user))
    except Exception as exc:  # a timeout or any failure: the second step is required
        _log.warning("portal_mfa.predicate_failed", predicate=name, error=type(exc).__name__)
        return True


async def mfa_required(tenant_id: UUID, user_id: UUID) -> bool:
    """Whether the person must pass the second step to sign in to this firm (fail closed)."""
    try:
        policy = await portal_security_policy(tenant_id)
    except Exception as exc:
        _log.warning("portal_mfa.policy_failed", error=type(exc).__name__)
        return True
    if policy.mfa_for_all_client_users:
        return True
    missing = FLOOR - _REQUIREMENTS.keys()
    if missing:
        _log.warning("portal_mfa.floor_unregistered", predicates=sorted(missing))
        return True
    tenant = _context(tenant_id)
    held = await asyncio.gather(
        *(_holds(name, p, tenant, user_id) for name, p in sorted(_REQUIREMENTS.items()))
    )
    return any(held)


async def owner_grant(tenant: TenantContext, user_id: UUID) -> bool:
    """identity's floor predicate: an active `owner` grant in the firm (DEC-34)."""
    return any(g.role == "owner" for g in await active_grants(tenant, user_id))
