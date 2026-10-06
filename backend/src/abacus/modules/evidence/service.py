"""Evidence rules (ADR-004, ADR-016, ADR-104). PROTECTED. TASK-009 design §5, revision 1.

Two steps, so no transaction is held across network I/O:

    stored = await stage_content(tenant_id, content)        # before the unit of work
    async with uow(ctx) as tx:
        ref = await add_version(tx, engagement_id=…, item=NewItem("Trial balance"), stored=stored,
                                media_type=…, provenance=…, idempotency_key=…)

Versions are only ever added. Staged content that no version ends up referencing is harmless: it
is content-addressed and reused by the next attempt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from uuid import UUID, uuid4

from abacus.kernel.db import TenantContext, tenant_session, transaction_context
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.evidence import storage
from abacus.modules.evidence.events import EvidenceVersionCreated
from abacus.modules.evidence.models import EvidenceVersion
from abacus.modules.evidence.repository import (
    get_item,
    get_version,
    insert_item,
    insert_version,
    next_version_no,
    version_for_key,
)
from abacus.modules.identity.api import AuthContext, authorise

Method = Literal["retrieved", "uploaded"]
StoredObject = storage.StoredObject


class EngagementArchived(Exception):
    """Archived engagements are read-only (`archived_write: deny`)."""


@dataclass(frozen=True)
class Provenance:
    """Where a version came from (AC-10). `pulled_at` is required for retrieved evidence."""

    source: str
    method: Method
    pulled_at: datetime | None = None
    period_start: date | None = None
    period_end: date | None = None
    client_entity_id: UUID | None = None
    snapshot_id: UUID | None = None


@dataclass(frozen=True)
class NewItem:
    title: str


@dataclass(frozen=True)
class EvidenceVersionRef:
    id: UUID
    evidence_item_id: UUID
    engagement_id: UUID
    version_no: int
    fingerprint: str
    size_bytes: int
    media_type: str
    created: bool  # False when an idempotency key matched an existing version


def _ref(version: EvidenceVersion, *, created: bool) -> EvidenceVersionRef:
    return EvidenceVersionRef(
        version.id,
        version.evidence_item_id,
        version.engagement_id,
        version.version_no,
        version.fingerprint,
        version.size_bytes,
        version.media_type,
        created,
    )


async def stage_content(tenant_id: UUID, content: bytes) -> StoredObject:
    """Store content write-once and encrypted under the tenant's key, outside any transaction.
    Also the store for raw connector payloads (AC-9), which aren't evidence versions."""
    return await storage.put(tenant_id, content)


async def read_content(tenant: TenantContext, stored: StoredObject) -> bytes:
    """Verified plaintext for callers that authorised under their own context (the system actor
    in workflows). Request handlers use `read_version`, which authorises and audits."""
    return await storage.get(tenant.tenant_id, stored)


