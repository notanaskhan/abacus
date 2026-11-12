"""Partner TINs: sealed at rest, masked in every payload, revealed only by a logged reveal
(T-05-T22; T-05 §4.2 M3; DEC-52, DEC-232, DEC-4404). Red zone (named in
`docs/architecture/protected-paths.md`).

- `seal_partner_tin` writes a partner's TIN on an entity return: an envelope under the firm's key
  (`kernel.crypto.seal`, bound to the partner), the last four digits and the kind, in the caller's
  unit of work, after `tax_ownership.edit` on the return's engagement (walled or unknown: 404). One
  `partner.updated` audit event names the field, never the value.
- Every payload carries only the last four (`MaskedTin`, Restricted, `pii_kind` tin).
- `reveal_partner_tin` is the only path that opens a partner's envelope: a live, onshore person
  with recent MFA and a reason code holding `tin.reveal` on the return's engagement (the matrix's
  `mfa_recent` and `not_offshore` conditions, enforced by `authorise`). One `partner_tin_reveals`
  row (with the reason) and one `partner_tin.revealed` audit event (its id, never the value) in
  the same unit of work; at most `REVEAL_LIMIT` partner reveals per person in a rolling hour
  (DEC-232's cap). The agent, the system and portal principals never reveal (matrix deny; INV-4).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainForbidden, DomainRateLimited, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise
from abacus.modules.organisations.api import (
    MaskedTin,
    RevealReason,
    TinKind,
    TinKindNotAllowed,
    normalise_tin,
)

EDIT: Final = "tax_ownership.edit"
REVEAL: Final = "tin.reveal"
REVEAL_LIMIT: Final = 20
REVEAL_WINDOW_SECONDS: Final = 3600
_KINDS: Final = frozenset({"ssn", "ein", "itin"})

_PARTNER = text(
    "SELECT p.engagement_id, p.work_item_id, p.tin_sealed, p.tin_kind, p.tin_last4 "
    "FROM partners p WHERE p.id = :id"
)
_WRITE = text(
    "UPDATE partners SET tin_sealed = :sealed, tin_last4 = :last4, tin_kind = :kind, "
    "updated_at = clock_timestamp() WHERE id = :id RETURNING id"
)
_LOCK_PERSON = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")
_RECENT = text(
    "SELECT count(*) AS n, min(revealed_at) AS oldest, clock_timestamp() AS now "
    "FROM partner_tin_reveals WHERE user_id = :user "
    "AND revealed_at > clock_timestamp() - make_interval(secs => :window)"
)
_RECORD = text(
    "INSERT INTO partner_tin_reveals (tenant_id, engagement_id, work_item_id, partner_id, "
    "user_id, reason_code, mfa_at) VALUES (:t, :e, :w, :p, :u, :reason, :mfa) RETURNING id"
)


class PartnerTinRevealNeedsMfa(DomainForbidden):
    """The role allows it but the second factor is missing or older than the matrix allows: the
    UI steps up and retries (DEC-232)."""

    code = "mfa_step_up_required"


class PartnerTinRevealRateLimited(DomainRateLimited):
    code = "tin_reveal_rate_limited"


@dataclass(frozen=True)
class RevealedPartnerTin:
    partner_id: UUID
    kind: TinKind
    value: str  # Restricted: returned once, `no-store`; never logged, stored or emitted
    reveal_id: UUID


@dataclass(frozen=True)
class _Partner:
    engagement_id: UUID
    work_item_id: UUID
    sealed: bytes | None
    kind: str | None
    last4: str | None


def _aad(partner_id: UUID) -> str:
    """The envelope opens only as this partner's TIN: a sealed value copied elsewhere won't."""
    return f"partner_tin:{partner_id}"


async def _partner(ctx: AuthContext, partner_id: UUID) -> _Partner:
    """The partner, seen through the caller's RLS; 404 for a portal principal (INV-4) or none."""
    if ctx.client:
        raise NotFound("partner")
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_PARTNER, {"id": partner_id})).first()
    if row is None:
        raise NotFound("partner")
    return _Partner(
        cast(UUID, row.engagement_id),
        cast(UUID, row.work_item_id),
        cast(bytes | None, row.tin_sealed),
        cast(str | None, row.tin_kind),
        cast(str | None, row.tin_last4),
    )


async def _engagement_resource(ctx: AuthContext, found: _Partner) -> Resource:
    engagement = await work_item_engagement(ctx.tenant, found.work_item_id)
    if engagement is None or engagement != found.engagement_id:
        raise NotFound("partner")
    ref = await get_ref(ctx, engagement)  # a wall answers 404 (DEC-43)
    return ref.resource()


