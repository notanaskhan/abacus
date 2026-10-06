"""Evidence rules (ADR-004, ADR-016, ADR-104). PROTECTED. TASK-009 design §5.

Versions are only ever added. The object is stored before the rows are written: it is
content-addressed, so an object left behind by a rolled-back transaction is harmless and is reused
by the next attempt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from uuid import UUID, uuid4

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence import storage
from abacus.modules.evidence.events import EvidenceVersionCreated
from abacus.modules.evidence.repository import (
    get_version,
    insert_item,
    insert_version,
    next_version_no,
)
from abacus.modules.identity.api import AuthContext, authorise

Method = Literal["retrieved", "uploaded"]


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


async def add_version(
    tx: UnitOfWork,
    tenant: TenantContext,
    *,
    engagement_id: UUID,
    item: UUID | NewItem,
    content: bytes,
    media_type: str,
    provenance: Provenance,
) -> EvidenceVersionRef:
    """Inside the caller's unit of work (opened with `tenant`); the caller has authorised
    `evidence.upload` for its actor (TASK-010: the system actor retrieving)."""
    stored = await storage.put(tenant.tenant_id, content)
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
    )
    tx.record(
        "evidence_version.created",
        target=Target("evidence_version", version.id),
        after=Ref(evidence_item_id=item_id, fingerprint=stored.fingerprint),
    )
    tx.emit(
        EvidenceVersionCreated(
            evidence_version_id=version.id, evidence_item_id=item_id, engagement_id=engagement_id
        )
    )
    return EvidenceVersionRef(
        version.id,
        item_id,
        engagement_id,
        version.version_no,
        version.fingerprint,
        version.size_bytes,
        version.media_type,
    )


async def read_version(ctx: AuthContext, version_id: UUID) -> bytes:
    """The version's content, decrypted and verified, for an actor allowed `evidence.read`."""
    async with tenant_session(ctx.tenant) as session:
        version = await get_version(session, version_id)
    if version is None:
        raise NotFound("evidence_version")
    engagement = await get_ref(ctx, version.engagement_id)
    await authorise(ctx, "evidence.read", engagement.resource())
    return await storage.get(
        ctx.tenant_id,
        storage.StoredObject(
            version.storage_key,
            version.storage_version_id,
            version.fingerprint,
            version.size_bytes,
        ),
    )
