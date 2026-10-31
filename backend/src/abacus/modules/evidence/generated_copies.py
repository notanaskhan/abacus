"""Rendered documents filed as immutable evidence versions (P-11-T09; P-11 §4.2; C11 v1).

The renderer's bytes become an evidence version with channel `generated` inside the caller's
unit of work: the reporting module stores them first (`store_generated`: Object Lock, the
retention the document kind's record type sets), then records the version here, in the same
transaction as its `generated_document_files` row. The version's fingerprint is the render's
hash, checked here, so a PDF's evidence fingerprint equals its `render_hash` by construction and
no path writes other bytes under it. Evidence versions are insert-only (ADR-004): nothing here
updates or deletes, and a re-render is a new version.

An engagement-scoped document announces `evidence_version.created`, so the words, PII scan and
masked preview steps run as for uploads (SHL-08 opens its pages masked). A client-scoped one (a
consent) is filed under the client with no engagement, as retrieved copies are.

The method is `uploaded`, as generated exports already are (0270 maps their channel to
`generated`); the channel says where the bytes came from (DEC-1457).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import insert

from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.evidence import storage
from abacus.modules.evidence.events import EvidenceVersionCreated
from abacus.modules.evidence.models import EvidenceItem, EvidenceVersion

DELIVERABLES = "deliverables"
PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class RenderHashMismatch(storage.IntegrityError):
    """The stored bytes are not the render's: refused before any row is written."""


@dataclass(frozen=True)
class GeneratedFile:
    """What the renderer produced and the store kept."""

    stored: storage.StoredObject
    render_hash: str
    media_type: str
    title: str
    #: The provenance footer's facts (document kind, version, content hash): identifiers only.
    provenance: str


async def store_generated(
    tenant_id: UUID, content: bytes, *, retain_until: datetime | None = None
) -> storage.StoredObject:
    """Store rendered bytes under Object Lock before the unit of work that records them (as
    `storage.put` asks); the lock is never shorter than the record type's retention."""
    return await storage.put(tenant_id, content, retain_until=retain_until)


async def record_generated(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    client_id: UUID,
    engagement_id: UUID | None,
    work_item_id: UUID | None,
    file: GeneratedFile,
    requested_by: UUID | None,
) -> UUID:
    """A new Deliverables item and its first version, channel `generated`; returns the version
    id. The bytes must be the render's (fingerprint = render hash) and this tenant's."""
    stored = file.stored
    if stored.fingerprint != file.render_hash:
        raise RenderHashMismatch("stored bytes are not the render's")
    if stored.key != storage.object_key(tenant_id, stored.fingerprint):
        raise storage.IntegrityError("stored content belongs to another tenant")
    item_id, version_id = uuid4(), uuid4()
    await tx.session.execute(
        insert(EvidenceItem).values(
            id=item_id,
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            client_id=client_id,
            work_item_id=work_item_id,
            scope="engagement" if engagement_id is not None else "client",
            folder_kind=DELIVERABLES,
            title=file.title,
            created_by_kind="system",
            created_by_id="reporting.render",
        )
    )
    tx.record(
        "evidence_item.created",
        target=Target("evidence_item", item_id),
        after=Ref(client_id=client_id),
    )
    await tx.session.execute(
        insert(EvidenceVersion).values(
            id=version_id,
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            evidence_item_id=item_id,
            version_no=1,
            fingerprint=stored.fingerprint,
            storage_key=stored.key,
            storage_version_id=stored.version_id,
            size_bytes=stored.size,
            media_type=file.media_type,
            source=file.provenance,
            method="uploaded",
            channel="generated",
            display_name=file.title,
        )
    )
    tx.record(
        "evidence_version.created",
        target=Target("evidence_version", version_id),
        after=Ref(evidence_item_id=item_id, fingerprint=stored.fingerprint),
    )
    if engagement_id is not None:
        tx.emit(
            EvidenceVersionCreated(
                evidence_version_id=version_id,
                evidence_item_id=item_id,
                engagement_id=engagement_id,
                requested_by=requested_by,
            )
        )
    return version_id


__all__ = [
    "DOCX",
    "PDF",
    "GeneratedFile",
    "RenderHashMismatch",
    "record_generated",
    "store_generated",
]
