"""A recent second factor for the review grammar's verdicts (ADR-160 clauses 8 and 12; DEC-501,
DEC-505). Signing (`sign_off.create`, `sign_off.bulk`) and deciding (`decision.decide`) carry
`mfa_recent: required` in the matrix; these answer the fixed 403 `mfa_required` with the window,
so the shell steps up through ConfirmItsYou and retries, instead of a bare 403."""

from __future__ import annotations

from datetime import timedelta

from abacus.kernel.clock import system_now
from abacus.kernel.errors import DomainForbidden
from abacus.modules.identity.api import MFA_RECENT, AuthContext

MAX_AGE_S = int(MFA_RECENT.total_seconds())


class MfaRequired(DomainForbidden):
    """No second factor verified in the last `max_age_s` seconds."""

    code = "mfa_required"


def require_fresh(ctx: AuthContext, max_age_s: int = MAX_AGE_S) -> None:
    """Refuse unless the caller verified a second factor within `max_age_s` (at most the
    matrix's 15 minutes: a kind may only tighten it)."""
    limit = min(max_age_s, MAX_AGE_S)
    if ctx.mfa_at is None or system_now() - ctx.mfa_at > timedelta(seconds=limit):
        raise MfaRequired(facts={"max_age_s": limit})
