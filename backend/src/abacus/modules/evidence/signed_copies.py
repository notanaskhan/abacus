"""Signed copies filed as client-scoped evidence (N-02-T08; N-02 §3.1; ADR-158, P-40).

Record-mode import (signatures) hands evidence two things: a file to screen and stage, and the
completed document to file under Files > work item > Signed authorizations. Screening is the
upload path's (`uploads.checked`: scanned before anything stores it, type from the bytes, fail
closed). Filing writes a new item (`folder_kind = 'signed_authorizations'`, client scope when no
engagement is named) and its first version (`method = 'imported'`, channel `import`), inside the
caller's unit of work. The caller has authorised its own action (`envelope.import_record`).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.clock import system_now
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.evidence import storage
from abacus.modules.evidence.models import EvidenceItem, EvidenceVersion
from abacus.modules.evidence.uploads import checked, clean_name
from abacus.modules.platform.api import StoredFile

SIGNED_AUTHORIZATIONS = "signed_authorizations"


@dataclass(frozen=True)
class ScreenedFile:
    file_name: str
    media_type: str
    sha256: str
    stored: storage.StoredObject


async def screen_and_stage(
    tenant_id: UUID, content: bytes, file_name: str, retain_until: datetime | None
) -> ScreenedFile:
    """Scan, type and store one file (SPEC-029 AC-1): a refused file raises `UploadRefused` and
    nothing is stored; a scanner outage raises and nothing is stored."""
    media_type, digest = await asyncio.to_thread(checked, content, file_name)
    stored = await storage.put(tenant_id, content, retain_until=retain_until)
    return ScreenedFile(clean_name(file_name), media_type, digest, stored)


async def screen_for_store(tenant_id: UUID, content: bytes, file_name: str) -> StoredFile:
    """`screen_and_stage` as the platform file store's screen (K-01-T18; DEC-1759)."""
    screened = await screen_and_stage(tenant_id, content, file_name, None)
    return StoredFile(
        file_name=screened.file_name,
        media_type=screened.media_type,
        sha256=screened.sha256,
        key=screened.stored.key,
        version_id=screened.stored.version_id,
    )


async def read_staged(
    tenant_id: UUID, stored_key: str, stored_version_id: str, sha256: str, size_bytes: int
) -> bytes:
    """A staged file's verified plaintext, for a caller that authorised its own action and holds
    the file's row (fingerprint-checked by `storage.get`)."""
    return await storage.get(
        tenant_id, storage.StoredObject(stored_key, stored_version_id, sha256, size_bytes)
    )


async def file_signed_copy(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    client_id: UUID,
    engagement_id: UUID | None,
    work_item_id: UUID | None,
    title: str,
    stored_key: str,
    stored_version_id: str,
    sha256: str,
    size_bytes: int,
    media_type: str,
    actor_kind: str,
    actor_id: str,
) -> UUID:
    """A new Signed authorizations item and its first version; returns the version id."""
    stored = storage.StoredObject(stored_key, stored_version_id, sha256, size_bytes)
    if stored.key != storage.object_key(tenant_id, stored.fingerprint):
        raise storage.IntegrityError("staged content belongs to another tenant")
    item_id, version_id = uuid4(), uuid4()
    await tx.session.execute(
        insert(EvidenceItem).values(
            id=item_id,
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            client_id=client_id,
            work_item_id=work_item_id,
            scope="engagement" if engagement_id is not None else "client",
            folder_kind=SIGNED_AUTHORIZATIONS,
            title=title,
            created_by_kind=actor_kind,
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
            engagement_id=engagement_id,
            evidence_item_id=item_id,
            version_no=1,
            fingerprint=stored.fingerprint,
            storage_key=stored.key,
            storage_version_id=stored.version_id,
            size_bytes=stored.size,
            media_type=media_type,
            source="signature_import",
            method="imported",
            pulled_at=system_now(),  # an imported version records when it came in (0041)
            channel="import",
            display_name=title,
        )
    )
    tx.record(
        "evidence_version.created",
        target=Target("evidence_version", version_id),
        after=Ref(evidence_item_id=item_id, fingerprint=stored.fingerprint),
    )
    return version_id


