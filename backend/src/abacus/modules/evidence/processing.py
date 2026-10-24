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
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel import _flags
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Handler, OutboxEvent, Ref, Target, uow
from abacus.modules.engagements.api import AccountRule, area_for, check_facts, version_detail
from abacus.modules.evidence import storage
from abacus.modules.evidence.checks import (
    CHECKER_VERSION,
    ExtractedFields,
    active_content,
    aging_checks,
    closing_consistent,
    duplicate,
    readable,
    running_balance,
    schedule_checks,
    statement_checks,
)
from abacus.modules.evidence.cross_checks import Account, aging_cross_check, bank_cross_check
from abacus.modules.evidence.events import (
    EvidenceUploaded,
    EvidenceVersionCreated,
    InboxFileAdded,
    InboxFileExtracted,
    UploadChecksRecorded,
)
from abacus.modules.evidence.extraction import EXTRACTOR_VERSION, Extraction, extract_isolated
from abacus.modules.evidence.models import UploadExtraction
from abacus.modules.evidence.object_keys import under_key
from abacus.modules.evidence.previews import RENDERER_VERSION, render_isolated
from abacus.modules.evidence.repository import (
    checks_exist,
    extraction_for,
    get_inbox_file,
    get_version,
    insert_checks,
    insert_extraction,
    insert_preview,
    insert_preview_pages,
    latest_checks,
    newest_extraction,
    other_version_with_fingerprint,
    preview_for,
    stale_pdf_uploads,
)
from abacus.modules.evidence.service import engagement_snapshots
from abacus.modules.evidence.workflow_types import INBOX, VERSION, UploadInput
from abacus.modules.evidence.workflows import TrustLayerBackfill, UploadProcessing
from abacus.modules.ledger.api import snapshot_view
from abacus.modules.requests.api import (
    RequestItemDocumentKindChanged,
    items_of_version,
    latest_version_of,
)

_log = get_logger(__name__)
# Interactive: a client is waiting to hear whether the file is usable (SPEC-029 story 1).
# P-03-T05: the trust layer backfill is bulk work and never delays a person.
WORKFLOWS: dict[type, WorkClass] = {
    UploadProcessing: "interactive",
    TrustLayerBackfill: "background",
}
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


