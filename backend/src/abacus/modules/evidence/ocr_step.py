"""The `upload.ocr` step (P-11-T25; P-11 F7, AC7.1 to AC7.7; DEC-2309). PROTECTED.

Runs after `upload.words` and before `upload.pii_scan`, so the scan, masks, citations and viewer
read a scan's words with no change of their own (`pages_of` prefers an OCR row). A version's bytes,
Object Lock and fingerprint never change: OCR output is a derived, rebuildable record (ADR-004,
ADR-110). The gate runs first and its refusal is final (never retried, never rerouted): the page
stays `not_scannable` and the consumer offers manual entry. No word, value or image reaches a log,
an event or a Temporal payload (AC7.7). Ends by publishing `evidence_text.ready` for a version with
words, whichever way they were read: form extraction starts from it.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Final
from uuid import UUID

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import dispatch, signal_workflow
from abacus.kernel.logging import get_logger
from abacus.kernel.ocr import OcrPage, OcrProvider, TextractOcr
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import service_line_of
from abacus.modules.evidence import storage
from abacus.modules.evidence.events import EvidenceTextReady, OcrRefusal, OcrRunRefused
from abacus.modules.evidence.intake_sources import IntakeSource, source_of, target_type
from abacus.modules.evidence.models import EvidenceVersion, InboxFile
from abacus.modules.evidence.object_keys import under_key
from abacus.modules.evidence.ocr_gate import (
    GateFacts,
    Refusal,
    first_refusal,
    over_daily_cap,
    record_run,
)
from abacus.modules.evidence.ocr_normalise import IMAGES, PDF, PageImage, rasterise_isolated
from abacus.modules.evidence.pii import names_a_tin
from abacus.modules.evidence.processing import record_ocr_extraction
from abacus.modules.evidence.repository import (
    OCR_VERSION,
    insert_pages,
    pages_of,
    sources_without_ocr,
)
from abacus.modules.evidence.words import (
    WORDS_VERSION,
    KeyHint,
    PageWords,
    Word,
    layer_document,
)
from abacus.modules.evidence.workflow_types import (
    INBOX,
    INTAKE,
    VERSION,
    BackfillInput,
    UploadInput,
)
from abacus.modules.evidence.workflows import BACKFILL_BATCH, LongOcr, OcrBackfill
from abacus.modules.identity.api import is_synthetic_firm

API: Final = "detect_text"
FORMS_API: Final = "analyze_forms"
BACKGROUND_ABOVE_PAGES: Final = 20  # P-11 §4: a long scan never delays a person's upload
LONG: Final = "long"
SHORT: Final = "short"
TAX_LINE: Final = "tax"
_log = get_logger(__name__)
# The gate's refusal in the event's words (`evidence.events.OcrRefusal`).
REFUSAL_WORDS: Final[dict[Refusal, OcrRefusal]] = {
    "kill_switch": "kill_switch",
    "flag_off": "flag_off",
    "terms_not_covering": "provider_terms",
    "boundary_basis": "boundary_basis",
    "consent_missing": "consent_7216",
    "quota_exceeded": "daily_page_cap",
}
_provider: list[OcrProvider] = []


def set_provider(provider: OcrProvider) -> None:
    """The synthetic corpus's `FakeOcr` (tests and synthetic firms); else Textract."""
    _provider[:] = [provider]


def provider() -> OcrProvider:
    if not _provider:
        _provider.append(TextractOcr())
    return _provider[0]


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "evidence.upload_processing")


def _page_words(
    page: int,
    width: float,
    height: float,
    rotation: int,
    read: OcrPage,
    forms: OcrPage | None = None,
) -> PageWords:
    return PageWords(
        page,
        width,
        height,
        rotation,
        tuple(
            Word(w.text, float(w.bbox[0]), float(w.bbox[1]), float(w.bbox[2]), float(w.bbox[3]),
                 float(w.confidence))
            for w in read.words
        ),
        hints=tuple(
            KeyHint(k.key, float(k.value_bbox[0]), float(k.value_bbox[1]),
                    float(k.value_bbox[2]), float(k.value_bbox[3]))
            for k in (forms.key_values if forms else ())
        ),
    )  # fmt: skip


async def gate_facts(tenant: TenantContext, engagement_id: UUID | None) -> GateFacts:
    """§7216's scope, failing closed: a file with no engagement yet counts as TRI, and a person's
    consent is C19's to prove (the gate needs counsel's `tri_basis` until the check is wired)."""
    line = None if engagement_id is None else await service_line_of(tenant, engagement_id)
    return GateFacts(
        synthetic_firm=await is_synthetic_firm(tenant),
        tri_scope=line is None or line == TAX_LINE,
        tri_consented=False,
    )