async def seal_partner_tin(
    tx: UnitOfWork, ctx: AuthContext, partner_id: UUID, raw: str, kind: TinKind
) -> MaskedTin:
    """Seal and store `raw` as the partner's TIN in the caller's unit of work. 422 `tin_invalid`
    (never echoing the input); 422 `tin_kind_not_allowed` for an unknown kind."""
    if kind not in _KINDS:
        raise TinKindNotAllowed(facts={"partner_id": str(partner_id)})
    found = await _partner(ctx, partner_id)
    await authorise(ctx, EDIT, await _engagement_resource(ctx, found))
    digits = normalise_tin(raw)
    sealed = await seal(ctx.tenant_id, digits.encode(), _aad(partner_id))
    written = await tx.session.execute(
        _WRITE, {"sealed": sealed, "last4": digits[-4:], "kind": kind, "id": partner_id}
    )
    if written.scalar_one_or_none() is None:
        raise NotFound("partner")
    tx.record(
        "partner.updated",
        target=Target("partner", partner_id),
        after=Ref(tin=1),
        scope=Scope(engagement_id=found.engagement_id),
    )
    return MaskedTin(kind, digits[-4:])


def masked(kind: str | None, last4: str | None) -> MaskedTin | None:
    """What every payload but the reveal carries: the kind and the last four, or nothing."""
    if kind is None or last4 is None:
        return None
    return MaskedTin(cast(TinKind, kind), last4)


async def reveal_partner_tin(
    ctx: AuthContext, partner_id: UUID, reason: RevealReason
) -> RevealedPartnerTin:
    """The one call that returns a partner's plain TIN (module docstring). 404 walled, unknown or
    no TIN on file; 403 `mfa_step_up_required` when only the second factor is stale; 403 when the
    caller holds no `tin.reveal` (offshore, no role, the agent); 429 past the hourly cap."""
    found = await _partner(ctx, partner_id)
    resource = await _engagement_resource(ctx, found)
    if ctx.mfa_at is None:
        raise PartnerTinRevealNeedsMfa(facts={"partner_id": str(partner_id)})
    try:
        await authorise(ctx, REVEAL, resource, reason=reason)
    except Forbidden as refused:
        if refused.layer == "attribute":
            raise PartnerTinRevealNeedsMfa(facts={"partner_id": str(partner_id)}) from None
        raise
    if found.sealed is None or found.kind is None:
        raise NotFound("tin")
    mfa_at: datetime = ctx.mfa_at
    async with uow(ctx.tenant) as tx:
        # One person's reveals are counted one at a time, so parallel calls can't pass the cap.
        await tx.session.execute(
            _LOCK_PERSON, {"key": f"partner_tin_reveal:{ctx.tenant_id}:{ctx.user_id}"}
        )
        recent = (
            await tx.session.execute(
                _RECENT, {"user": ctx.user_id, "window": REVEAL_WINDOW_SECONDS}
            )
        ).one()
        if int(recent.n) >= REVEAL_LIMIT:
            elapsed = (recent.now - recent.oldest).total_seconds()
            raise PartnerTinRevealRateLimited(
                facts={
                    "limit": REVEAL_LIMIT,
                    "retry_after": max(1, math.ceil(REVEAL_WINDOW_SECONDS - elapsed)),
                }
            )
        reveal_id = cast(
            UUID,
            (
                await tx.session.execute(
                    _RECORD,
                    {
                        "t": ctx.tenant_id,
                        "e": found.engagement_id,
                        "w": found.work_item_id,
                        "p": partner_id,
                        "u": ctx.user_id,
                        "reason": reason,
                        "mfa": mfa_at,
                    },
                )
            ).scalar_one(),
        )
        tx.record(
            "partner_tin.revealed",
            target=Target("partner", partner_id),
            after=Ref(reveal_id=reveal_id),  # the reason code is on the reveal row
            scope=Scope(engagement_id=found.engagement_id),
        )
    value = (await open_sealed(ctx.tenant_id, found.sealed, _aad(partner_id))).decode()
    return RevealedPartnerTin(partner_id, cast(TinKind, found.kind), value, reveal_id)


__all__ = [
    "EDIT",
    "REVEAL",
    "REVEAL_LIMIT",
    "PartnerTinRevealNeedsMfa",
    "PartnerTinRevealRateLimited",
    "RevealedPartnerTin",
    "masked",
    "reveal_partner_tin",
    "seal_partner_tin",
]
