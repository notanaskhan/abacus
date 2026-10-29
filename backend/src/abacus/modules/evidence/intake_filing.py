"""Filing an intake object (N-01-T18; N-01 §3.4; ADR-158, ADR-162; DEC-1061).

A person's triage files an intake attachment as evidence: a new item (in an engagement, or the
client's permanent file) with its first version, or the next version of an item already there
(optionally superseding the one it replaces; superseding never deletes). The version reuses the
intake object as stored: content-addressed bytes by their fingerprint, and a detached-key portal
file (ADR-162 §5) under its own key, the version taking the attachment's id so its object path
and key resolve unchanged. The caller (communications' apply) authorised `inbox.file` and holds
the attachment's row; this runs inside its unit of work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select

from abacus.kernel.clock import system_now
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.evidence import storage
from abacus.modules.evidence.models import EvidenceItem, EvidenceVersion

SOURCE_DOCUMENTS: Final = "source_documents"
_CHANNEL: Final = {"email": "email", "portal_upload": "portal", "staff_logged": "firm_upload"}


class SupersedeMismatch(DomainConflict):
    """The version to supersede is not on the chosen destination's client: choose again."""

    code = "supersede_mismatch"


@dataclass(frozen=True)
class IntakeObject:
    attachment_id: UUID
    client_id: UUID
    channel: str  # the intake channel (email, portal_upload, staff_logged)
    storage_key: str
    storage_version_id: str
    fingerprint: str
    size_bytes: int
    media_type: str
    detached: bool


@dataclass(frozen=True)
class Filed:
    evidence_item_id: UUID
    evidence_version_id: UUID
    version_no: int


async def file_intake_object(
    tx: UnitOfWork,
    obj: IntakeObject,
    *,
    tenant_id: UUID,
    title: str,
    engagement_id: UUID | None,
    work_item_id: UUID | None,
    folder_kind: str = SOURCE_DOCUMENTS,
    next_version_of: UUID | None = None,
    supersede: bool = False,
    actor_kind: str,
    actor_id: str,
) -> Filed:
    """File `obj`: a new item, or (with `next_version_of`, an existing version) the next version
    of that version's item, superseding it when asked."""
    if obj.detached:
        if obj.storage_key != storage.detached_path(tenant_id, obj.attachment_id):
            raise storage.IntegrityError("the intake object is not at its own path")
    elif obj.storage_key != storage.object_key(tenant_id, obj.fingerprint):
        raise storage.IntegrityError("staged content belongs to another tenant")
    if next_version_of is not None:
        prior = (
            await tx.session.execute(
                select(
                    EvidenceVersion.evidence_item_id,
                    EvidenceItem.client_id,
                    EvidenceItem.engagement_id,
                )
                .join(EvidenceItem, EvidenceItem.id == EvidenceVersion.evidence_item_id)
                .where(EvidenceVersion.id == next_version_of)
            )
        ).one_or_none()
        if prior is None:
            raise NotFound("evidence_version")
        if prior.client_id != obj.client_id:
            raise SupersedeMismatch
        item_id: UUID = prior.evidence_item_id
        engagement_id = prior.engagement_id
        version_no = (
            int(
                (
                    await tx.session.execute(
                        select(func.max(EvidenceVersion.version_no)).where(
                            EvidenceVersion.evidence_item_id == item_id
                        )
                    )
                ).scalar_one()
            )
            + 1
        )
    else:
        item_id = uuid4()
        version_no = 1
        await tx.session.execute(
            insert(EvidenceItem).values(
                id=item_id,
                tenant_id=tenant_id,
                engagement_id=engagement_id,
                client_id=obj.client_id,
                work_item_id=work_item_id,
                scope="engagement" if engagement_id is not None else "client",
                folder_kind=folder_kind,
                title=title,
                created_by_kind=actor_kind,
                created_by_id=actor_id,
            )
        )
        tx.record(
            "evidence_item.created",
            target=Target("evidence_item", item_id),
            after=Ref(client_id=obj.client_id),
        )
    version_id = obj.attachment_id if obj.detached else uuid4()
    await tx.session.execute(
        insert(EvidenceVersion).values(
            id=version_id,
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            evidence_item_id=item_id,
            version_no=version_no,
            fingerprint=obj.fingerprint,
            storage_key=obj.storage_key,
            storage_version_id=obj.storage_version_id,
            size_bytes=obj.size_bytes,
            media_type=obj.media_type,
            source="inbox",
            method="uploaded",
            pulled_at=system_now(),
            channel=_CHANNEL.get(obj.channel, "firm_upload"),
            storage_mode="detached_key" if obj.detached else "content_addressed",
            supersedes_version_id=next_version_of if supersede else None,
            display_name=title,
        )
    )
    tx.record(
        "evidence_version.created",
        target=Target("evidence_version", version_id),
        after=Ref(evidence_item_id=item_id, inbox_attachment_id=obj.attachment_id),
    )
    return Filed(item_id, version_id, version_no)