async def file_engine_copy(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    client_id: UUID,
    engagement_id: UUID | None,
    work_item_id: UUID | None,
    folder_kind: str,
    title: str,
    stored_key: str,
    stored_version_id: str,
    sha256: str,
    size_bytes: int,
    actor_id: str,
) -> UUID:
    """T-01-T26: a PDF the tax engine produced, filed as an imported evidence version (channel
    `import`, source `engine_import`) in `folder_kind`; returns the version id. The file was
    scanned and staged by `screen_and_stage` before the caller's unit of work."""
    stored = storage.StoredObject(stored_key, stored_version_id, sha256, size_bytes)
    if stored.key != storage.object_key(tenant_id, stored.fingerprint):
        raise storage.IntegrityError("staged content belongs to another tenant")
    item_id, version_id = uuid4(), uuid4()
    await tx.session.execute(
        insert(EvidenceItem).values(
            id=item_id,
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            client_id=client_id,
            work_item_id=work_item_id,
            scope="engagement" if engagement_id is not None else "client",
            folder_kind=folder_kind,
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
            engagement_id=engagement_id,
            evidence_item_id=item_id,
            version_no=1,
            fingerprint=stored.fingerprint,
            storage_key=stored.key,
            storage_version_id=stored.version_id,
            size_bytes=stored.size,
            media_type="application/pdf",
            source="engine_import",
            method="imported",
            pulled_at=system_now(),
            channel="import",
            display_name=title,
        )
    )
    tx.record(
        "evidence_version.created",
        target=Target("evidence_version", version_id),
        after=Ref(evidence_item_id=item_id, fingerprint=stored.fingerprint),
    )
    return version_id


async def file_handoff_copy(
    tx: UnitOfWork,
    *,
    source_version_id: UUID,
    tenant_id: UUID,
    client_id: UUID,
    engagement_id: UUID,
    work_item_id: UUID,
    title: str,
    actor_id: str,
) -> UUID:
    """T-02-T20: a K-1 shared to another return's intake, filed there as a new evidence item
    whose first version (channel `internal_handoff`) names the same stored bytes (write-once,
    so nothing is copied); returns the version id."""
    source = (
        await tx.session.execute(
            select(
                EvidenceVersion.fingerprint,
                EvidenceVersion.storage_key,
                EvidenceVersion.storage_version_id,
                EvidenceVersion.size_bytes,
                EvidenceVersion.media_type,
            ).where(EvidenceVersion.id == source_version_id)
        )
    ).one_or_none()
    if source is None:
        raise storage.IntegrityError("the shared version is not this tenant's")
    item_id, version_id = uuid4(), uuid4()
    await tx.session.execute(
        insert(EvidenceItem).values(
            id=item_id,
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            client_id=client_id,
            work_item_id=work_item_id,
            scope="engagement",
            folder_kind="source_documents",  # a K-1 received is a source document here
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
            engagement_id=engagement_id,
            evidence_item_id=item_id,
            version_no=1,
            fingerprint=source.fingerprint,
            storage_key=source.storage_key,
            storage_version_id=source.storage_version_id,
            size_bytes=source.size_bytes,
            media_type=source.media_type,
            source="internal_handoff",
            method="imported",
            pulled_at=system_now(),
            channel="internal_handoff",
            display_name=title,
        )
    )
    tx.record(
        "evidence_version.created",
        target=Target("evidence_version", version_id),
        after=Ref(evidence_item_id=item_id, fingerprint=source.fingerprint),
    )
    return version_id


__all__ = [
    "SIGNED_AUTHORIZATIONS",
    "ScreenedFile",
    "file_engine_copy",
    "file_handoff_copy",
    "file_signed_copy",
    "read_staged",
    "screen_and_stage",
]


async def version_titles(session: AsyncSession, version_ids: list[UUID]) -> dict[UUID, str]:
    """Each filed version's item title (N-02-T13: the envelope drawer's documents). For a caller
    that authorised the envelope the versions are named on; others' rows stay out under RLS."""
    if not version_ids:
        return {}
    rows = await session.execute(
        select(EvidenceVersion.id, EvidenceItem.title)
        .join(EvidenceItem, EvidenceItem.id == EvidenceVersion.evidence_item_id)
        .where(EvidenceVersion.id.in_(version_ids))
    )
    return {version: title for version, title in rows.tuples()}
