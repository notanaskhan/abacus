"""Unlocking a password-protected PDF (ADR-052, ADR-004). PROTECTED, red zone.

Two paths, both with the password used once in memory and never stored, logged or audited:

- **As a new version** (`unlock_upload`, TASK-323): card and bank e-statements often arrive with a
  password. PDFium opens the stored file in an isolated child and saves a copy without security;
  the copy is uploaded to the same request item as a new version through the ordinary upload
  path (scan, store, extract, words, PII scan, masked rendition, check).
- **As a derivation** (`unlock_version`, P-03-T19; C4 §3.5; SPEC-322 F5): the viewer's Unlock.
  One isolated child (`derive_unlocked`) decrypts, reads the word layer (`words.extract_words`,
  w2), scans it for PII (`pii.scan_layer`, d2) and renders masked pages (`previews.render_masked`,
  v3/m2): exactly what an upload's workflow runs, so the unlocked copy is masked as any upload is.
  The decrypted bytes never leave the child. Inside the request (never Temporal: workflow inputs
  and histories are persisted), the results are written as insert-only derived records under one
  `evidence_derivations` row; the evidence version's bytes and fingerprint never change.
  - **Who:** a live person serving their own request (INV-1: never an agent, the system, a
    worker or a support session; never a client principal, INV-4), who may see the version and
    holds `evidence.unlock` on its engagement.
  - **Limit:** five failed attempts per person per version in 15 minutes, counted over the
    `evidence_version.unlock_failed` audit rows under a per-(person, version) advisory lock (no
    Redis, DEC-16); then 429 `unlock_rate_limited` with `retry_after`. Failures are audited by
    count only.
  - **Secret:** the password arrives as a `SecretStr` and is unwrapped only into the child's
    arguments. Nothing about it is logged, audited, stored, emitted or echoed; any exception in
    the child becomes an outcome, so no message crosses the process boundary.
"""

from __future__ import annotations

import asyncio
import io
import math
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal, Protocol, cast
from uuid import UUID

from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.crypto import seal
from abacus.kernel.errors import DomainConflict, DomainInvalid, DomainRateLimited, NotFound
from abacus.kernel.isolation import IsolationFailed, run_isolated
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Scope, Target, audit_actor_count_since, uow
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence import storage
from abacus.modules.evidence.events import EvidenceVersionUnlocked
from abacus.modules.evidence.extraction import PDF
from abacus.modules.evidence.models import EvidenceVersion
from abacus.modules.evidence.object_keys import under_key
from abacus.modules.evidence.pii import (
    DETECTOR_VERSION,
    Found,
    ScanPage,
    scan_layer,
    value_context,
)
from abacus.modules.evidence.previews import (
    MASK_VERSION,
    MASKED_RENDERER_VERSION,
    Rendered,
    render_masked,
)
from abacus.modules.evidence.repository import (
    current_derivation,
    insert_derivation,
    insert_pages,
    insert_pii_regions,
    insert_preview,
    insert_preview_pages,
    insert_scan_run,
)
from abacus.modules.evidence.service import version_view
from abacus.modules.evidence.uploads import (
    UploadView,
    authorise_upload,
    is_staff_on,
    upload,
    uploads_for,
)
from abacus.modules.evidence.viewer import ActiveContent, visible_version
from abacus.modules.evidence.words import WORDS_VERSION, PageWords, extract_words, layer_document
from abacus.modules.identity.api import AuthContext, Forbidden, authorise, serving_request

_log = get_logger(__name__)

MAX_PASSWORD: Final = 256
UNLOCKED_NOTE: Final = "Password removed from the uploaded copy."


class NotLocked(DomainConflict):
    """The file isn't a password-protected PDF."""

    code = "not_locked"


class WrongPassword(DomainInvalid):
    code = "wrong_password"


class UnlockFailed(DomainConflict):
    code = "unlock_failed"


class _Document(Protocol):  # what pypdfium2's stubs leave out of PdfDocument
    def save(self, dest: io.BytesIO, version: int | None = None, flags: int = 0) -> None: ...
    def close(self) -> None: ...


class _Opens(Protocol):
    def __call__(self, content: bytes, *, password: str) -> _Document: ...


Outcome = Literal["unlocked", "wrong_password", "not_locked", "damaged", "active_content"]


