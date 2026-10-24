"""Taxpayer IDs: sealed at rest, masked in every payload, revealed only by a logged reveal
(P-07-T10; DEC-52, DEC-141, DEC-223). Red zone.

- `seal_tin` writes a client entity's TIN: an envelope under the firm's key (`kernel.crypto.seal`,
  bound to the entity), the last four digits, the kind and a fingerprint (HMAC-SHA256 under a
  per-firm key) that keeps one TIN on file once per firm. An SSN or ITIN on a firm that is not
  synthetic answers 422 `tin_kind_not_allowed` until C19's consent gate lands; an EIN is
  accepted (P-07 OQ-4).
- Every payload carries only `mask_tin`'s last four digits (`MaskedTinOut`, Restricted).
- `reveal_tin` is the only path that opens an envelope: a live, onshore person with recent MFA,
  a reason code and `tin.reveal` on one of the client's open engagements. One `tin_reveals` row
  and one `tin.revealed` audit event (the reason via the row, never the value) are written in the
  same unit of work, and a counter counts reveals by reason. Nothing here logs a value.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.config import settings
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import (
    DomainConflict,
    DomainForbidden,
    DomainInvalid,
    DomainRateLimited,
    NotFound,
    ServiceUnavailable,
)
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
    is_synthetic_firm,
    visible_clients,
)
from abacus.modules.organisations.models import Client, ClientEntity
from abacus.modules.organisations.slots import fact_query

TinKind = Literal["ssn", "ein", "itin"]
RevealReason = Literal[
    "prepare_return",
    "review_return",
    "file_or_correct_filing",
    "respond_to_notice",
    "verify_identity",
]
REVEAL: Final = "tin.reveal"
# DEC-232: at most this many reveals per person per firm in a rolling hour. A preparer working a
# household's returns or a notice reveals a handful; twenty an hour covers a busy afternoon of
# e-file corrections and bounds what one stolen session can read to twenty TINs an hour.
REVEAL_LIMIT: Final = 20
REVEAL_WINDOW_SECONDS: Final = 3600
_UNIQUE_VIOLATION: Final = "23505"
_TIN_UNIQUE_INDEX: Final = "client_entities_one_tin"
WriteAction = Literal["client.update", "client.intake"]
# Until C19 (T-01) gates §7216 consent, only a synthetic firm may hold an individual's TIN.
_GATED_KINDS: Final = frozenset({"ssn", "itin"})
_SEPARATORS: Final = re.compile(r"[\s-]")
_NINE: Final = re.compile(r"[0-9]{9}")
# Public, like the local master key: it fingerprints only data on this machine (DEC-223).
_LOCAL_PEPPER: Final = b"abacus-local-tin-fingerprint-pepper"

_reveals = meter(__name__).create_counter(
    "abacus.organisations.tin_reveals",
    unit="{reveal}",
    description="Logged TIN reveals, by reason code (never the entity or the value).",
)
_throttled = meter(__name__).create_counter(
    "abacus.organisations.tin_reveals_throttled",
    unit="{refusal}",
    description="TIN reveals refused by the per-person hourly cap, by reason code.",
)
_log = get_logger(__name__)


class TinInvalid(DomainInvalid):
    """A taxpayer ID is nine digits (dashes and spaces aside), and not all zeros."""

    code = "tin_invalid"


class TinKindNotAllowed(DomainInvalid):
    """An SSN or ITIN can't be stored for a firm that isn't synthetic until the §7216 consent
    gate (C19) lands; an EIN can (P-07 OQ-4, DEC-52)."""

    code = "tin_kind_not_allowed"


class TinConflict(DomainConflict):
    """This taxpayer ID can't be stored for this entity. Generic on purpose: it never says
    which entity, or whose client, holds it (DEC-232)."""

    code = "tin_conflict"


class TinRevealNeedsMfa(DomainForbidden):
    """Your role allows the reveal, but your last MFA is older than 15 minutes: verify again,
    then retry (the UI's step-up)."""

    code = "mfa_step_up_required"


class TinRevealRateLimited(DomainRateLimited):
    """You have revealed the most TINs allowed in an hour: retry after `retry_after` seconds."""

    code = "tin_reveal_rate_limited"


def normalise_tin(raw: str) -> str:
    """The nine digits of `raw`, or 422 `tin_invalid`. Never echoes the input."""
    digits = _SEPARATORS.sub("", raw)
    if not _NINE.fullmatch(digits) or digits == "000000000":
        raise TinInvalid
    return digits


def mask_tin(kind: str, last4: str) -> str:
    """The display form every payload but the reveal may carry: `XX-XXX1234`, `•••-••-1234`."""
    return f"XX-XXX{last4}" if kind == "ein" else f"•••-••-{last4}"


def _pepper() -> bytes:
    configured = settings().tin_fingerprint_pepper
    if configured is not None:
        return configured.get_secret_value().encode()
    if settings().environment in ("local", "test"):
        return _LOCAL_PEPPER
    raise ServiceUnavailable("TIN fingerprinting is not configured")


def fingerprint_tin(tenant_id: UUID, digits: str) -> bytes:
    """HMAC-SHA256 of the digits under the firm's own fingerprint key (derived from the pepper
    and the tenant ID), so two firms' fingerprints of one TIN never match."""
    firm_key = hmac.new(
        _pepper(), b"abacus-tin-fingerprint-v1|" + tenant_id.bytes, hashlib.sha256
    ).digest()
    return hmac.new(firm_key, digits.encode(), hashlib.sha256).digest()


def _aad(entity_id: UUID) -> str:
    """The envelope opens only as this entity's TIN: a sealed value copied elsewhere won't."""
    return f"client_entity_tin:{entity_id}"


@dataclass(frozen=True)
class MaskedTin:
    kind: TinKind
    last4: str


_WRITE = text(
    "UPDATE client_entities SET tin_sealed = :sealed, tin_last4 = :last4, tin_kind = :kind, "
    "tin_status = 'on_file', tin_fingerprint = :fingerprint WHERE id = :id RETURNING id"
)
_CLEAR = text(
    "UPDATE client_entities SET tin_sealed = NULL, tin_last4 = NULL, tin_kind = NULL, "
    "tin_status = :status, tin_fingerprint = NULL WHERE id = :id RETURNING id"
)
_SEALED = text("SELECT tin_sealed, tin_kind FROM client_entities WHERE id = :id")


async def _writable_entity(
    session: AsyncSession, ctx: AuthContext, entity_id: UUID, action: WriteAction
) -> UUID:
    """The entity's client, after `action` is authorised on it. A walled or unknown entity is
    404 before anything is touched, so a write can't tell a wall from a missing entity."""
    seen = await visible_clients(ctx, "client.read", Client.id)
    client_id = (
        await session.execute(
            select(ClientEntity.client_id)
            .join(Client, Client.id == ClientEntity.client_id)
            .where(ClientEntity.id == entity_id, seen)
        )
    ).scalar_one_or_none()
    if client_id is None:
        raise NotFound("client_entity")
    try:
        await authorise(ctx, action, Resource.client(ctx.tenant_id, client_id))
    except Forbidden as denied:
        if denied.layer == "wall":
            raise NotFound("client_entity") from None
        raise
    return client_id


def _is_tin_duplicate(exc: IntegrityError) -> bool:
    orig = exc.orig
    cause = getattr(orig, "__cause__", None)
    constraint = getattr(orig, "constraint_name", None) or getattr(cause, "constraint_name", None)
    return getattr(orig, "sqlstate", None) == _UNIQUE_VIOLATION and constraint in (
        _TIN_UNIQUE_INDEX,
        None,
    )


async def seal_tin(
    tx: UnitOfWork,
    ctx: AuthContext,
    entity_id: UUID,
    raw: str,
    kind: TinKind,
    *,
    action: WriteAction = "client.update",
) -> MaskedTin:
    """Seal and store `raw` as the entity's TIN, in the caller's unit of work, with one
    `client_entity.updated` audit event naming the field, never the value. `action` is
    authorised on the entity's client first (walled or unknown: 404). 422 `tin_invalid`, 422
    `tin_kind_not_allowed`, 409 `tin_conflict` (generic). Any other integrity failure is raised
    as it is, never read as a conflict (DEC-232)."""
    await _writable_entity(tx.session, ctx, entity_id, action)
    digits = normalise_tin(raw)
    if kind in _GATED_KINDS and not await is_synthetic_firm(ctx.tenant):
        raise TinKindNotAllowed(facts={"client_entity_id": str(entity_id)})
    sealed = await seal(ctx.tenant_id, digits.encode(), _aad(entity_id))
    try:
        async with tx.session.begin_nested():
            written = await tx.session.execute(
                _WRITE,
                {
                    "sealed": sealed,
                    "last4": digits[-4:],
                    "kind": kind,
                    "fingerprint": fingerprint_tin(ctx.tenant_id, digits),
                    "id": entity_id,
                },
            )
            if written.scalar_one_or_none() is None:
                raise NotFound("client_entity")
    except IntegrityError as exc:
        if _is_tin_duplicate(exc):
            raise TinConflict from None
        raise
    tx.record("client_entity.updated", target=Target("client_entity", entity_id), after=Ref(tin=1))
    return MaskedTin(kind, digits[-4:])


async def clear_tin(
    tx: UnitOfWork,
    ctx: AuthContext,
    entity_id: UUID,
    status: Literal["none", "applied_for"] = "none",
    *,
    action: WriteAction = "client.update",
) -> None:
    """Remove the entity's TIN (or mark it applied for); the envelope goes with it. Authorised as
    `seal_tin` is."""
    await _writable_entity(tx.session, ctx, entity_id, action)
    cleared = await tx.session.execute(_CLEAR, {"status": status, "id": entity_id})
    if cleared.scalar_one_or_none() is None:
        raise NotFound("client_entity")
    tx.record("client_entity.updated", target=Target("client_entity", entity_id), after=Ref(tin=0))


# --- the reveal ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class RevealedTin:
    entity_id: UUID
    kind: TinKind
    value: str  # Restricted: returned once, `no-store`; never logged, stored or emitted
    reveal_id: UUID


async def _client_engagements(ctx: AuthContext, client_id: UUID) -> list[Resource]:
    """The client's open engagements as resources (registered by engagements; none when
    unregistered), each with its own archived state from the row."""
    query = fact_query("engagements")
    if query is None:
        return []
    facts = query.subquery("client_engagements")
    async with tenant_session(ctx.tenant) as session:
        rows = await session.execute(
            select(facts.c.engagement_id, facts.c.status)
            .where(facts.c.client_id == client_id)
            .order_by(facts.c.engagement_id)
        )
        return [
            Resource.engagement(
                ctx.tenant_id, engagement_id, archived=status == "archived", client_id=client_id
            )
            for engagement_id, status in rows.all()
        ]


async def may_reveal(ctx: AuthContext, client_id: UUID) -> bool:
    """Whether the caller could reveal a TIN of this client (every layer but fresh MFA and a
    reason, which the UI steps up to): CLI-02's `allowed_actions`."""
    for resource in await _client_engagements(ctx, client_id):
        if REVEAL in await allowed_actions(ctx, resource, (REVEAL,)):
            return True
    return False


async def reveal_tin(ctx: AuthContext, entity_id: UUID, reason: RevealReason) -> RevealedTin:
    """The one call that returns a plain TIN. 404 when the entity's client isn't visible to the
    caller (walls first, DEC-43) or no TIN is on file; 403 `mfa_step_up_required` when a role
    allows it but MFA is missing or older than 15 minutes (the UI steps up); a plain 403 when no
    open engagement of the client gives the caller `tin.reveal` (offshore, no role); 429
    `tin_reveal_rate_limited` past `REVEAL_LIMIT` reveals in a rolling hour (DEC-232)."""
    async with tenant_session(ctx.tenant) as session:
        seen = await visible_clients(ctx, "client.read", Client.id)
        client_id = (
            await session.execute(
                select(ClientEntity.client_id)
                .join(Client, Client.id == ClientEntity.client_id)
                .where(ClientEntity.id == entity_id, seen)
            )
        ).scalar_one_or_none()
    if client_id is None:
        raise NotFound("client_entity")
    mfa_at = ctx.mfa_at
    if mfa_at is None:  # no MFA in this session at all: step up before any check
        raise TinRevealNeedsMfa(facts={"client_entity_id": str(entity_id)})
    allowed_on: UUID | None = None
    denied: Forbidden | None = None
    for resource in await _client_engagements(ctx, client_id):
        try:
            await authorise(ctx, REVEAL, resource, reason=reason)
        except Forbidden as refused:
            # Keep the attribute layer (stale MFA) over a role or condition denial elsewhere:
            # the role allowed it, so the person can step up and retry (DEC-232).
            if denied is None or refused.layer == "attribute":
                denied = refused
            continue
        allowed_on = resource.engagement_id
        break
    if allowed_on is None:
        if denied is not None and denied.layer == "attribute":
            raise TinRevealNeedsMfa(facts={"client_entity_id": str(entity_id)})
        raise denied or Forbidden(REVEAL, "relationship")
    try:
        return await _reveal_once(ctx, entity_id, reason, allowed_on, mfa_at)
    except _OverCap as over:
        await _record_throttle(ctx, entity_id, reason, allowed_on)
        raise TinRevealRateLimited(
            facts={"limit": REVEAL_LIMIT, "retry_after": over.retry_after}
        ) from None


class _OverCap(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("over the hourly reveal cap")
        self.retry_after = retry_after


_LOCK_PERSON = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")
_RECENT = text(
    "SELECT count(*) AS n, min(revealed_at) AS oldest, clock_timestamp() AS now "
    "FROM tin_reveals WHERE user_id = :user "
    "AND revealed_at > clock_timestamp() - make_interval(secs => :window)"
)


async def _reveal_once(
    ctx: AuthContext, entity_id: UUID, reason: RevealReason, allowed_on: UUID, mfa_at: datetime
) -> RevealedTin:
    async with uow(ctx.tenant) as tx:
        # One person's reveals are counted one at a time, so parallel calls can't pass the cap.
        await tx.session.execute(
            _LOCK_PERSON, {"key": f"tin_reveal:{ctx.tenant_id}:{ctx.user_id}"}
        )
        recent = (
            await tx.session.execute(
                _RECENT, {"user": ctx.user_id, "window": REVEAL_WINDOW_SECONDS}
            )
        ).one()
        if int(recent.n) >= REVEAL_LIMIT:
            elapsed = (recent.now - recent.oldest).total_seconds()
            raise _OverCap(max(1, math.ceil(REVEAL_WINDOW_SECONDS - elapsed)))
        found = (await tx.session.execute(_SEALED, {"id": entity_id})).one_or_none()
        if found is None or found.tin_sealed is None:
            raise NotFound("tin")
        reveal_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO tin_reveals (tenant_id, client_entity_id, engagement_id, "
                    "user_id, reason_code, mfa_at) VALUES (:tenant, :entity, :engagement, "
                    ":user, :reason, :mfa) RETURNING id"
                ),
                {
                    "tenant": ctx.tenant_id,
                    "entity": entity_id,
                    "engagement": allowed_on,
                    "user": ctx.user_id,
                    "reason": reason,
                    "mfa": mfa_at,
                },
            )
        ).scalar_one()
        tx.record(
            "tin.revealed",
            target=Target("client_entity", entity_id),
            after=Ref(reveal_id=reveal_id),
            scope=Scope(engagement_id=allowed_on),
        )
        plain = await open_sealed(ctx.tenant_id, bytes(found.tin_sealed), _aad(entity_id))
        kind: TinKind = found.tin_kind
    _reveals.add(1, {"reason": reason})
    return RevealedTin(entity_id, kind, plain.decode(), reveal_id)