async def on_document_kind_changed(event: OutboxEvent) -> None:
    """TASK-055 D5: the team changed what an item expects; check its latest upload again (a
    separate run per event, so the first run's ID stays its own)."""
    tenant_id = event.tenant_id
    item = UUID(str(event.payload["request_item_id"]))
    version = await latest_version_of(_system(tenant_id), item)
    if version is None or not await flag_enabled(_system(tenant_id), _flags.UPLOADS_PROCESSING):
        return
    await dispatch(
        UploadProcessing,
        UploadInput(str(tenant_id), VERSION, str(version)),
        id=f"{workflow_id(tenant_id, VERSION, version)}:recheck:{event.event_id}",
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


async def on_evidence_version_created(event: OutboxEvent) -> None:
    """TASK-056 D1: every new version is processed (pipeline workbooks too, for previews); an
    upload's own event starts the same run (same workflow ID), so it runs once."""
    await _start(event.tenant_id, VERSION, UUID(str(event.payload["evidence_version_id"])))


SUBSCRIPTIONS: dict[str, Handler] = {
    EvidenceVersionCreated.event_type: on_evidence_version_created,
    EvidenceUploaded.event_type: on_evidence_uploaded,
    InboxFileAdded.event_type: on_inbox_file_added,
    RequestItemDocumentKindChanged.event_type: on_document_kind_changed,
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
        derived = await storage.put(tenant_id, document.encode(), under=under_key(source))
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
        if row is not None and inbox_id is not None and found.status == "extracted":
            tx.emit(  # SPEC-033 (TASK-066): the matcher may follow (P-7)
                InboxFileExtracted(engagement_id=source.engagement_id, inbox_file_id=inbox_id)
            )
    _log.info("upload.extracted", kind=given.kind, status=found.status, reason=found.reason)
    return found.status


# --- Checks (SPEC-029 goals 5 and 6; TASK-055) ---------------------------------------------------


async def year_end_accounts(
    tenant: TenantContext, engagement_id: UUID, year_end: date, methodology: UUID | None
) -> list[Account] | None:
    """The year end's trial balance accounts with their methodology area names, from the
    latest snapshot behind this engagement's evidence; None without one."""
    views = [
        await snapshot_view(tenant, i) for i in await engagement_snapshots(tenant, engagement_id)
    ]
    found = [v for v in views if v.period_end == year_end]
    if not found:
        return None
    latest = max(found, key=lambda v: v.pulled_at)
    areas: dict[str, str] = {}
    rules: tuple[AccountRule, ...] = ()
    if methodology is not None:
        detail = await version_detail(tenant, methodology)
        areas = {a.code: a.name for a in detail.areas}
        rules = detail.rules
    return [
        Account(
            line.account_code,
            line.account_name,
            line.debit - line.credit,
            areas.get(area_for(line.account_code, rules) or ""),
        )
        for line in latest.lines
    ]


async def _document(tenant_id: UUID, row: UploadExtraction) -> dict[str, object] | None:
    if row.storage_key is None or row.storage_version_id is None or row.fingerprint is None:
        return None
    stored = storage.StoredObject(
        row.storage_key, row.storage_version_id, row.fingerprint, row.size_bytes or 0
    )
    loaded = json.loads(await storage.get(tenant_id, stored))
    return cast(dict[str, object], loaded) if isinstance(loaded, dict) else None


def _fields(row: UploadExtraction, document: dict[str, object] | None) -> ExtractedFields:
    return ExtractedFields(
        row.status,
        row.reason,
        row.period_start,
        row.period_end,
        row.as_of,
        row.entity_name,
        row.opening,
        row.closing,
        row.credits,
        row.debits,
        document,
    )


async def check_upload(given: UploadInput) -> int:
    """Check one evidence version against the kind its item expects; returns how many checks
    were recorded (0 when already checked for this kind, or for an inbox file, Q8)."""
    if given.kind != VERSION:
        return 0
    tenant_id, version_id = UUID(given.tenant_id), UUID(given.source_id)
    tenant = _system(tenant_id)
    items = await items_of_version(tenant, version_id)
    kind = next((i.document_kind for i in items if i.document_kind is not None), None)
    async with tenant_session(tenant) as session:
        if await checks_exist(session, version_id, CHECKER_VERSION, kind):
            return 0
        row = await newest_extraction(session, evidence_version_id=version_id)
        version = await get_version(session, version_id)
        if row is None or version is None:
            raise NotFound("upload_extraction")
        other = await other_version_with_fingerprint(
            session, version.engagement_id, version.fingerprint, version_id
        )
    facts = await check_facts(tenant, version.engagement_id)
    if facts is None:
        raise NotFound("engagement")
    other_items = await items_of_version(tenant, other) if other is not None else []
    results = [
        readable(_fields(row, None)),
        duplicate(other_items[0].id if other_items else None, other is not None),
    ]
    flagged = active_content(_fields(row, None))
    if flagged is not None:
        results.append(flagged)
    if row.status == "extracted" and kind is not None:
        document = await _document(tenant_id, row)
        fields = _fields(row, document)
        if kind == "bank_statement":
            results += statement_checks(fields, facts.fiscal_period_end, facts.client_entity_name)
            results += [running_balance(fields), closing_consistent(fields)]  # TASK-058 (A)
        elif kind in ("ar_aging", "ap_aging"):
            results += aging_checks(fields, facts.fiscal_period_end)
        else:
            results += schedule_checks(fields)
        if kind != "schedule":
            accounts = await year_end_accounts(
                tenant,
                version.engagement_id,
                facts.fiscal_period_end,
                facts.methodology_version_id,
            )
            results.append(
                bank_cross_check(
                    row.closing,
                    row.account_last4,
                    accounts,
                    facts.methodology_version_id is not None,
                )
                if kind == "bank_statement"
                else aging_cross_check(row.grand_total, kind == "ap_aging", accounts)
            )
    rows: list[dict[str, object]] = [
        {
            "tenant_id": tenant_id,
            "engagement_id": version.engagement_id,
            "evidence_version_id": version_id,
            "checker_version": CHECKER_VERSION,
            "document_kind": kind,
            "check_code": r.code,
            "outcome": r.outcome,
            "audience": r.audience,
            "reason": r.reason,
            "expected_date": r.expected_date,
            "found_date": r.found_date,
            "amount": r.amount,
            "difference": r.difference,
            "account_code": r.account_code,
            "ref_item_id": r.ref_item_id,
        }
        for r in results
    ]
    async with uow(tenant) as tx:
        added = await insert_checks(tx.session, rows)
        tx.record(
            "upload.checked",
            target=Target("evidence_version", version_id),
            after=Ref(checks=added, problems=sum(r.outcome == "problem" for r in results)),
        )
        if added and items:  # SPEC-030 (TASK-059): the reviewer may follow
            tx.emit(
                UploadChecksRecorded(
                    engagement_id=version.engagement_id, evidence_version_id=version_id
                )
            )
    _log.info("upload.checked", kind=kind, checks=added)
    return added


# --- Previews (SPEC-029 goal 8; TASK-056) --------------------------------------------------------


async def preview_upload(given: UploadInput) -> str:
    """Render one upload's preview and record it; returns its kind. Idempotent."""
    tenant_id, source_id = UUID(given.tenant_id), UUID(given.source_id)
    tenant = _system(tenant_id)
    version_id = source_id if given.kind == VERSION else None
    inbox_id = source_id if given.kind == INBOX else None
    async with tenant_session(tenant) as session:
        done = await preview_for(
            session,
            evidence_version_id=version_id,
            inbox_file_id=inbox_id,
            renderer_version=RENDERER_VERSION,
        )
        if done is not None:
            return done.kind
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
    rendered = await asyncio.to_thread(
        render_isolated, await storage.get(tenant_id, stored), source.media_type
    )
    under = under_key(source)
    pages = [await storage.put(tenant_id, page.png, under=under) for page in rendered.pages]
    async with uow(tenant) as tx:
        row = await insert_preview(
            tx.session,
            tenant_id=tenant_id,
            engagement_id=source.engagement_id,
            evidence_version_id=version_id,
            inbox_file_id=inbox_id,
            renderer_version=RENDERER_VERSION,
            kind=rendered.kind,
            reason=rendered.reason,
            page_count=len(pages),
            truncated=rendered.truncated,
        )
        if row is not None:
            await insert_preview_pages(
                tx.session,
                [
                    {
                        "tenant_id": tenant_id,
                        "preview_id": row.id,
                        "page_no": n,
                        "storage_key": put.key,
                        "storage_version_id": put.version_id,
                        "fingerprint": put.fingerprint,
                        "size_bytes": put.size,
                        "width": page.width,
                        "height": page.height,
                    }
                    for n, (put, page) in enumerate(zip(pages, rendered.pages, strict=True), 1)
                ],
            )
        tx.record(
            "upload.previewed" if row is not None else "upload.preview_exists",
            target=Target("evidence_version" if version_id else "inbox_file", source_id),
            after=Ref(pages=len(pages)),
        )
    return rendered.kind


# --- Material for the upload reviewer (SPEC-030; TASK-058) ---------------------------------------

EXCERPT_CHARS: Final = 14_000  # about 3,500 tokens: inside the context's task budget
EXCERPT_ROWS: Final = 60


@dataclass(frozen=True)
class ReviewMaterial:
    """What the upload reviewer may see of a version: identifiers, code's own findings, and an
    excerpt of the extraction. Pages and sheets are the full extraction, for citation checks."""

    engagement_id: UUID
    extraction_status: str
    document_kind: str | None
    item_description: str
    checks: tuple[tuple[str, str, str | None], ...]  # (code, outcome, reason), every audience
    excerpt_pages: tuple[tuple[int, str], ...]
    excerpt_tables: tuple[tuple[str, tuple[tuple[str, ...], ...]], ...]
    truncated: bool
    pages: dict[int, str]
    sheets: dict[str, tuple[tuple[str, ...], ...]]


def _excerpt(
    pages: dict[int, str], sheets: dict[str, tuple[tuple[str, ...], ...]]
) -> tuple[tuple[tuple[int, str], ...], tuple[tuple[str, tuple[tuple[str, ...], ...]], ...], bool]:
    """The first pages, then the first rows of each sheet, within `EXCERPT_CHARS`."""
    budget, truncated = EXCERPT_CHARS, False
    shown_pages: list[tuple[int, str]] = []
    for number in sorted(pages):
        text = pages[number]
        if budget <= 0:
            truncated = True
            break
        if len(text) > budget:
            text, truncated = text[:budget], True
        shown_pages.append((number, text))
        budget -= len(text)
    shown_sheets: list[tuple[str, tuple[tuple[str, ...], ...]]] = []
    for name, rows in sheets.items():
        if budget <= 0:
            truncated = True
            break
        kept: list[tuple[str, ...]] = []
        for row in rows[:EXCERPT_ROWS]:
            size = sum(len(c) for c in row) + len(row)
            if size > budget:
                truncated = True
                break
            kept.append(row)
            budget -= size
        truncated = truncated or len(rows) > len(kept)
        shown_sheets.append((name, tuple(kept)))
    return tuple(shown_pages), tuple(shown_sheets), truncated


async def review_material(tenant: TenantContext, version_id: UUID) -> ReviewMaterial | None:
    """For an agent run authorised on the version's engagement; None without an extraction."""
    async with tenant_session(tenant) as session:
        row = await newest_extraction(session, evidence_version_id=version_id)
        checks = await latest_checks(session, version_id)
    if row is None:
        return None
    items = await items_of_version(tenant, version_id)
    item = next((i for i in items), None)
    pages, sheets = await document_text(tenant.tenant_id, row)
    excerpt_pages, excerpt_tables, truncated = _excerpt(pages, sheets)
    return ReviewMaterial(
        row.engagement_id,
        row.status,
        item.document_kind if item is not None else None,
        item.description if item is not None else "",
        # Every code finding, firm-only ones included: the model is told not to repeat them.
        tuple((c.check_code, c.outcome, c.reason) for c in checks),
        excerpt_pages,
        excerpt_tables,
        truncated,
        pages,
        sheets,
    )


async def document_text(
    tenant_id: UUID, row: UploadExtraction
) -> tuple[dict[int, str], dict[str, tuple[tuple[str, ...], ...]]]:
    """The extraction's page text by number and table rows by sheet (empty unless extracted)."""
    document = await _document(tenant_id, row) if row.status == "extracted" else None
    pages: dict[int, str] = {}
    sheets: dict[str, tuple[tuple[str, ...], ...]] = {}
    if document is not None:
        for number, text in enumerate(_strings(document.get("pages")), start=1):
            pages[number] = text
        for table in cast(list[dict[str, object]], document.get("tables") or []):
            if table.get("page") is not None:
                continue  # a PDF's tables are already in its page text
            rows = tuple(
                tuple(str(c) for c in cast(list[object], r))
                for r in cast(list[object], table.get("rows") or [])
            )
            sheets[str(table.get("sheet") or "")] = rows
    return pages, sheets


def excerpt_of(
    pages: dict[int, str], sheets: dict[str, tuple[tuple[str, ...], ...]]
) -> tuple[tuple[tuple[int, str], ...], tuple[tuple[str, tuple[tuple[str, ...], ...]], ...], bool]:
    return _excerpt(pages, sheets)


def _strings(value: object) -> list[str]:
    return [str(v) for v in cast(list[object], value)] if isinstance(value, list) else []


async def stale_pdfs(tenant_id: UUID, limit: int = 500) -> list[UploadInput]:
    """TASK-344: the tenant's PDF uploads and inbox files the current extractor hasn't read, as
    inputs for `process_upload` (the system acting on the firm's own uploads)."""
    async with tenant_session(_system(tenant_id)) as session:
        found = await stale_pdf_uploads(session, EXTRACTOR_VERSION, limit)
    return [
        UploadInput(str(tenant_id), VERSION if kind == "version" else INBOX, str(source))
        for kind, source in found
    ]