def remove_password(content: bytes, password: str) -> tuple[Outcome, bytes]:
    """The PDF without security (`unlocked`), or why not. Runs in the isolated child, so it
    returns an outcome rather than raising across the process boundary."""
    import pypdfium2
    import pypdfium2.raw as pdfium_raw  # pyright: ignore[reportMissingTypeStubs] -- no stubs

    try:
        pypdfium2.PdfDocument(content).close()
    except pypdfium2.PdfiumError as exc:
        if "password" not in str(exc).lower():
            return "damaged", b""
    else:
        return "not_locked", b""
    try:
        document = cast(_Opens, pypdfium2.PdfDocument)(content, password=password)
    except pypdfium2.PdfiumError as exc:
        return ("wrong_password" if "password" in str(exc).lower() else "damaged"), b""
    try:
        out = io.BytesIO()
        document.save(out, flags=pdfium_raw.FPDF_REMOVE_SECURITY)
        return "unlocked", out.getvalue()
    finally:
        document.close()


async def unlock_upload(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, version_id: UUID, password: str
) -> UploadView:
    """A new version of the item: the stored PDF without its password."""
    if not 1 <= len(password) <= MAX_PASSWORD:
        raise WrongPassword("length")
    await authorise_upload(ctx, engagement_id, item_id)
    found = next(
        (
            u
            for u in await uploads_for(ctx, engagement_id, item_id)
            if u.evidence_version_id == version_id
        ),
        None,
    )
    if found is None:
        raise NotFound("evidence_version")
    if found.media_type != PDF:
        raise NotLocked("not_pdf")
    view = await version_view(ctx.tenant, version_id)
    content = await storage.get(ctx.tenant_id, view.stored)
    try:
        outcome, plain = await asyncio.to_thread(run_isolated, remove_password, content, password)
    except IsolationFailed as exc:
        raise UnlockFailed("crashed") from exc
    if outcome == "wrong_password":
        raise WrongPassword("incorrect")
    if outcome == "not_locked":
        raise NotLocked("no_password")
    if outcome != "unlocked":
        raise UnlockFailed(outcome)
    staff = await is_staff_on(ctx, engagement_id)
    return await upload(
        ctx,
        engagement_id,
        item_id,
        file_name=found.file_name,
        content=plain,
        on_behalf=staff,
        note=UNLOCKED_NOTE if staff else None,
    )


# --- Unlock as a derivation (P-03-T19) -------------------------------------------------------

UNLOCK: Final = "evidence.unlock"
UNLOCKED: Final = "evidence_version.unlocked"
UNLOCK_FAILED: Final = "evidence_version.unlock_failed"
UNLOCK_THROTTLED: Final = "evidence_version.unlock_throttled"
DERIVATION_KIND: Final = "password_unlock"
# P-03 AC5.3, C4 §6: five failed unlocks per person per version in fifteen minutes (DEC-425).
UNLOCK_LIMIT: Final = 5
UNLOCK_WINDOW_SECONDS: Final = 15 * 60
_LOCK: Final = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")

UnlockStatus = Literal["ready", "wrong_password"]


class NotPasswordProtected(DomainConflict):
    """The version isn't a password-protected PDF, or it has already been unlocked."""

    code = "not_password_protected"


class UnlockRateLimited(DomainRateLimited):
    """Five unlock attempts on this file failed in fifteen minutes: retry after `retry_after`
    seconds."""

    code = "unlock_rate_limited"


@dataclass(frozen=True)
class Derived:
    """What the unlock's child returns. Never the decrypted file: its words (Restricted, sealed
    when stored), its detected values (Restricted, sealed) and its masked page images."""

    outcome: Outcome
    pages: tuple[PageWords, ...] = ()
    truncated: bool = False
    found: tuple[Found, ...] = ()
    scanned: tuple[int, ...] = ()
    unscannable: tuple[int, ...] = ()
    rendered: Rendered | None = None


def _pt(value: float) -> float:
    """A page side as `evidence_pages` keeps it (numeric(8, 2)), so the scan and the masker read
    the same geometry as an upload's scan does from the stored rows."""
    return float(Decimal(str(value)).quantize(Decimal("0.01")))


def derive_unlocked(content: bytes, password: str) -> Derived:
    """In the isolated child: decrypt, read the word layer, scan it and render masked pages.
    Returns an outcome, never raises: an exception's message could carry anything."""
    try:
        outcome, plain = remove_password(content, password)
        if outcome != "unlocked":
            return Derived(outcome)
        layer = extract_words(plain, PDF)
        if layer.reason == "active_content":
            return Derived("active_content")  # DEC-296: kept, never read or shown
        if layer.status != "extracted":
            return Derived("damaged")
        found, scanned, unscannable = scan_layer(
            [
                ScanPage(
                    p.page,
                    p.words if p.words else None,
                    p.rotation,
                    _pt(p.width),
                    _pt(p.height),
                    p.unread,
                )
                for p in layer.pages
            ]
        )
        masks: dict[int, list[tuple[float, float, float, float]]] = {}
        for f in found:
            masks.setdefault(f.page, []).append(f.box)
        sizes = {p.page: (_pt(p.width), _pt(p.height)) for p in layer.pages}
        rendered = render_masked(plain, PDF, masks, sizes)
        if rendered.kind != "pages" or not rendered.pages:
            return Derived("damaged")
        return Derived(
            "unlocked",
            layer.pages,
            layer.truncated,
            tuple(found),
            tuple(scanned),
            tuple(unscannable),
            rendered,
        )
    except Exception:  # a hostile file: whatever went wrong, only the outcome leaves
        return Derived("damaged")


