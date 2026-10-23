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
import re
from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from abacus.kernel.config import settings
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound, ServiceUnavailable
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


class TinInvalid(DomainInvalid):
    """A taxpayer ID is nine digits (dashes and spaces aside), and not all zeros."""

    code = "tin_invalid"


class TinKindNotAllowed(DomainInvalid):
    """An SSN or ITIN can't be stored for a firm that isn't synthetic until the §7216 consent
    gate (C19) lands; an EIN can (P-07 OQ-4, DEC-52)."""

    code = "tin_kind_not_allowed"


class TinConflict(DomainConflict):
    """This taxpayer ID is already on file for another of the firm's entities."""

    code = "tin_conflict"


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


async def seal_tin(
    tx: UnitOfWork, tenant: TenantContext, entity_id: UUID, raw: str, kind: TinKind
) -> MaskedTin:
    """Seal and store `raw` as the entity's TIN, in the caller's unit of work, with one
    `client_entity.updated` audit event naming the field, never the value. 422 `tin_invalid`,
    422 `tin_kind_not_allowed`, 409 `tin_conflict`, 404 for an unknown entity."""
    digits = normalise_tin(raw)
    if kind in _GATED_KINDS and not await is_synthetic_firm(tenant):
        raise TinKindNotAllowed(facts={"client_entity_id": str(entity_id)})
    sealed = await seal(tenant.tenant_id, digits.encode(), _aad(entity_id))
    try:
        async with tx.session.begin_nested():
            written = await tx.session.execute(
                _WRITE,
                {
                    "sealed": sealed,
                    "last4": digits[-4:],
                    "kind": kind,
                    "fingerprint": fingerprint_tin(tenant.tenant_id, digits),
                    "id": entity_id,
                },
            )
            if written.scalar_one_or_none() is None:
                raise NotFound("client_entity")
    except IntegrityError:
        raise TinConflict(facts={"client_entity_id": str(entity_id)}) from None
    tx.record("client_entity.updated", target=Target("client_entity", entity_id), after=Ref(tin=1))
    return MaskedTin(kind, digits[-4:])


async def clear_tin(
    tx: UnitOfWork, entity_id: UUID, status: Literal["none", "applied_for"] = "none"
) -> None:
    """Remove the entity's TIN (or mark it applied for); the envelope goes with it."""
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
    caller (walls first, DEC-43) or no TIN is on file; 403 when no open engagement of the client
    gives the caller `tin.reveal` (offshore, no recent MFA, no role)."""
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
    allowed_on: UUID | None = None
    for resource in await _client_engagements(ctx, client_id):
        try:
            await authorise(ctx, REVEAL, resource, reason=reason)
        except Forbidden:
            continue
        allowed_on = resource.engagement_id
        break
    if allowed_on is None:
        raise Forbidden(REVEAL, "role")
    if ctx.mfa_at is None:  # authorise required recent MFA; the row records when
        raise Forbidden(REVEAL, "attribute")
    async with uow(ctx.tenant) as tx:
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
                    "mfa": ctx.mfa_at,
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


__all__ = [
    "MaskedTin",
    "RevealReason",
    "RevealedTin",
    "TinConflict",
    "TinInvalid",
    "TinKind",
    "TinKindNotAllowed",
    "clear_tin",
    "fingerprint_tin",
    "mask_tin",
    "may_reveal",
    "normalise_tin",
    "reveal_tin",
    "seal_tin",
]
