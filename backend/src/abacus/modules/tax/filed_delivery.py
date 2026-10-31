"""Filed-return delivery to the client (T-01-T41; T-01 §3.14; TAX-12 d; DEC-1571). AMBER.

- **Publish** (`deliverable.publish`, client service or a manager on the return, a person): once
  the return is Accepted and its delivery packet approved, the packet's client copy (the engine's
  `client_copy` PDF, an evidence version) is released to the household's portal scope: one
  insert-only `filed_return_deliveries` row (0526), `return.delivered` audited (human-only) and
  announced. Publishing again is the same release.
- **Portal home** (`portal/home_sources/tax_filings.py`): an Earlier row "2025 Form 1040 filed and
  accepted" per released return among the work items the home already authorised for the scope
  (`scope_only`, INV-4), with its download.
- **Download**: a client person whose grant covers the return (`portal_home.read` on it; anyone
  else 404), with the portal's second step (TRI, 403 `mfa_required`); the bytes are the evidence
  version's, fingerprint-verified, and every download is audited `filed_return.downloaded`.
- **C10**: when R-02's deliverables registry lands, each release is registered there by its id
  (the row keeps the engagement, client, return and version it needs).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Annotated, Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainForbidden, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, uow
from abacus.modules.engagements.api import get_ref, work_item_facts
from abacus.modules.evidence.api import version_content
from abacus.modules.identity.api import AuthContext, Forbidden, authorise, engagement_resource
from abacus.modules.tax.filing import PacketNotApproved

TARGET: Final = "tax_return"
PUBLISH: Final = "deliverable.publish"
PORTAL_READ: Final = "portal_home.read"
CLIENT_COPY: Final = "client_copy"


class ReturnNotAccepted(DomainConflict):
    code = "return_not_accepted"


class NoClientCopy(DomainConflict):
    code = "no_client_copy"


class MfaRequired(DomainForbidden):
    """403: the portal's second step first (the client copy is TRI)."""

    code = "mfa_required"


class ReturnDelivered(DomainEvent):
    """The filed client copy reached the client's portal (identifiers only)."""

    event_type = "return.delivered"
    return_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    delivery_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


@dataclass(frozen=True)
class Delivered:
    id: UUID
    return_id: UUID
    published_at: datetime


@dataclass(frozen=True)
class FiledReturn:
    delivery_id: UUID
    return_id: UUID
    tax_year: int
    form: str
    delivered_on: date


@dataclass(frozen=True)
class ClientCopy:
    file_name: str
    content: bytes


def _client_copy_of(items: object) -> UUID | None:
    raw = json.loads(items) if isinstance(items, str) else items
    for item in cast(list[dict[str, object]], raw or []):
        version = item.get("evidence_version_id")
        if item.get("kind") == CLIENT_COPY and item.get("included") is not False and version:
            return UUID(str(version))
    return None


