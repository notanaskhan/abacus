"""Sign-in and the request context (ADR-002, ADR-029). PROTECTED. TASK-007 design §4.

1. Verify the bearer token (401 if not valid).
2. Resolve the user by issuer and subject (403 if unknown).
3. Load the user's active memberships, fresh on every request.
4. Choose the active tenant: the only membership, or the one named in `X-Abacus-Tenant`, which
   counts only if it matches an active membership. Otherwise 403.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.repository import (
    MembershipRecord,
    UserRecord,
    active_memberships,
    find_user,
)
from abacus.modules.identity.tokens import InvalidToken, VerifiedIdentity, token_verifier

TENANT_HEADER = "X-Abacus-Tenant"


class Unauthenticated(Exception):
    """No valid bearer token."""


class NoActiveTenant(Exception):
    """Authenticated, but no tenant this user may act in was chosen."""


@dataclass(frozen=True)
class SignedIn:
    """A verified user and their active memberships; no tenant chosen yet."""

    user: UserRecord
    identity: VerifiedIdentity
    memberships: list[MembershipRecord]


def _bearer(authorization: str | None) -> str:
    if authorization is None:
        raise Unauthenticated("missing bearer token")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise Unauthenticated("missing bearer token")
    return token.strip()


async def sign_in(authorization: str | None) -> SignedIn:
    try:
        identity = token_verifier().verify(_bearer(authorization))
    except InvalidToken as exc:
        raise Unauthenticated(str(exc)) from None
    user = await find_user(identity.issuer, identity.subject)
    if user is None:
        raise NoActiveTenant("unknown user")
    return SignedIn(user, identity, await active_memberships(user.id))


def choose_tenant(signed_in: SignedIn, requested: str | None) -> AuthContext:
    memberships = signed_in.memberships
    if requested is not None:
        try:
            tenant_id = UUID(requested)
        except ValueError:
            raise NoActiveTenant("malformed tenant") from None
        chosen = [m for m in memberships if m.tenant_id == tenant_id]
    else:
        chosen = memberships if len(memberships) == 1 else []
    if len(chosen) != 1:
        raise NoActiveTenant("no active membership chosen")
    membership = chosen[0]
    user_id = signed_in.user.id
    return AuthContext(
        tenant=TenantContext(membership.tenant_id, "human", str(user_id)),
        user_id=user_id,
        membership_id=membership.membership_id,
        firm_role=membership.firm_role,
        mfa_at=signed_in.identity.mfa_at,
    )