async def ocr_upload(given: UploadInput) -> int:
    """One upload's OCR: returns the pages read (0 when none were due or the gate refused)."""
    tenant_id, source_id = UUID(given.tenant_id), UUID(given.source_id)
    tenant = _system(tenant_id)
    version_id = source_id if given.kind == VERSION else None
    inbox_id = source_id if given.kind == INBOX else None
    attachment_id = source_id if given.kind == INTAKE else None
    async with tenant_session(tenant) as session:
        source = await source_of(session, tenant, given.kind, source_id)
        pages = await pages_of(
            session,
            evidence_version_id=version_id,
            inbox_file_id=inbox_id,
            inbox_attachment_id=attachment_id,
            extractor_version=WORDS_VERSION,
        )
    if source is None:
        return 0  # withdrawn in flight, or gone: nothing to read
    read = 0
    due: list[int] | None
    if source.media_type == PDF:
        due = [p.page_no for p in pages if not p.has_text_layer]
    elif source.media_type in IMAGES and not pages:
        due = None  # every frame of an image
    else:
        due = []
    if due is None or due:
        read = await _read(given, tenant, version_id, inbox_id, attachment_id, source, due)
    await _publish_text_ready(tenant, version_id, source.engagement_id)
    return read


async def _read(
    given: UploadInput,
    tenant: TenantContext,
    version_id: UUID | None,
    inbox_id: UUID | None,
    attachment_id: UUID | None,
    found: EvidenceVersion | InboxFile | IntakeSource,
    due: list[int] | None,
) -> int:
    tenant_id = tenant.tenant_id
    facts = await gate_facts(tenant, found.engagement_id)
    refused = await first_refusal(tenant, facts)
    if refused is None and await over_daily_cap(tenant, len(due) if due else 1):
        refused = "quota_exceeded"
    engine = provider()
    if refused is not None:
        await record_run(
            tenant, evidence_version_id=version_id, inbox_file_id=inbox_id,
            provider=engine.name, api=API, pages=list(due or []), refused=refused,
            synthetic_firm=facts.synthetic_firm, request_ids=[],
        )  # fmt: skip
        if version_id is not None:
            async with uow(tenant) as tx:
                tx.emit(
                    OcrRunRefused(
                        evidence_version_id=version_id,
                        engagement_id=found.engagement_id,
                        reason=REFUSAL_WORDS[refused],
                    )
                )
                tx.record(
                    "upload.ocr_refused",
                    target=Target(target_type(given.kind), UUID(given.source_id)),
                )
        _log.info("upload.ocr_refused", kind=given.kind, reason=refused)
        return 0
    stored = storage.StoredObject(
        found.storage_key, found.storage_version_id, found.fingerprint, found.size_bytes
    )
    content = await storage.get(tenant_id, stored)
    images = await asyncio.to_thread(rasterise_isolated, content, found.media_type, due)
    results: list[tuple[PageImage, OcrPage, OcrPage | None]] = []
    for image in images:
        width, height = Decimal(str(image.width_pt)), Decimal(str(image.height_pt))
        page_read = await engine.read(image.png, width_pt=width, height_pt=height, api=API)
        forms = (
            await engine.read(image.png, width_pt=width, height_pt=height, api=FORMS_API)
            if names_a_tin(w.text for w in page_read.words)
            else None
        )
        results.append((image, page_read, forms))
    run_id = await record_run(
        tenant, evidence_version_id=version_id, inbox_file_id=inbox_id, provider=engine.name,
        api=API, pages=[i.page for i in images], refused=None,
        synthetic_firm=facts.synthetic_firm,
        request_ids=[r.request_id for _, r, _f in results if r.request_id],
    )  # fmt: skip
    with_forms = [(i, f) for i, _r, f in results if f is not None]
    if with_forms:
        await record_run(
            tenant, evidence_version_id=version_id, inbox_file_id=inbox_id, provider=engine.name,
            api=FORMS_API, pages=[i.page for i, _f in with_forms], refused=None,
            synthetic_firm=facts.synthetic_firm,
            request_ids=[f.request_id for _i, f in with_forms if f.request_id],
        )  # fmt: skip
    under = under_key(found)
    rows: list[dict[str, object]] = []
    for image, page_read, forms in results:
        layer = _page_words(
            image.page, image.width_pt, image.height_pt, image.rotation, page_read, forms
        )
        put = (
            await storage.put(tenant_id, layer_document(layer), under=under)
            if layer.words
            else None
        )
        rows.append(
            {
                "tenant_id": tenant_id,
                "evidence_version_id": version_id,
                "inbox_file_id": inbox_id,
                "inbox_attachment_id": attachment_id,
                "derivation_id": None,
                "page_no": image.page,
                "width_pt": Decimal(str(image.width_pt)),
                "height_pt": Decimal(str(image.height_pt)),
                "rotation": image.rotation,
                "has_text_layer": bool(layer.words),
                "word_count": len(layer.words),
                "text_layer_key": put.key if put else None,
                "text_layer_version_id": put.version_id if put else None,
                "text_layer_fingerprint": put.fingerprint if put else None,
                "text_layer_size": put.size if put else None,
                "ocr_used": True,
                "extractor_version": OCR_VERSION,
                "text_source": "ocr",
                "ocr_run_id": run_id,
                "mean_confidence": page_read.mean_confidence,
                "low_conf_words": page_read.low_confidence_words(),
            }
        )
    async with uow(tenant) as tx:
        added = await insert_pages(tx.session, rows)
        tx.record(
            "upload.ocr_read",
            target=Target(target_type(given.kind), UUID(given.source_id)),
            after=Ref(pages=added, run=run_id),
        )
    # SPEC-029's checks read this row on a scan, as they read a PDF's text (P-11-T25).
    await record_ocr_extraction(
        given,
        source=found,
        page_count=len(results),
        pages=[" ".join(w.text for w in page_read.words) for _, page_read, _f in results],
    )
    _log.info("upload.ocr_read", kind=given.kind, pages=len(rows))
    return len(rows)


