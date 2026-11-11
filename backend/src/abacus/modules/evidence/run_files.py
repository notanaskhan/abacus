"""Files for the agent's approved writes (P-10-T38; SPEC-647 AC-P1 to AC-P3; ADR P-35, ADR-004,
ADR-042; DEC-3402).

- `store_workbook`: a run's workbook, built deterministically (`kernel.safe_xlsx`: same rows, same
  bytes; text that a spreadsheet would evaluate is quoted), stored under Object Lock before any
  row names it. Nothing here is filed: the bytes are the run's draft artifact until a person
  approves "Save to Files".
- `file_approved_copy`: the approved write's effect. A new Files item and its first version on
  the engagement (channel `generated`), recorded in the caller's unit of work, whose actor is the
  agent on behalf of the approver ("Hannah Leclerc via Agent"); `file.saved` carries the approval
  grant's id (`after_ref`, INV-5). The caller has consumed the grant (`identity.consume_grant`,
  which re-checks the approver's `file.save`); this module never decides whether to file.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import insert

from abacus.kernel.safe_xlsx import XLSX, Sheet, workbook
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.evidence import storage
from abacus.modules.evidence.events import EvidenceVersionCreated
from abacus.modules.evidence.models import EvidenceItem, EvidenceVersion

FOLDERS: Final = frozenset({"deliverables", "workpapers", "correspondence"})
SOURCE: Final = "agent_run"
MAX_SHEETS: Final = 12
MAX_ROWS: Final = 5_000


class WorkbookTooLarge(ValueError):
    """More sheets or rows than one agent workbook may hold."""


def workbook_bytes(sheets: Sequence[Sheet]) -> bytes:
    """The workbook's bytes: deterministic for the same sheets (ADR-042)."""
    if not 1 <= len(sheets) <= MAX_SHEETS or any(len(s.rows) > MAX_ROWS for s in sheets):
        raise WorkbookTooLarge("workbook_too_large")
    return workbook(sheets)


async def store_workbook(tenant_id: UUID, sheets: Sequence[Sheet]) -> storage.StoredObject:
    """Store the workbook's bytes (before the unit of work that records the artifact)."""
    return await storage.put(tenant_id, workbook_bytes(sheets))


def stored_object(
    tenant_id: UUID, key: str, version_id: str, sha256: str, size: int
) -> storage.StoredObject:
    """A run artifact's stored object, refused when it is not this tenant's."""
    stored = storage.StoredObject(key, version_id, sha256, size)
    if stored.key != storage.object_key(tenant_id, sha256):
        raise storage.IntegrityError("stored content belongs to another tenant")
    return stored


async def file_approved_copy(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    client_id: UUID,
    title: str,
    folder_kind: str,
    stored: storage.StoredObject,
    grant_id: UUID,
    requested_by: UUID,
) -> UUID:
    """The approved copy as a new Files item and version; returns the version id."""
    if folder_kind not in FOLDERS:
        raise ValueError(f"folder {folder_kind!r} is not one an agent's copy may be filed in")
    if stored.key != storage.object_key(tenant_id, stored.fingerprint):
        raise storage.IntegrityError("stored content belongs to another tenant")
    item_id, version_id = uuid4(), uuid4()
    await tx.session.execute(
        insert(EvidenceItem).values(
            id=item_id,
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            client_id=client_id,
            scope="engagement",
            folder_kind=folder_kind,
            title=title,
            created_by_kind="agent",
            created_by_id=tx.tenant.actor_id,
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
            media_type=XLSX,
            source=SOURCE,
            method="uploaded",
            channel="generated",
            display_name=title,
        )
    )
    tx.record(
        "evidence_version.created",
        target=Target("evidence_version", version_id),
        after=Ref(evidence_item_id=item_id, fingerprint=stored.fingerprint),
    )
    tx.record(
        "file.saved",
        target=Target("evidence_item", item_id),
        after=Ref(grant=grant_id, evidence_version_id=version_id),
    )
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
    "FOLDERS",
    "WorkbookTooLarge",
    "file_approved_copy",
    "store_workbook",
    "stored_object",
    "workbook_bytes",
]
