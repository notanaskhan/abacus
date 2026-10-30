"""Retrieved records filed as client-scoped evidence (T-01-T43; T-01 §3.6; DEC-1651).

An IRS transcript a practitioner pulled from IRS e-Services under the 8821 on file and uploaded
is evidence the firm retrieved, not a client upload: filed under Files > Source documents for the
client (`folder_kind = 'source_documents'`, client scope) as a first version with `method =
'retrieved'`, channel `retrieval` and the time it was pulled, inside the caller's unit of work.
The file was screened and staged first (`screen_and_stage`: scanned before storage, fail closed).
The caller has authorised its own action (`transcript.upload`).

`pdf_text` reads a staged file's text for a pure parser: a PDF through the upload extractor in
its isolated child (active content is never read), plain text as UTF-8; anything else, or a PDF
the extractor could not read, is None and the caller records the parse as failed.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import insert

from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.evidence import storage
from abacus.modules.evidence.extraction import PDF, extract_isolated
from abacus.modules.evidence.models import EvidenceItem, EvidenceVersion

SOURCE_DOCUMENTS = "source_documents"
TEXT = "text/plain"


async def file_retrieved_copy(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    client_id: UUID,
    title: str,
    source: str,
    pulled_at: datetime,
    stored_key: str,
    stored_version_id: str,
    sha256: str,
    size_bytes: int,
    media_type: str,
    actor_id: str,
) -> UUID:
    """A new client-scoped Source documents item and its first, retrieved version; returns the
    version id."""
    stored = storage.StoredObject(stored_key, stored_version_id, sha256, size_bytes)
    if stored.key != storage.object_key(tenant_id, stored.fingerprint):
        raise storage.IntegrityError("staged content belongs to another tenant")
    item_id, version_id = uuid4(), uuid4()
    await tx.session.execute(
        insert(EvidenceItem).values(
            id=item_id,
            tenant_id=tenant_id,
            engagement_id=None,
            client_id=client_id,
            work_item_id=None,
            scope="client",
            folder_kind=SOURCE_DOCUMENTS,
            title=title,
            created_by_kind="human",
            created_by_id=actor_id,
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
            engagement_id=None,
            evidence_item_id=item_id,
            version_no=1,
            fingerprint=stored.fingerprint,
            storage_key=stored.key,
            storage_version_id=stored.version_id,
            size_bytes=stored.size,
            media_type=media_type,
            source=source,
            method="retrieved",
            pulled_at=pulled_at,
            channel="retrieval",
            display_name=title,
        )
    )
    tx.record(
        "evidence_version.created",
        target=Target("evidence_version", version_id),
        after=Ref(evidence_item_id=item_id, fingerprint=stored.fingerprint),
    )
    return version_id


def pdf_text(content: bytes, media_type: str) -> str | None:
    """The file's text for a pure parser, or None when it has none this reader can trust."""
    if media_type == TEXT:
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if media_type != PDF:
        return None
    extraction = extract_isolated(content, media_type)
    if extraction.status != "extracted":
        return None
    return "\n".join(extraction.pages)


__all__ = ["SOURCE_DOCUMENTS", "file_retrieved_copy", "pdf_text"]