async def _publish_text_ready(
    tenant: TenantContext, version_id: UUID | None, engagement_id: UUID | None
) -> None:
    if version_id is None:
        return
    async with tenant_session(tenant) as session:
        pages = await pages_of(
            session, evidence_version_id=version_id, extractor_version=WORDS_VERSION
        )
    worded = [p for p in pages if p.has_text_layer]
    if not worded:
        return
    source = "ocr" if any(p.extractor_version == OCR_VERSION for p in worded) else "text_layer"
    async with uow(tenant) as tx:
        tx.emit(
            EvidenceTextReady(
                evidence_version_id=version_id,
                engagement_id=engagement_id,
                text_source=source,
                pages=len(worded),
            )
        )
        tx.record(
            "upload.text_ready",
            target=Target("evidence_version", version_id),
            after=Ref(pages=len(worded)),
        )


# --- The backfill and long scans (AC7.4; P-11 §4) -------------------------------------------


async def pending_ocr(given: BackfillInput) -> list[UploadInput]:
    """The `upload.pending_ocr` activity's body: the next uploads with a page no reader has words
    for and no OCR row yet, by id after the cursors. An attachment's intake isn't included: an
    intake file is read when it's filed."""
    tenant_id = UUID(given.tenant_id)
    async with tenant_session(_system(tenant_id)) as session:
        found = await sources_without_ocr(
            session,
            OCR_VERSION,
            after_version=UUID(given.after_version) if given.after_version else None,
            after_inbox=UUID(given.after_inbox) if given.after_inbox else None,
            limit=BACKFILL_BATCH,
        )
    return [
        UploadInput(given.tenant_id, VERSION if kind == "version" else INBOX, str(source))
        for kind, source in found
    ]


def ocr_backfill_id(tenant_id: UUID) -> str:
    return f"ocr_backfill:{tenant_id}"


async def start_ocr_backfill(tenant_id: UUID) -> str:
    """Start (or join) the firm's backfill; an operator command runs this (never a request)."""
    workflow_id = ocr_backfill_id(tenant_id)
    await dispatch(
        OcrBackfill,
        BackfillInput(str(tenant_id)),
        id=workflow_id,
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return workflow_id


def long_ocr_id(given: UploadInput) -> str:
    return f"upload_ocr:{given.tenant_id}:{given.kind}:{given.source_id}"


async def route_ocr(given: UploadInput) -> str:
    """`upload.ocr_route`: more than 20 due pages run as `LongOcr` on the background queue, and
    the upload waits for it (ADR-071 allows no queue on an activity); the rest run inline. Pages
    come from the word layer: an image or a file with no layer yet counts as short."""
    tenant = _system(UUID(given.tenant_id))
    source_id = UUID(given.source_id)
    async with tenant_session(tenant) as session:
        pages = await pages_of(
            session,
            evidence_version_id=source_id if given.kind == VERSION else None,
            inbox_file_id=source_id if given.kind == INBOX else None,
            inbox_attachment_id=source_id if given.kind == INTAKE else None,
            extractor_version=WORDS_VERSION,
        )
    if sum(1 for p in pages if not p.has_text_layer) <= BACKGROUND_ABOVE_PAGES:
        return SHORT
    await dispatch(
        LongOcr,
        given,
        id=long_ocr_id(given),
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return LONG


async def ocr_finished(given: UploadInput) -> None:
    """`upload.ocr_finished`: `LongOcr` tells the upload it can go on."""
    await signal_workflow(
        f"upload:{given.tenant_id}:{given.kind}:{given.source_id}", "long_ocr_done"
    )
