"""A stored version filed again under another work item (N-04-T07; DEC-2953).

"Attach to N2" files the intake's document as a supporting document of an existing notice. Evidence
is immutable and an item's placement is set once, so the document gets a new item on that notice's
work item whose first version points at the same stored bytes (content-addressed: no copy is
made). The original stays where it was.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import insert, select

from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.evidence.models import EvidenceItem, EvidenceVersion

SOURCE_DOCUMENTS = "source_documents"


async def file_copy_onto_work_item(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    version_id: UUID,
    engagement_id: UUID,
    work_item_id: UUID,
    title: str,
    actor_id: str,
) -> UUID:
    """The new version's id, under `work_item_id`, pointing at `version_id`'s bytes."""
    source = (
        await tx.session.execute(select(EvidenceVersion).where(EvidenceVersion.id == version_id))
    ).scalar_one_or_none()
    if source is None:
        raise NotFound("evidence_version")
    item_id, new_id = uuid4(), uuid4()
    await tx.session.execute(
        insert(EvidenceItem).values(
            id=item_id,
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            work_item_id=work_item_id,
            folder_kind=SOURCE_DOCUMENTS,
            title=title,
            created_by_kind="human",
            created_by_id=actor_id,
        )
    )
    tx.record(
        "evidence_item.created",
        target=Target("evidence_item", item_id),
        after=Ref(work_item_id=work_item_id),
    )
    await tx.session.execute(
        insert(EvidenceVersion).values(
            id=new_id,
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            evidence_item_id=item_id,
            version_no=1,
            fingerprint=source.fingerprint,
            storage_key=source.storage_key,
            storage_version_id=source.storage_version_id,
            size_bytes=source.size_bytes,
            media_type=source.media_type,
            source=source.source,
            method=source.method,
            pulled_at=source.pulled_at,
            client_entity_id=source.client_entity_id,
            display_name=title,
        )
    )
    tx.record(
        "evidence_version.created",
        target=Target("evidence_version", new_id),
        after=Ref(evidence_item_id=item_id, fingerprint=source.fingerprint),
    )
    return new_id


__all__ = ["file_copy_onto_work_item"]