async def add_version(
    tx: UnitOfWork,
    *,
    engagement_id: UUID,
    item: UUID | NewItem,
    stored: StoredObject,
    media_type: str,
    provenance: Provenance,
    idempotency_key: str | None = None,
    requested_by: UUID | None = None,
) -> EvidenceVersionRef:
    """Add the next version inside the caller's unit of work. The tenant and actor are the
    transaction's own. The caller has authorised `evidence.upload` for its actor.

    With an `idempotency_key` already used in this tenant, returns that version
    (`created=False`) and records nothing: the caller's unit of work must then record its own
    event, or skip the unit of work after checking `created`. `requested_by` is the person the
    version is added for (published on `evidence_version.created`)."""
    tenant = await transaction_context(tx.session)
    if stored.key != storage.object_key(tenant.tenant_id, stored.fingerprint):
        raise storage.IntegrityError("staged content belongs to another tenant")
    if idempotency_key is not None:
        existing = await version_for_key(tx.session, idempotency_key)
        if existing is not None:
            if (
                existing.fingerprint != stored.fingerprint
                or existing.engagement_id != engagement_id
            ):
                raise ValueError("idempotency key reused for different content or engagement")
            return _ref(existing, created=False)
    engagement = await lock_ref(tx, engagement_id)  # 404 outside the tenant; locked until commit
    if engagement.archived:
        raise EngagementArchived("engagement is archived")
    if not 1 <= len(media_type) <= 100:
        raise ValueError("media_type must be 1-100 characters")
    if isinstance(item, NewItem):
        item_id = uuid4()
        await insert_item(
            tx.session,
            item_id=item_id,
            tenant_id=tenant.tenant_id,
            engagement_id=engagement_id,
            title=item.title,
            created_by_kind=tenant.actor_kind,
            created_by_id=tenant.actor_id,
        )
        tx.record(
            "evidence_item.created",
            target=Target("evidence_item", item_id),
            after=Ref(engagement_id=engagement_id),
        )
    else:
        existing_item = await get_item(tx.session, item)
        if existing_item is None or existing_item.engagement_id != engagement_id:
            raise NotFound("evidence_item")
        item_id = item
    version = await insert_version(
        tx.session,
        version_id=uuid4(),
        tenant_id=tenant.tenant_id,
        engagement_id=engagement_id,
        evidence_item_id=item_id,
        version_no=await next_version_no(tx.session, item_id),
        fingerprint=stored.fingerprint,
        storage_key=stored.key,
        storage_version_id=stored.version_id,
        size_bytes=stored.size,
        media_type=media_type,
        source=provenance.source,
        method=provenance.method,
        pulled_at=provenance.pulled_at,
        period_start=provenance.period_start,
        period_end=provenance.period_end,
        client_entity_id=provenance.client_entity_id,
        snapshot_id=provenance.snapshot_id,
        idempotency_key=idempotency_key,
    )
    tx.record(
        "evidence_version.created",
        target=Target("evidence_version", version.id),
        after=Ref(evidence_item_id=item_id, fingerprint=stored.fingerprint),
    )
    tx.emit(
        EvidenceVersionCreated(
            evidence_version_id=version.id,
            evidence_item_id=item_id,
            engagement_id=engagement_id,
            requested_by=requested_by,
        )
    )
    return _ref(version, created=True)


async def read_version(ctx: AuthContext, version_id: UUID) -> bytes:
    """The version's content for an actor allowed `evidence.read`: authorised, audited
    (`evidence_version.read`, ADR-104) and fingerprint-verified."""
    async with tenant_session(ctx.tenant) as session:
        version = await get_version(session, version_id)
    if version is None:
        raise NotFound("evidence_version")
    engagement = await get_ref(ctx, version.engagement_id)
    await authorise(ctx, "evidence.read", engagement.resource())
    async with uow(ctx.tenant) as tx:
        tx.record("evidence_version.read", target=Target("evidence_version", version.id))
    return await storage.get(
        ctx.tenant_id,
        StoredObject(
            version.storage_key,
            version.storage_version_id,
            version.fingerprint,
            version.size_bytes,
        ),
    )


@dataclass(frozen=True)
class EvidenceVersionView:
    id: UUID
    engagement_id: UUID
    evidence_item_id: UUID
    stored: StoredObject
    snapshot_id: UUID | None
    media_type: str
    period_start: date | None
    period_end: date | None


async def version_view(tenant: TenantContext, version_id: UUID) -> EvidenceVersionView:
    """A version's metadata for a caller that has authorised under its own context (`NotFound`
    outside the tenant)."""
    async with tenant_session(tenant) as session:
        version = await get_version(session, version_id)
    if version is None:
        raise NotFound("evidence_version")
    return EvidenceVersionView(
        version.id,
        version.engagement_id,
        version.evidence_item_id,
        StoredObject(
            version.storage_key,
            version.storage_version_id,
            version.fingerprint,
            version.size_bytes,
        ),
        version.snapshot_id,
        version.media_type,
        version.period_start,
        version.period_end,
    )
