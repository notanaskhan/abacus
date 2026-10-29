"""The record-mode writes' authorisation (A-01-T23; DEC-547, DEC-592).

`authorise`, with a stale second factor told apart from every other refusal: the release and
archive records answer it with 403 `facts.reason = mfa_required`, as the export routes do, so the
shell's step-up opens for that alone and a role, wall, independence or archived refusal reads as
a refusal. Then the act must be a live person's own (INV-1): never an agent, the platform or a
support session.
"""

from __future__ import annotations

from datetime import datetime

from abacus.kernel.clock import system_now
from abacus.kernel.errors import DomainForbidden
from abacus.modules.identity.api import (
    MFA_RECENT,
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
)


class RecordNeedsMfa(DomainForbidden):
    """The role allows it, but the last second factor is older than 15 minutes: verify again,
    then retry (the shell's step-up). Answers `facts.reason = mfa_required`."""

    code = "forbidden"


def _stale(ctx: AuthContext) -> bool:
    return ctx.mfa_at is None or system_now() - ctx.mfa_at > MFA_RECENT


async def authorise_record(ctx: AuthContext, action: str, resource: Resource) -> None:
    """The matrix row (role, independence, walls, archived, fresh MFA), then a live person."""
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")
    try:
        await authorise(ctx, action, resource)
    except Forbidden as refused:
        if refused.layer != "attribute" or resource.archived or not _stale(ctx):
            raise
        # Step up only when the stale factor is the sole blocker (DEC-598): every other layer
        # must allow it (`allowed_actions` checks all but fresh MFA), so an independence or other
        # attribute refusal reads as itself.
        if action not in await allowed_actions(ctx, resource, [action]):
            raise
        raise RecordNeedsMfa(facts={"reason": "mfa_required"}) from None


def fresh_mfa_at(ctx: AuthContext) -> datetime:
    """The second factor's time the record stores (`authorise_record` has checked it)."""
    if ctx.mfa_at is None or _stale(ctx):
        raise RecordNeedsMfa(facts={"reason": "mfa_required"})
    return ctx.mfa_at
