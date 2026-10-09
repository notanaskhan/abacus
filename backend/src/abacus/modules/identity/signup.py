"""Self-serve sign-up (SPEC-024 AC-1; TASK-040). PROTECTED.

A signed-in person with a provider-verified email and a founder-issued code (Q1, D2) creates
their firm and becomes its first firm administrator, in one reviewed definer transaction
(`firm_signup`). Every attempt is recorded as fingerprints for the rate limits (5 failures an hour
per identity, 20 per address; amendment 2) and every refusal is logged.
"""

from __future__ import annotations

import hashlib
import re
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict, DomainInvalid
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.repository import active_memberships, find_user, firm_signup
from abacus.modules.identity.tokens import VerifiedIdentity

_PLATFORM: Final = UUID(int=0)
_SPACE = re.compile(r"\s+")
_log = get_logger(__name__)


class SignupInvalid(DomainInvalid):
    """No provider-verified email, or a firm name that isn't 1 to 200 printable characters."""

    code = "signup_invalid"


class SignupCodeInvalid(DomainConflict):
    """The code is unknown, already used or expired."""

    code = "signup_code_invalid"


class AlreadyStaff(DomainConflict):
    """The person already belongs to a firm's staff: one firm per sign-up (SPEC-024 §4)."""

    code = "signup_already_staff"


class SignupRateLimited(DomainConflict):
    code = "signup_rate_limited"


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def clean_firm_name(name: str) -> str:
    spaced = "".join(" " if ch.isspace() else ch for ch in name)
    kept = _SPACE.sub(" ", "".join(ch for ch in spaced if ch.isprintable())).strip()
    if not 1 <= len(kept) <= 200:
        raise SignupInvalid("firm name")
    return kept


async def sign_up(identity: VerifiedIdentity, *, code: str, firm_name: str, address: str) -> UUID:
    """AC-1: the new firm's tenant, with the caller as its only firm administrator."""
    if identity.email is None:
        raise SignupInvalid("verified email")
    name = clean_firm_name(firm_name)
    identity_hash = _fingerprint(f"{identity.issuer}#{identity.subject}")
    # One firm per sign-up (SPEC-024 §4), read across firms through the identity role.
    user = await find_user(identity.issuer, identity.subject)
    if user is not None and any(m.kind == "staff" for m in await active_memberships(user.id)):
        _log.warning("signup.refused", outcome="already_member", identity=identity_hash[:16])
        raise AlreadyStaff("signup")
    async with uow(TenantContext(_PLATFORM, "system", "signup")) as tx:
        outcome, tenant_id = await firm_signup(
            tx.session,
            code_hash=_fingerprint(code.strip()),
            identity_hash=identity_hash,
            address_hash=_fingerprint(address),
            issuer=identity.issuer,
            subject=identity.subject,
            email=identity.email,
            display_name=identity.email.split("@", 1)[0][:200] or "Administrator",
            firm_name=name,
        )
        tx.record(
            "firm.signup_attempted",
            target=Target("firm", tenant_id or _PLATFORM),
            after=Ref(identity=identity_hash),
        )
    if tenant_id is None:
        _log.warning("signup.refused", outcome=outcome, identity=identity_hash[:16])
        if outcome == "rate_limited":
            raise SignupRateLimited("signup")
        raise SignupCodeInvalid("signup")
    async with uow(TenantContext(tenant_id, "system", "signup")) as tx:
        tx.record("firm.created", target=Target("firm", tenant_id), after=Ref(tenant=tenant_id))
    _log.info("signup.created", tenant_id=tenant_id)
    return tenant_id