async def publish(ctx: AuthContext, return_id: UUID) -> Delivered:
    """Release the accepted return's client copy to the household (TAX-12 d)."""
    if ctx.client:
        raise NotFound(TARGET)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(PUBLISH, "role")
    item = next(
        (
            i
            for i in await work_item_facts(ctx, TARGET, "tax_return.read_metadata")
            if i.work_item_id == return_id
        ),
        None,
    )
    if item is None:
        raise NotFound(TARGET)
    resource = replace(
        await engagement_resource(ctx.tenant, item.engagement_id),
        client_id=item.client_id,
        work_item_id=return_id,
    )
    await authorise(ctx, PUBLISH, resource)
    async with tenant_session(ctx.tenant) as session:
        status = await session.scalar(
            text("SELECT status FROM tax_returns WHERE work_item_id = :r"), {"r": return_id}
        )
        packet = (
            await session.execute(
                text(
                    "SELECT id, items FROM delivery_packets WHERE return_id = :r "
                    "AND status = 'approved' ORDER BY version DESC LIMIT 1"
                ),
                {"r": return_id},
            )
        ).first()
    if status != "accepted":
        raise ReturnNotAccepted(facts={"work_item_id": str(return_id)})
    if packet is None:
        raise PacketNotApproved(facts={"work_item_id": str(return_id)})
    version_id = _client_copy_of(packet[1])
    if version_id is None:
        raise NoClientCopy(facts={"work_item_id": str(return_id)})
    async with uow(ctx.tenant) as tx:
        row = (
            await tx.session.execute(
                text(
                    "INSERT INTO filed_return_deliveries (tenant_id, return_id, engagement_id, "
                    "client_id, packet_id, evidence_version_id, published_by, actor_kind) "
                    "VALUES (:t, :r, :e, :c, :p, :v, :u, :kind) ON CONFLICT DO NOTHING "
                    "RETURNING id, published_at"
                ),
                {
                    "t": ctx.tenant_id,
                    "r": return_id,
                    "e": item.engagement_id,
                    "c": item.client_id,
                    "p": packet[0],
                    "v": version_id,
                    "u": ctx.user_id,
                    "kind": ctx.tenant.actor_kind,
                },
            )
        ).first()
        if row is None:  # released before: the same release
            row = (
                await tx.session.execute(
                    text(
                        "SELECT id, published_at FROM filed_return_deliveries "
                        "WHERE return_id = :r AND evidence_version_id = :v"
                    ),
                    {"r": return_id, "v": version_id},
                )
            ).one()
        tx.record(
            "return.delivered",
            target=Target(TARGET, return_id),
            after=Ref(delivery=cast(UUID, row[0]), evidence_version=version_id),
            scope=Scope(engagement_id=item.engagement_id, client_id=item.client_id),
        )
        tx.emit(
            ReturnDelivered(
                return_id=return_id,
                engagement_id=item.engagement_id,
                client_id=item.client_id,
                delivery_id=cast(UUID, row[0]),
                by_user=ctx.user_id,
            )
        )
    return Delivered(cast(UUID, row[0]), return_id, cast(datetime, row[1]))


async def filed_returns(tenant: TenantContext, return_ids: list[UUID]) -> list[FiledReturn]:
    """The released, accepted returns among `return_ids` (work items the caller's home already
    authorised for its scope), newest first."""
    if not return_ids:
        return []
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT DISTINCT ON (d.return_id) d.id, d.return_id, r.tax_year, r.form, "
                    "d.published_at FROM filed_return_deliveries d JOIN tax_returns r "
                    "ON r.work_item_id = d.return_id WHERE d.return_id = ANY(:ids) "
                    "AND r.status = 'accepted' ORDER BY d.return_id, d.published_at DESC"
                ),
                {"ids": return_ids},
            )
        ).all()
    found = [
        FiledReturn(
            cast(UUID, r[0]),
            cast(UUID, r[1]),
            int(r[2]),
            str(r[3]),
            cast(datetime, r[4]).date(),
        )
        for r in rows
    ]
    return sorted(found, key=lambda f: (f.tax_year, f.delivered_on), reverse=True)


async def client_copy(ctx: AuthContext, delivery_id: UUID) -> ClientCopy:
    """A client person's download of a released client copy (audited each time)."""
    if not ctx.client:
        raise NotFound("filed_return")
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT d.return_id, d.engagement_id, d.evidence_version_id, r.tax_year, "
                    "r.form, r.status FROM filed_return_deliveries d JOIN tax_returns r "
                    "ON r.work_item_id = d.return_id WHERE d.id = :d"
                ),
                {"d": delivery_id},
            )
        ).first()
    if row is None or row[5] != "accepted":
        raise NotFound("filed_return")
    return_id, engagement_id, version_id = (
        cast(UUID, row[0]),
        cast(UUID, row[1]),
        cast(UUID, row[2]),
    )
    try:
        resource = replace((await get_ref(ctx, engagement_id)).resource(), work_item_id=return_id)
        await authorise(ctx, PORTAL_READ, resource)
    except (Forbidden, NotFound):
        raise NotFound("filed_return") from None  # another scope's return does not exist (INV-4)
    if ctx.mfa_at is None and not ctx.portal_second_step:
        raise MfaRequired
    content = await version_content(ctx.tenant, version_id)
    async with uow(ctx.tenant) as tx:
        tx.record(
            "filed_return.downloaded",
            target=Target(TARGET, return_id),
            after=Ref(delivery=delivery_id, evidence_version=version_id),
        )
    return ClientCopy(f"{int(row[3])} Form {row[4]} client copy.pdf", content)


__all__ = [
    "ClientCopy",
    "Delivered",
    "FiledReturn",
    "MfaRequired",
    "NoClientCopy",
    "ReturnDelivered",
    "ReturnNotAccepted",
    "client_copy",
    "filed_returns",
    "publish",
]