async def _record_throttle(
    ctx: AuthContext, entity_id: UUID, reason: RevealReason, engagement_id: UUID
) -> None:
    """The security record of a refused reveal: an audit event in its own unit of work (the
    reveal's rolled back), a warning log naming the person and the reason, and a counter by
    reason. Identifiers and codes only; never the TIN."""
    async with uow(ctx.tenant) as tx:
        tx.record(
            "tin.reveal_throttled",
            target=Target("client_entity", entity_id),
            after=Ref(limit=REVEAL_LIMIT),
            scope=Scope(engagement_id=engagement_id),
        )
    _throttled.add(1, {"reason": reason})
    _log.warning(
        "tin.reveal_throttled",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        client_entity_id=entity_id,
        reason=reason,
        limit=REVEAL_LIMIT,
    )


__all__ = [
    "REVEAL_LIMIT",
    "MaskedTin",
    "RevealReason",
    "RevealedTin",
    "TinConflict",
    "TinInvalid",
    "TinKind",
    "TinKindNotAllowed",
    "TinRevealNeedsMfa",
    "TinRevealRateLimited",
    "clear_tin",
    "fingerprint_tin",
    "mask_tin",
    "may_reveal",
    "normalise_tin",
    "reveal_tin",
    "seal_tin",
]