@dataclass(frozen=True)
class UnlockResult:
    status: UnlockStatus
    attempts_left: int | None
    derivation_id: UUID | None


class _OverLimit(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("over the unlock attempt limit")
        self.retry_after = retry_after


def _human(ctx: AuthContext) -> None:
    """INV-1: only a person, in a request they are making themself, never a support session or a
    client principal (INV-4)."""
    if (
        not isinstance(ctx, AuthContext)  # pyright: ignore[reportUnnecessaryIsInstance] -- ADR-005 at runtime too
        or ctx.tenant.actor_kind != "human"
        or ctx.is_support
        or ctx.client
        or not serving_request()
    ):
        raise Forbidden(UNLOCK, "role")


async def unlock_version(ctx: AuthContext, version_id: UUID, password: SecretStr) -> UnlockResult:
    """AC5.2 to AC5.5: the version's derived, masked pages from the right password; with a wrong
    one, the attempts left. Every refusal comes before the file is read."""
    _human(ctx)
    secret = password.get_secret_value()
    if not 1 <= len(secret) <= MAX_PASSWORD:
        raise DomainInvalid("password")  # the model bounds it too; never echoed
    version = await visible_version(ctx, version_id)  # 403 client, 404 invisible or walled
    engagement = await get_ref(ctx, version.engagement_id)
    await authorise(ctx, UNLOCK, engagement.resource())
    if version.media_type != PDF:
        raise NotPasswordProtected
    stored = storage.StoredObject(
        version.storage_key, version.storage_version_id, version.fingerprint, version.size_bytes
    )
    content = await storage.get(ctx.tenant_id, stored)
    target = Target("evidence_version", version.id)
    scope = Scope(engagement_id=engagement.id)
    try:
        async with uow(ctx.tenant) as tx:
            await tx.session.execute(
                _LOCK, {"key": f"unlock:{ctx.tenant_id}:{ctx.user_id}:{version.id}"}
            )
            failures, oldest, now = await audit_actor_count_since(
                tx.session,
                action=UNLOCK_FAILED,
                target=("evidence_version", version.id),
                actor_id=ctx.tenant.actor_id,
                window_seconds=UNLOCK_WINDOW_SECONDS,
            )
            if failures >= UNLOCK_LIMIT:
                elapsed = (now - oldest).total_seconds() if oldest is not None else 0.0
                raise _OverLimit(max(1, math.ceil(UNLOCK_WINDOW_SECONDS - elapsed)))
            if await current_derivation(tx.session, version.id) is not None:
                raise NotPasswordProtected  # unlocked already: the viewer reads the derivation
            try:
                derived = await asyncio.to_thread(run_isolated, derive_unlocked, content, secret)
            except IsolationFailed as exc:
                raise UnlockFailed("crashed") from exc
            if derived.outcome == "wrong_password":
                attempt = failures + 1
                tx.record(UNLOCK_FAILED, target=target, after=Ref(attempt=attempt), scope=scope)
                _log.info(
                    "evidence.unlock_failed", evidence_version_id=version.id, attempt=attempt
                )
                return UnlockResult("wrong_password", UNLOCK_LIMIT - attempt, None)
            if derived.outcome == "not_locked":
                raise NotPasswordProtected
            if derived.outcome == "active_content":
                raise ActiveContent
            if derived.outcome != "unlocked" or derived.rendered is None:
                raise UnlockFailed(derived.outcome)
            derivation_id = await _store(ctx, tx.session, version, derived, derived.rendered)
            tx.record(UNLOCKED, target=target, after=Ref(derivation_id=derivation_id), scope=scope)
            tx.emit(
                EvidenceVersionUnlocked(
                    evidence_version_id=version.id,
                    engagement_id=engagement.id,
                    derivation_id=derivation_id,
                    unlocked_by=ctx.user_id,
                )
            )
    except _OverLimit as over:
        await _record_throttle(ctx, target, scope)
        raise UnlockRateLimited(
            facts={"limit": UNLOCK_LIMIT, "retry_after": over.retry_after}
        ) from None
    _log.info(
        "evidence.unlocked",
        evidence_version_id=version.id,
        derivation_id=derivation_id,
        pages=len(derived.pages),
        regions=len(derived.found),
    )
    return UnlockResult("ready", None, derivation_id)


async def _store(
    ctx: AuthContext,
    session: AsyncSession,
    version: EvidenceVersion,
    derived: Derived,
    rendered: Rendered,
) -> UUID:
    """The derivation and its records, in the caller's unit of work: the sealed word pages, the
    scan run, the regions (values sealed) and the masked rendition, each with `derivation_id`."""
    tenant_id = ctx.tenant_id
    under = under_key(version)
    derivation_id = uuid.uuid4()
    await insert_derivation(
        session,
        id=derivation_id,
        tenant_id=tenant_id,
        evidence_version_id=version.id,
        kind=DERIVATION_KIND,
        created_by_user_id=ctx.user_id,
        extractor_version=WORDS_VERSION,
        renderer_version=MASKED_RENDERER_VERSION,
        detector_version=DETECTOR_VERSION,
    )
    layer_objects = [
        await storage.put(tenant_id, layer_document(page), under=under) if page.words else None
        for page in derived.pages
    ]
    await insert_pages(
        session,
        [
            {
                "tenant_id": tenant_id,
                "evidence_version_id": version.id,
                "inbox_file_id": None,
                "derivation_id": derivation_id,
                "page_no": page.page,
                "width_pt": Decimal(str(page.width)),
                "height_pt": Decimal(str(page.height)),
                "rotation": page.rotation,
                "has_text_layer": bool(page.words),
                "word_count": len(page.words),
                "text_layer_key": put.key if put else None,
                "text_layer_version_id": put.version_id if put else None,
                "text_layer_fingerprint": put.fingerprint if put else None,
                "text_layer_size": put.size if put else None,
                "ocr_used": False,
                "extractor_version": WORDS_VERSION,
            }
            for page, put in zip(derived.pages, layer_objects, strict=True)
        ],
    )
    await insert_scan_run(
        session,
        tenant_id=tenant_id,
        evidence_version_id=version.id,
        inbox_file_id=None,
        derivation_id=derivation_id,
        detector_version=DETECTOR_VERSION,
        pages_scanned=list(derived.scanned),
        pages_not_scannable=list(derived.unscannable),
        region_count=len(derived.found),
    )
    regions: list[dict[str, object]] = []
    for item in derived.found:
        region_id = uuid.uuid4()
        regions.append(
            {
                "id": region_id,
                "tenant_id": tenant_id,
                "evidence_version_id": version.id,
                "inbox_file_id": None,
                "derivation_id": derivation_id,
                "page_no": item.page,
                "bbox": [Decimal(str(v)) for v in item.box],
                "kind": item.kind,
                "value_sealed": await seal(
                    tenant_id, item.value.encode(), value_context(region_id)
                ),
                "last4": item.last4,
                "label_anchored": item.label_anchored,
                "detector_version": DETECTOR_VERSION,
            }
        )
    await insert_pii_regions(session, regions)
    pngs = [await storage.put(tenant_id, page.png, under=under) for page in rendered.pages]
    preview = await insert_preview(
        session,
        tenant_id=tenant_id,
        engagement_id=version.engagement_id,
        evidence_version_id=version.id,
        inbox_file_id=None,
        derivation_id=derivation_id,
        renderer_version=MASKED_RENDERER_VERSION,
        mask_version=MASK_VERSION,
        kind=rendered.kind,
        reason=rendered.reason,
        page_count=len(pngs),
        truncated=rendered.truncated,
    )
    if preview is None:  # unreachable: the derivation is new, so its rendition is too
        raise UnlockFailed("preview_exists")
    await insert_preview_pages(
        session,
        [
            {
                "tenant_id": tenant_id,
                "preview_id": preview.id,
                "page_no": n,
                "storage_key": put.key,
                "storage_version_id": put.version_id,
                "fingerprint": put.fingerprint,
                "size_bytes": put.size,
                "width": page.width,
                "height": page.height,
            }
            for n, (put, page) in enumerate(zip(pngs, rendered.pages, strict=True), 1)
        ],
    )
    return derivation_id


async def _record_throttle(ctx: AuthContext, target: Target, scope: Scope) -> None:
    """The security record of a refused attempt, in its own unit of work: identifiers only."""
    async with uow(ctx.tenant) as tx:
        tx.record(UNLOCK_THROTTLED, target=target, after=Ref(limit=UNLOCK_LIMIT), scope=scope)
    _log.warning(
        "evidence.unlock_throttled",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        target_id=target.id,
        limit=UNLOCK_LIMIT,
    )
