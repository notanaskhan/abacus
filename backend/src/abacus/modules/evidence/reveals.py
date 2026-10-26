"""The logged PII reveal (P-03-T16; SPEC-322 AC-26 to AC-29; C4 §3.5; DEC-52, DEC-60, DEC-370).
PROTECTED, red zone.

`reveal_pii` is the only path that opens a `pii_regions.value_sealed` envelope:
- **Who:** a live person serving their own request (never an agent, the system, a worker or a
  platform-support session: `serving_request()`, INV-1), not a client principal (403 before any
  read), who may see the version (404 otherwise) and holds `pii.reveal` on its engagement, which
  the matrix denies to offshore members (`not_offshore`), client roles, `client_service`, agents
  and the system, and requires independence and MFA within the window for. Every refusal happens
  before the region is read.
- **MFA:** a role that allows the reveal with MFA missing or older than the window answers 403
  `{"detail": "forbidden", "facts": {"reason": "mfa_required"}}`, so the shell steps up and
  retries (AC-27). The matrix requires it for every kind (DEC-370).
- **Limit:** at most `REVEAL_LIMIT` reveals per person per firm in a rolling hour, counted over
  `pii_reveals` under a per-person advisory lock (no Redis, DEC-16); the next answers 429
  `reveal_rate_limited` with `retry_after`, and is audited and counted (AC-29).
- **Record:** one `pii_reveals` row (`reason_code` `source_review`, the person, their MFA time,
  expiry 30 s on) and one `pii.revealed` audit event naming the person, with identifiers only,
  in the same unit of work; then a Q-02 `access_events` row (`pii.revealed`, flagged with the
  value's family) before the value leaves. **The value is never logged, audited, emitted or
  cached** (DEC-60); the route answers `Cache-Control: no-store`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import select, text

from abacus.kernel.access import AccessSubject, record_reads, register_access_kind
from abacus.kernel.clock import system_now
from abacus.kernel.crypto import open_sealed
from abacus.kernel.errors import DomainForbidden, DomainRateLimited, NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence.models import PiiRegion
from abacus.modules.evidence.pii import value_context
from abacus.modules.evidence.repository import current_derivation
from abacus.modules.evidence.viewer import visible_version
from abacus.modules.identity.api import (
    MFA_RECENT,
    AuthContext,
    Forbidden,
    authorise,
    names_of,
    serving_request,
)

REVEAL: Final = "pii.reveal"
# P-03 §4.3 and OQ-6 (SPEC-322 §8): twenty an hour per person, as the TIN reveal (DEC-232).
REVEAL_LIMIT: Final = 20
REVEAL_WINDOW_SECONDS: Final = 3600
EXPIRES_IN: Final = 30  # seconds the viewer shows the value (C4 §3.5)
REASON_CODE: Final = "source_review"
TIN_KINDS: Final = frozenset({"ssn", "itin", "ein"})
ACCESS_KIND: Final = "pii.revealed"
register_access_kind(ACCESS_KIND, ["restricted"])
_FLAGS: Final = {
    "ssn": "pii_tin",
    "itin": "pii_tin",
    "ein": "pii_tin",
    "bank_account": "pii_bank",
    "routing_number": "pii_bank",
    "dob": "pii_dob",
}

_reveals = meter(__name__).create_counter(
    "abacus.evidence.pii_reveals",
    unit="{reveal}",
    description="Logged PII reveals on the source viewer, by kind (never the region or value).",
)
_throttled = meter(__name__).create_counter(
    "abacus.evidence.pii_reveals_throttled",
    unit="{refusal}",
    description="PII reveals refused by the per-person hourly cap.",
)
_log = get_logger(__name__)


class RevealNeedsMfa(DomainForbidden):
    """Your role allows the reveal, but your last MFA is older than the window: verify again,
    then retry (the shell's step-up). Answers `facts.reason = mfa_required`."""

    code = "forbidden"


class RevealRateLimited(DomainRateLimited):
    """You have revealed the most values allowed in an hour: retry after `retry_after` seconds."""

    code = "reveal_rate_limited"


@dataclass(frozen=True)
class RevealedPii:
    mask_id: UUID
    value: str  # Restricted: returned once, `no-store`; never logged, stored or emitted
    kind: str
    expires_in: int
    revealed_by: str
    revealed_at: datetime


def _human(ctx: AuthContext) -> None:
    """INV-1: only a person, in a request they are making themself, never a support session."""
    if (
        not isinstance(ctx, AuthContext)  # pyright: ignore[reportUnnecessaryIsInstance] -- ADR-005 at runtime too
        or ctx.tenant.actor_kind != "human"
        or ctx.is_support
        or ctx.client
        or not serving_request()
    ):
        raise Forbidden(REVEAL, "role")


def _stale(mfa_at: datetime | None, now: datetime) -> bool:
    return mfa_at is None or now - mfa_at > MFA_RECENT


def shown(kind: str, value: str) -> str:
    """The value as the form prints it: `ddd-dd-dddd` for an SSN or ITIN and `dd-ddddddd` for an
    EIN held as nine digits; anything else as detected."""
    if kind in ("ssn", "itin") and len(value) == 9 and value.isdigit():
        return f"{value[:3]}-{value[3:5]}-{value[5:]}"
    if kind == "ein" and len(value) == 9 and value.isdigit():
        return f"{value[:2]}-{value[2:]}"
    return value


class _OverCap(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("over the hourly reveal cap")
        self.retry_after = retry_after


_LOCK_PERSON = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")
_RECENT = text(
    "SELECT count(*) AS n, min(revealed_at) AS oldest, clock_timestamp() AS now "
    "FROM pii_reveals WHERE user_id = :user "
    "AND revealed_at > clock_timestamp() - make_interval(secs => :window)"
)
# The only read of a sealed value (the model maps no `value_sealed`, P-03 §4.2).
_SEALED = text("SELECT value_sealed FROM pii_regions WHERE id = :id")
_INSERT = text(
    "INSERT INTO pii_reveals (tenant_id, region_id, evidence_version_id, user_id, reason_code, "
    "context_ref, mfa_at, expires_at) VALUES (:tenant, :region, :version, :user, :reason, "
    ":context, :mfa, clock_timestamp() + make_interval(secs => :expires)) "
    "RETURNING id, revealed_at"
)


async def reveal_pii(
    ctx: AuthContext, version_id: UUID, region_id: UUID, context_ref: str | None
) -> RevealedPii:
    """AC-26 to AC-29: the one call that returns a detected value in the clear."""
    _human(ctx)
    version = await visible_version(ctx, version_id)  # 403 client, 404 invisible or walled
    engagement = await get_ref(ctx, version.engagement_id)
    try:
        await authorise(ctx, REVEAL, engagement.resource())
    except Forbidden as refused:
        # The attribute layer comes after roles and conditions (offshore, independence): a
        # person refused there is allowed but for fresh MFA (or an archived engagement).
        if refused.layer == "attribute" and _stale(ctx.mfa_at, system_now()):
            raise RevealNeedsMfa(facts={"reason": "mfa_required"}) from None
        raise
    try:
        revealed, kind = await _reveal_once(ctx, version.id, engagement.id, region_id, context_ref)
    except _OverCap as over:
        await _record_throttle(ctx, version.id, engagement.id)
        raise RevealRateLimited(
            facts={"limit": REVEAL_LIMIT, "retry_after": over.retry_after}
        ) from None
    # Q-02: who saw which region, before the value leaves (an error here serves nothing).
    await record_reads(
        ctx.tenant,
        ACCESS_KIND,
        [
            AccessSubject(
                "pii_region",
                region_id,
                client_id=engagement.client_id,
                engagement_id=engagement.id,
            )
        ],
        flags=[_FLAGS.get(kind, "restricted")],
    )
    _reveals.add(1, {"kind": kind})
    return revealed


async def _reveal_once(
    ctx: AuthContext,
    version_id: UUID,
    engagement_id: UUID,
    region_id: UUID,
    context_ref: str | None,
) -> tuple[RevealedPii, str]:
    async with uow(ctx.tenant) as tx:
        # The version's own regions, or those of its current unlock (P-03-T19): the regions the
        # viewer's manifest shows.
        derivation = await current_derivation(tx.session, version_id)
        region = (
            await tx.session.execute(
                select(PiiRegion).where(
                    PiiRegion.id == region_id,
                    PiiRegion.evidence_version_id == version_id,
                    PiiRegion.derivation_id.is_(None)
                    if derivation is None
                    else PiiRegion.derivation_id == derivation.id,
                )
            )
        ).scalar_one_or_none()
        if region is None:
            raise NotFound("pii_region")
        # One person's reveals are counted one at a time, so parallel calls can't pass the cap.
        await tx.session.execute(
            _LOCK_PERSON, {"key": f"pii_reveal:{ctx.tenant_id}:{ctx.user_id}"}
        )
        recent = (
            await tx.session.execute(
                _RECENT, {"user": ctx.user_id, "window": REVEAL_WINDOW_SECONDS}
            )
        ).one()
        if int(recent.n) >= REVEAL_LIMIT:
            elapsed = (recent.now - recent.oldest).total_seconds()
            raise _OverCap(max(1, math.ceil(REVEAL_WINDOW_SECONDS - elapsed)))
        row = (
            await tx.session.execute(
                _INSERT,
                {
                    "tenant": ctx.tenant_id,
                    "region": region.id,
                    "version": version_id,
                    "user": ctx.user_id,
                    "reason": REASON_CODE,
                    "context": context_ref,
                    "mfa": ctx.mfa_at,
                    "expires": EXPIRES_IN,
                },
            )
        ).one()
        tx.record(
            "pii.revealed",
            target=Target("evidence_version", version_id),
            after=Ref(reveal_id=row.id, region_id=region.id),
            scope=Scope(engagement_id=engagement_id),
        )
        sealed = (await tx.session.execute(_SEALED, {"id": region.id})).scalar_one()
        plain = await open_sealed(ctx.tenant_id, bytes(sealed), value_context(region.id))
        kind = region.kind
    name = (await names_of([ctx.user_id])).get(ctx.user_id, "")
    return (
        RevealedPii(
            mask_id=region.id,
            value=shown(kind, plain.decode()),
            kind=kind,
            expires_in=EXPIRES_IN,
            revealed_by=name,
            revealed_at=row.revealed_at,
        ),
        kind,
    )


async def _record_throttle(ctx: AuthContext, version_id: UUID, engagement_id: UUID) -> None:
    """The security record of a refused reveal: an audit event in its own unit of work (the
    reveal's rolled back), a warning naming the person, and a counter. Identifiers only."""
    async with uow(ctx.tenant) as tx:
        tx.record(
            "pii.reveal_throttled",
            target=Target("evidence_version", version_id),
            after=Ref(limit=REVEAL_LIMIT),
            scope=Scope(engagement_id=engagement_id),
        )
    _throttled.add(1)
    _log.warning(
        "pii.reveal_throttled",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        evidence_version_id=version_id,
        limit=REVEAL_LIMIT,
    )


__all__ = [
    "EXPIRES_IN",
    "REVEAL_LIMIT",
    "TIN_KINDS",
    "RevealNeedsMfa",
    "RevealRateLimited",
    "RevealedPii",
    "reveal_pii",
    "shown",
]
