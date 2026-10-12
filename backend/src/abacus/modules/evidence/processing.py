"""Processing uploads (SPEC-029; TASK-054; ADR-110). PROTECTED.

Evidence's subscribers start one `upload_processing` workflow per upload when the firm's
`uploads.processing` flag is on: `evidence.uploaded` (an item upload, or an inbox file assigned
to an item) and `inbox_file.added`. The workflow ID is tenant-qualified and per upload, so an
at-least-once event starts it once.

`process_upload` (the activity's body) reads the stored file, extracts it in an isolated child
(`extraction.extract_isolated`), stores the full extraction as a JSON object (content-addressed)
and records `upload_extractions` with the fields checks need. Idempotent: an upload already
extracted by this extractor version is left alone. A bad file is recorded `unreadable`, never an
error. It acts as the system, on its own module's data; nothing here authorises a person.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel import _flags
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Handler, OutboxEvent, Ref, Target, uow
from abacus.modules.evidence import storage
from abacus.modules.evidence.events import EvidenceUploaded, InboxFileAdded
from abacus.modules.evidence.extraction import EXTRACTOR_VERSION, Extraction, extract_isolated
from abacus.modules.evidence.repository import (
    extraction_for,
    get_inbox_file,
    get_version,
    insert_extraction,
)
from abacus.modules.evidence.workflow_types import INBOX, VERSION, UploadInput
from abacus.modules.evidence.workflows import UploadProcessing

_log = get_logger(__name__)
# Interactive: a client is waiting to hear whether the file is usable (SPEC-029 story 1).
WORKFLOWS: dict[type, WorkClass] = {UploadProcessing: "interactive"}
register_work_classes(WORKFLOWS)


def workflow_id(tenant_id: UUID, kind: str, source_id: UUID) -> str:
    return f"upload:{tenant_id}:{kind}:{source_id}"


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "evidence.upload_processing")


async def _start(tenant_id: UUID, kind: str, source_id: UUID) -> None:
    if not await flag_enabled(_system(tenant_id), _flags.UPLOADS_PROCESSING):
        return
    await dispatch(
        UploadProcessing,
        UploadInput(str(tenant_id), kind, str(source_id)),
        id=workflow_id(tenant_id, kind, source_id),
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


async def on_evidence_uploaded(event: OutboxEvent) -> None:
    await _start(event.tenant_id, VERSION, UUID(str(event.payload["evidence_version_id"])))


async def on_inbox_file_added(event: OutboxEvent) -> None:
    await _start(event.tenant_id, INBOX, UUID(str(event.payload["inbox_file_id"])))


SUBSCRIPTIONS: dict[str, Handler] = {
    EvidenceUploaded.event_type: on_evidence_uploaded,
    InboxFileAdded.event_type: on_inbox_file_added,
}


def _json_default(value: object) -> str:
    if isinstance(value, (date, Decimal)):
        return str(value)
    raise TypeError(type(value).__name__)


def _columns(found: Extraction) -> dict[str, object]:
    """The fields checks need (TASK-055), as columns."""
    statement, aging = found.statement, found.aging
    grand = aging.grand_total[-1] if aging is not None and aging.grand_total else None
    return {
        "page_count": found.page_count,
        "truncated": found.truncated,
        "period_start": statement.period_start if statement else None,
        "period_end": statement.period_end if statement else None,
        "as_of": aging.as_of if aging else None,
        "entity_name": statement.holder[:200] if statement and statement.holder else None,
        "account_last4": statement.account_last4 if statement else None,
        "opening": statement.opening if statement else None,
        "closing": statement.closing if statement else None,
        "credits": statement.credits if statement else None,
        "debits": statement.debits if statement else None,
        "grand_total": grand,
    }


async def process_upload(given: UploadInput) -> str:
    """Extract one upload and record it; returns the extraction's status."""
    tenant_id, source_id = UUID(given.tenant_id), UUID(given.source_id)
    tenant = _system(tenant_id)
    version_id = source_id if given.kind == VERSION else None
    inbox_id = source_id if given.kind == INBOX else None
    async with tenant_session(tenant) as session:
        done = await extraction_for(
            session,
            evidence_version_id=version_id,
            inbox_file_id=inbox_id,
            extractor_version=EXTRACTOR_VERSION,
        )
        if done is not None:
            return done.status
        source = (
            await get_version(session, source_id)
            if version_id is not None
            else await get_inbox_file(session, source_id)
        )
    if source is None:
        raise NotFound("upload")
    stored = storage.StoredObject(
        source.storage_key, source.storage_version_id, source.fingerprint, source.size_bytes
    )
    content = await storage.get(tenant_id, stored)
    found = await asyncio.to_thread(extract_isolated, content, source.media_type)
    derived: storage.StoredObject | None = None
    if found.status == "extracted":
        document = json.dumps(asdict(found), default=_json_default, sort_keys=True)
        derived = await storage.put(tenant_id, document.encode())
    async with uow(tenant) as tx:
        row = await insert_extraction(
            tx.session,
            tenant_id=tenant_id,
            engagement_id=source.engagement_id,
            evidence_version_id=version_id,
            inbox_file_id=inbox_id,
            extractor_version=EXTRACTOR_VERSION,
            status=found.status,
            reason=found.reason,
            storage_key=derived.key if derived else None,
            storage_version_id=derived.version_id if derived else None,
            fingerprint=derived.fingerprint if derived else None,
            size_bytes=derived.size if derived else None,
            **_columns(found),
        )
        # A concurrent run that got there first leaves `row` None: still one audited write.
        tx.record(
            "upload.extracted" if row is not None else "upload.extraction_exists",
            target=Target("evidence_version" if version_id else "inbox_file", source_id),
            after=Ref(fingerprint=source.fingerprint),
        )
    _log.info("upload.extracted", kind=given.kind, status=found.status, reason=found.reason)
    return found.status
