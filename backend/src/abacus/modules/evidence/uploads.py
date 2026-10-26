"""Client uploads to request items (SPEC-020; TASK-035).

Uploaded files are hostile (ADR-052): the type comes from the leading bytes, never the name or
the request's header (D6); the file name is kept only as length-capped plain text; nothing here
opens, parses or renders a file. Each upload is a new evidence item (titled with the file name)
whose first version has provenance `uploaded` / `client_upload` (ADR-004).
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import re
import unicodedata
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final, cast
from uuid import UUID, uuid4

from abacus.kernel.clock import now, system_now
from abacus.kernel.crypto import DetachedKey
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.isolation import IsolationFailed, Limits, run_isolated_with
from abacus.kernel.scanning import scan
from abacus.kernel.tin_patterns import scrub_tins
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.api import gate_client_data, get_ref, lock_ref, service_line_of
from abacus.modules.evidence import storage
from abacus.modules.evidence.access import record_content_read
from abacus.modules.evidence.active_content import REASON_CODES, UNSCANNABLE, reason_of
from abacus.modules.evidence.citations.matching import words_in
from abacus.modules.evidence.events import EvidenceUploaded
from abacus.modules.evidence.masked_previews import PreviewOutdated
from abacus.modules.evidence.masking import mask_token
from abacus.modules.evidence.models import EvidencePage
from abacus.modules.evidence.pii import masked_rows
from abacus.modules.evidence.previews import MASKED_RENDERER_VERSION, RENDERER_VERSION, TABLE_ROWS
from abacus.modules.evidence.projection import Projection, projection_of
from abacus.modules.evidence.repository import (
    fingerprint_among,
    latest_checks,
    masked_preview_for,
    newest_extraction,
    pages_of,
    preview_for,
    preview_page,
    uploaded_versions,
)
from abacus.modules.evidence.retention import retain_until_for
from abacus.modules.evidence.service import NewItem, Provenance, add_version, version_view
from abacus.modules.evidence.words import WORDS_VERSION, read_page_layer
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    authorise,
    engagement_role_of,
    names_of,
    refuse_unmasked_read,
)
from abacus.modules.requests.api import (
    ItemNotFulfillable,
    RequestItemRef,
    fulfil_by_upload,
    item_ref,
    item_versions,
    items_of_version,
    read_item,
    read_item_versions,
    refuse_closed_item,
    refuse_closed_item_in,
)

MAX_UPLOAD_BYTES: Final = 50 * 1024 * 1024  # DEC-58 (c), DEC-296; was SPEC-020's 25 MB
# The edge lets a file route's body run this far past the limit, so the route answers 422
# `upload_too_large` itself (DEC-296; ED-018): the item upload, the inbox, the setup files and
# the portal drop (R-01-T09).
UPLOAD_EDGE_BYTES: Final = MAX_UPLOAD_BYTES + 1024 * 1024
UPLOAD_ROUTE_PATHS: Final = re.compile(
    r"/v1/(?:engagements/[^/]+/(?:request-items/[^/]+/uploads|inbox|acceptance/file|letter/file)"
    r"|portal/binders/[^/]+/drops)"  # R-01-T09: a portal drop, under the same policy
)
MAX_NAME: Final = 200
SOURCE: Final = "client_upload"

PDF: Final = "application/pdf"
PNG: Final = "image/png"
JPEG: Final = "image/jpeg"
HEIC: Final = "image/heic"
HEIF: Final = "image/heif"
TIFF: Final = "image/tiff"
GIF: Final = "image/gif"
CSV: Final = "text/csv"
XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX: Final = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
OLE: Final = "application/x-ole-storage"  # legacy .xls and .doc: recognised, never allowed
XLSM: Final = "application/vnd.ms-excel.sheet.macroEnabled.12"  # recognised, never allowed
DOCM: Final = "application/vnd.ms-word.document.macroEnabled.12"  # recognised, never allowed
_OLE_MAGIC: Final = bytes.fromhex("d0cf11e0a1b11ae1")
# DEC-58 (c) as decided on 2026-10-24 (DEC-296): what an upload may be, and the extensions that
# agree with each type. The bytes decide the type; the name must agree; anything else is 422.
ALLOWED_TYPES: Final[dict[str, frozenset[str]]] = {
    PDF: frozenset({"pdf"}),
    JPEG: frozenset({"jpg", "jpeg"}),
    PNG: frozenset({"png"}),
    HEIC: frozenset({"heic", "heif"}),
    HEIF: frozenset({"heic", "heif"}),
    TIFF: frozenset({"tif", "tiff"}),
    GIF: frozenset({"gif"}),
    CSV: frozenset({"csv"}),
    XLSX: frozenset({"xlsx"}),
    DOCX: frozenset({"docx"}),
}
# ISO-BMFF `ftyp` brands of HEIC (HEVC-coded) and other HEIF images.
_HEIC_BRANDS: Final = frozenset({b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis"})
_HEIF_BRANDS: Final = frozenset({b"mif1", b"msf1", b"heif"})
_CSV_SAMPLE: Final = 256 * 1024
_CSV_DELIMITERS: Final = (",", ";", "\t", "|")


class UploadTooLarge(DomainInvalid):
    code = "upload_too_large"


class UploadTypeNotAllowed(DomainInvalid):
    code = "upload_type_not_allowed"


class UploadEmpty(DomainInvalid):
    code = "upload_empty"


class UploadRefused(DomainInvalid):
    """The malware scanner refused the file (SPEC-029 AC-1; ADR-110). Nothing is stored."""

    code = "file_refused"


class DuplicateUpload(DomainConflict):
    """The same file (same SHA-256) is already on this item."""

    code = "duplicate_upload"


class ItemClosed(DomainConflict):
    """The item no longer takes evidence (ready for review or further on)."""

    code = "item_closed"


def sniff(content: bytes) -> str | None:
    """The media type the content is, judged by its bytes alone (D6), or None. Legacy OLE and
    macro-enabled Office files are recognised so they can be named in a refusal; `allowed_type`
    decides what may be kept."""
    if content.startswith(b"%PDF-"):
        return PDF
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if content.startswith(b"\xff\xd8\xff"):
        return JPEG
    if content.startswith((b"GIF87a", b"GIF89a")):
        return GIF
    if content.startswith((b"II*\x00", b"MM\x00*")):
        return TIFF
    if content[4:8] == b"ftyp":
        return _heif(content)
    if content.startswith(_OLE_MAGIC):
        return OLE
    if content.startswith(b"PK\x03\x04"):
        return _ooxml(content)
    return CSV if _is_csv(content) else None


def _heif(content: bytes) -> str | None:
    """An ISO-BMFF file whose major or compatible brands are HEIC or HEIF (a phone photo)."""
    size = int.from_bytes(content[:4], "big")
    box = content[8 : max(16, min(size, 256))]
    brands = {box[i : i + 4] for i in range(0, len(box) - 3, 4) if i != 4}
    if brands & _HEIC_BRANDS:
        return HEIC
    if brands & _HEIF_BRANDS:
        return HEIF
    return None


_XML_PART_LIMIT: Final = 1024 * 1024  # [Content_Types].xml and each .rels part
_MAX_RELS: Final = 200
_CONTENT_TYPE: Final = re.compile(rb"ContentType\s*=\s*[\"']([^\"']{1,255})[\"']", re.IGNORECASE)
_EXTERNAL: Final = re.compile(rb"TargetMode\s*=\s*[\"']\s*External\s*[\"']", re.IGNORECASE)
_RELATIONSHIP: Final = re.compile(
    rb"<\s*(?:[A-Za-z_][\w.-]*:)?Relationship\b[^>]*>", re.IGNORECASE
)
_REL_TYPE: Final = re.compile(rb"\bType\s*=\s*[\"']([^\"']{1,512})[\"']", re.IGNORECASE)
# The one external relationship a client's workbook or document ordinarily carries: a hyperlink
# (DEC-299). Remote templates, OLE links, frames, sub-documents and external workbook links stay
# refused, and so does any external relationship that names no type.
_HYPERLINK: Final = b"/relationships/hyperlink"
# Content types that carry code or embedded objects (DEC-299): macro-enabled parts, VBA projects,
# macro sheets, ActiveX controls and OLE objects.
_ACTIVE_TYPES: Final = ("macroenabled", "vba", "macrosheet", "activex", "oleobject")
_ACTIVE_PARTS: Final = ("vbaproject", "vbadata", "/activex/", "oleobject", "macrosheets/")


def _bounded(package: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes | None:
    """A small XML part's bytes, or None when it is (or inflates) past the bound."""
    if info.file_size > _XML_PART_LIMIT:
        return None
    with package.open(info) as part:
        data = part.read(_XML_PART_LIMIT + 1)
    return data if len(data) <= _XML_PART_LIMIT else None


def _external_code(rels: bytes) -> bool:
    """Whether a relationship part has an external target other than a plain hyperlink."""
    for element in _RELATIONSHIP.findall(rels):
        if _EXTERNAL.search(element) is None:
            continue
        kind = _REL_TYPE.search(element)
        if kind is None or not kind.group(1).lower().endswith(_HYPERLINK):
            return True
    return False


def _ooxml(content: bytes) -> str | None:
    """An Office Open XML package: a zip with `[Content_Types].xml` and a workbook or document
    part. Only the central directory, `[Content_Types].xml` and the relationship parts are read,
    each bounded; no other member is extracted. A package carrying code or embedded objects (a
    macro-enabled, VBA, macro-sheet, ActiveX or OLE content type or part, in any letter case) or
    any external relationship other than a hyperlink (`TargetMode="External"`: how remote-template
    macros arrive) is the macro-enabled type, whatever it is named (DEC-299)."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as package:
            infos = package.infolist()
            names = {i.filename for i in infos}
            if "[Content_Types].xml" not in names:
                return None
            folded = [n.casefold() for n in names]
            active = any(marker in n for n in folded for marker in _ACTIVE_PARTS)
            types = _bounded(package, package.getinfo("[Content_Types].xml"))
            if types is None:
                active = True
            else:
                declared = [t.decode("latin-1").casefold() for t in _CONTENT_TYPE.findall(types)]
                active = active or any(m in t for t in declared for m in _ACTIVE_TYPES)
            rels = [i for i in infos if i.filename.casefold().endswith(".rels")]
            if len(rels) > _MAX_RELS:
                active = True
            for info in rels[:_MAX_RELS]:
                if active:
                    break
                data = _bounded(package, info)
                active = data is None or _external_code(data)
    except (zipfile.BadZipFile, ValueError, OSError, RuntimeError, EOFError):
        return None
    if "xl/workbook.xml" in folded:
        return XLSM if active else XLSX
    if "word/document.xml" in folded:
        return DOCM if active else DOCX
    return None


def _is_text(content: bytes) -> bool:
    if b"\x00" in content:
        return False
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _is_csv(content: bytes) -> bool:
    """UTF-8 text that parses as CSV (DEC-296): not markup (HTML, SVG, XML start with `<`), and
    its first rows read strictly with one of the usual delimiters, at least one row holding two
    or more fields. Other text (a script, prose) is not kept as `text/csv`."""
    if not _is_text(content):
        return False
    text = content[:_CSV_SAMPLE].decode("utf-8", errors="ignore").lstrip("\ufeff")
    stripped = text.lstrip()
    if not stripped or stripped.startswith("<"):
        return False
    if len(content) > _CSV_SAMPLE:  # the sample may end mid-row
        text = text[: text.rfind("\n") + 1] or text
    for delimiter in _CSV_DELIMITERS:
        try:
            rows = list(csv.reader(io.StringIO(text), delimiter=delimiter, strict=True))
        except csv.Error:
            continue
        if any(len(row) >= 2 for row in rows):
            return True
    return False


def extension_of(file_name: str) -> str:
    """The name's extension, lower case, after the name is cleaned; "" without one."""
    base = clean_name(file_name)
    return base.rsplit(".", 1)[-1].casefold() if "." in base.strip(".") else ""


def allowed_type(content: bytes, file_name: str | None) -> str:
    """DEC-58 (c) and DEC-296: the bytes decide the type, it must be one of `ALLOWED_TYPES`, and
    the file's extension must agree with it (None: a caller with no client-given name). Raises
    `UploadTypeNotAllowed` otherwise."""
    media_type = sniff(content)
    if media_type is None or media_type not in ALLOWED_TYPES:
        raise UploadTypeNotAllowed
    if file_name is not None and extension_of(file_name) not in ALLOWED_TYPES[media_type]:
        raise UploadTypeNotAllowed
    return media_type


def clean_name(name: str) -> str:
    """The file name as plain text: no path, no control characters, at most 200 characters."""
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    kept = "".join(ch for ch in base if unicodedata.category(ch)[0] != "C").strip()
    return kept[:MAX_NAME] or "Untitled file"


@dataclass(frozen=True)
class UploadView:
    evidence_version_id: UUID
    file_name: str
    media_type: str
    size_bytes: int
    uploaded_by: UUID | None
    uploaded_by_name: str
    uploaded_at: datetime
    # SPEC-023: added by the firm for the client, and where it came from.
    on_behalf: bool = False
    note: str | None = None


ON_BEHALF_SOURCE: Final = "firm_upload_for_client"
MAX_NOTE: Final = 500
_STAFF_ROLES: Final = frozenset({"engagement_partner", "manager", "senior", "staff", "reviewer"})


class NotStaff(DomainConflict):
    """Only the firm's team can add files on the client's behalf (SPEC-023 AC-1)."""

    code = "not_staff"


def clean_note(note: str | None) -> str | None:
    """Plain text, control characters removed, at most 500 characters; empty means none."""
    if note is None:
        return None
    kept = "".join(ch for ch in note if unicodedata.category(ch)[0] != "C" or ch == " ").strip()
    return kept[:MAX_NOTE] or None


async def is_staff_on(ctx: AuthContext, engagement_id: UUID) -> bool:
    return await engagement_role_of(ctx.tenant, engagement_id, ctx.user_id) in _STAFF_ROLES


def item_resource(item: RequestItemRef, base: Resource) -> Resource:
    return Resource.engagement(
        base.tenant_id,
        item.engagement_id,
        archived=base.archived,
        client_id=base.client_id,
        item=item.facts,
    )


async def authorise_upload(ctx: AuthContext, engagement_id: UUID, item_id: UUID) -> None:
    """`evidence.upload` with the item's facts (SPEC-020)."""
    engagement = await get_ref(ctx, engagement_id)
    item = await read_item(ctx.tenant, engagement_id, item_id)
    await authorise(ctx, "evidence.upload", item_resource(item, engagement.resource()))
    await refuse_closed_item(ctx, item_id)  # ED-118: a closed binder is read-only (DEC-461)


async def check_upload(ctx: AuthContext, engagement_id: UUID, item_id: UUID) -> None:
    """Authorise before the body is read, so a stranger can't make the server take 50 MB."""
    await authorise_upload(ctx, engagement_id, item_id)


def checked(content: bytes, file_name: str | None = None) -> tuple[str, str]:
    """The content's allowed media type and fingerprint, or the AC-9 refusal (DEC-296: the
    name's extension must agree with the bytes; None only for a caller with no client name)."""
    if not content:
        raise UploadEmpty
    if len(content) > MAX_UPLOAD_BYTES:
        raise UploadTooLarge
    # SPEC-029 AC-1: scanned before anything stores or parses it. Malware is answered as
    # malware whatever it claims to be; any other scan refusal (an unreadable archive) of a file
    # whose type is refused anyway is answered as the type refusal (DEC-296).
    verdict = scan(content)
    try:
        media_type = allowed_type(content, file_name)
    except UploadTypeNotAllowed:
        if not verdict.clean and verdict.reason == "malware":
            raise UploadRefused from None
        raise
    if not verdict.clean:
        raise UploadRefused
    return media_type, storage.fingerprint(content)


@dataclass(frozen=True)
class Screened:
    media_type: str
    fingerprint: str
    # DEC-296 (ED-021): why a PDF carries active content, or None. Stored, never derived from.
    active_content: str | None


# DEC-299: the active-content scan runs in a child of its own, bounded, never on the shared
# thread pool's CPU; a scan that dies or overruns is a flagged file (fail closed).
SCAN_LIMITS: Final = Limits(timeout_seconds=20, cpu_seconds=15)


def active_content_of(content: bytes) -> str | None:
    try:
        return run_isolated_with(SCAN_LIMITS, reason_of, content)
    except IsolationFailed:
        return UNSCANNABLE
    except Exception:  # anything the child didn't turn into a result
        return UNSCANNABLE


def _screen(content: bytes, file_name: str) -> Screened:
    media_type, digest = checked(content, file_name)
    flag = active_content_of(content) if media_type == PDF else None
    return Screened(media_type, digest, flag)


async def screened(
    ctx: AuthContext, engagement_id: UUID, content: bytes, file_name: str
) -> Screened:
    """`checked`, off the event loop, auditing a refused file (SPEC-029 AC-1): nothing is
    stored, and only the size is recorded."""
    try:
        return await asyncio.to_thread(_screen, content, file_name)
    except UploadRefused:
        async with uow(ctx.tenant) as tx:
            tx.record(
                "upload.refused",
                target=Target("engagement", engagement_id),
                after=Ref(size=len(content)),
            )
        raise


async def attach(
    tx: UnitOfWork,
    ctx: AuthContext,
    *,
    engagement_id: UUID,
    item_id: UUID,
    stored: storage.StoredObject,
    name: str,
    media_type: str,
    source: str,
    note: str | None,
    active_content: str | None = None,
    detached: tuple[UUID, DetachedKey] | None = None,
) -> UUID:
    """Inside the caller's unit of work: re-check the item (its facts may have changed), refuse
    a closed item or a duplicate, add the version, link it and announce it. Shared by uploads
    and inbox assignment (SPEC-023)."""
    locked_engagement = await lock_ref(tx, engagement_id)
    locked = await item_ref(tx, item_id, lock=True)
    if locked.engagement_id != engagement_id:
        raise NotFound("request_item")
    await authorise(ctx, "evidence.upload", item_resource(locked, locked_engagement.resource()))
    await refuse_closed_item_in(tx.session, ctx, item_id)  # ED-118 (DEC-461)
    if locked.status not in ("draft", "requested", "uploaded", "returned"):
        raise ItemClosed
    if await fingerprint_among(tx.session, await item_versions(tx, item_id), stored.fingerprint):
        raise DuplicateUpload
    version = await add_version(
        tx,
        engagement_id=engagement_id,
        item=NewItem(title=name),
        stored=stored,
        media_type=media_type,
        provenance=Provenance(source=source, method="uploaded"),
        requested_by=ctx.user_id,
        upload_note=note,
        detached=detached,
    )
    try:
        await fulfil_by_upload(tx, request_item_id=item_id, evidence_version_id=version.id)
    except ItemNotFulfillable:
        raise ItemClosed from None
    tx.record(
        "evidence.uploaded",
        target=Target("evidence_version", version.id),
        after=Ref(request_item_id=item_id, fingerprint=stored.fingerprint, size=stored.size),
    )
    if active_content is not None:  # DEC-296: kept, flagged for the team, never derived from
        tx.record(
            "evidence_version.flagged",
            target=Target("evidence_version", version.id),
            after=Ref(reason=REASON_CODES[active_content]),
        )
    tx.emit(
        EvidenceUploaded(
            engagement_id=engagement_id,
            request_item_id=item_id,
            evidence_version_id=version.id,
            uploaded_by=ctx.user_id,
        )
    )
    return version.id


async def upload(
    ctx: AuthContext,
    engagement_id: UUID,
    item_id: UUID,
    *,
    file_name: str,
    content: bytes,
    on_behalf: bool = False,
    note: str | None = None,
) -> UploadView:
    """Store a file as new evidence on the item (SPEC-020 AC-8, AC-9). On the client's behalf
    (SPEC-023 AC-1), only the firm's team may, with an optional note."""
    await authorise_upload(ctx, engagement_id, item_id)
    await gate_client_data(ctx, engagement_id, "evidence.upload")  # SPEC-025 AC-7
    if on_behalf and not await is_staff_on(ctx, engagement_id):
        raise NotStaff
    found = await screened(ctx, engagement_id, content, file_name)
    media_type, digest = found.media_type, found.fingerprint
    async with tenant_session(ctx.tenant) as session:
        if await fingerprint_among(session, await read_item_versions(ctx.tenant, item_id), digest):
            raise DuplicateUpload
    # Q-02-T24: locked at least until the client document's policy expiry, anchored at upload
    # for now (provisional; an anchor event extends it later).
    keep = await retain_until_for(
        ctx.tenant,
        "client_document",
        await service_line_of(ctx.tenant, engagement_id) or "any",
        system_now(),
    )
    # ADR-162 §5 (P-06-T18): a client's own upload is stored in detached-key mode, so it can be
    # withdrawn and crypto-erased; the firm's uploads stay content-addressed.
    detached: tuple[UUID, DetachedKey] | None = None
    if ctx.client and not on_behalf:
        new_id = uuid4()
        stored, key = await storage.put_detached(ctx.tenant_id, new_id, content, retain_until=keep)
        detached = (new_id, key)
    else:
        stored = await storage.put(ctx.tenant_id, content, retain_until=keep)
    name = clean_name(file_name)
    kept_note = clean_note(note) if on_behalf else None
    async with uow(ctx.tenant) as tx:
        version_id = await attach(
            tx,
            ctx,
            engagement_id=engagement_id,
            item_id=item_id,
            stored=stored,
            name=name,
            media_type=media_type,
            source=ON_BEHALF_SOURCE if on_behalf else SOURCE,
            note=kept_note,
            active_content=found.active_content,
            detached=detached,
        )
    names = await names_of([ctx.user_id])
    return UploadView(
        version_id,
        name,
        media_type,
        len(content),
        ctx.user_id,
        names.get(ctx.user_id, ""),
        await now(ctx.tenant),
        on_behalf,
        kept_note,
    )


async def uploads_for(ctx: AuthContext, engagement_id: UUID, item_id: UUID) -> list[UploadView]:
    """The item's uploads, newest first, for anyone allowed `evidence.read` on it."""
    engagement = await get_ref(ctx, engagement_id)
    item = await read_item(ctx.tenant, engagement_id, item_id)
    await authorise(ctx, "evidence.read", item_resource(item, engagement.resource()))
    async with tenant_session(ctx.tenant) as session:
        rows = await uploaded_versions(session, await read_item_versions(ctx.tenant, item_id))
    uploaders = [_user(evidence_item.created_by_id) for _, evidence_item in rows]
    names = await names_of(sorted({u for u in uploaders if u is not None}, key=str))
    return [
        UploadView(
            version.id,
            evidence_item.title,
            version.media_type,
            version.size_bytes,
            uploader,
            names.get(uploader, "") if uploader is not None else "",
            version.created_at,
            version.source == ON_BEHALF_SOURCE,
            version.upload_note,
        )
        for (version, evidence_item), uploader in zip(rows, uploaders, strict=True)
    ]


def _user(actor_id: str) -> UUID | None:
    try:
        return UUID(actor_id)
    except ValueError:
        return None


# --- Checks (SPEC-029; TASK-055) -----------------------------------------------------------------

_CLIENT_ROLES: Final = frozenset({"client_admin", "client_contributor"})


@dataclass(frozen=True)
class CheckView:
    code: str
    outcome: str
    audience: str
    document_kind: str | None
    reason: str | None
    expected_date: date | None
    found_date: date | None
    amount: Decimal | None
    difference: Decimal | None
    account_code: str | None
    ref_item_id: UUID | None


async def upload_checks(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, version_id: UUID
) -> list[CheckView]:
    """The latest checks of one of the item's uploads, for anyone allowed `evidence.read` on the
    item. Client roles get only client-audience checks (SPEC-029 AC-10, Q3): enforced here, so
    no screen can show a client a firm check."""
    engagement = await get_ref(ctx, engagement_id)
    item = await read_item(ctx.tenant, engagement_id, item_id)
    await authorise(ctx, "evidence.read", item_resource(item, engagement.resource()))
    if version_id not in await read_item_versions(ctx.tenant, item_id):
        raise NotFound("evidence_version")
    client = await engagement_role_of(ctx.tenant, engagement_id, ctx.user_id) in _CLIENT_ROLES
    async with tenant_session(ctx.tenant) as session:
        rows = await latest_checks(session, version_id)
    return [
        CheckView(
            r.check_code,
            r.outcome,
            r.audience,
            r.document_kind,
            r.reason,
            r.expected_date,
            r.found_date,
            r.amount,
            r.difference,
            r.account_code,
            r.ref_item_id,
        )
        for r in rows
        if not client or r.audience == "client"
    ]


# --- Previews (SPEC-029 goal 8; TASK-056) --------------------------------------------------------


@dataclass(frozen=True)
class PreviewView:
    kind: str  # pages | image | table | none; "pending" while the workflow hasn't made it yet
    reason: str | None
    page_count: int
    truncated: bool
    sheets: tuple[tuple[str, tuple[tuple[str, ...], ...]], ...] = ()
    # TASK-334: each PDF page's printed lines and their boxes, to point at where a value was.
    page_lines: tuple[tuple[tuple[str, tuple[float, float, float, float]], ...], ...] = ()


async def _authorised_version(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, version_id: UUID
) -> None:
    """`evidence.read` on the item with its client facts, and the version fulfils it."""
    engagement = await get_ref(ctx, engagement_id)
    item = await read_item(ctx.tenant, engagement_id, item_id)
    await authorise(ctx, "evidence.read", item_resource(item, engagement.resource()))
    if version_id not in await read_item_versions(ctx.tenant, item_id):
        raise NotFound("evidence_version")


async def preview_of(
    tenant: TenantContext, *, evidence_version_id: UUID | None, inbox_file_id: UUID | None
) -> PreviewView:
    """For a caller that has authorised on the upload: the viewer's description, from the masked
    rendition when there is one (P-03-T15), with a spreadsheet's first rows and a PDF's printed
    lines as a reader may see them: masked by code, and lines only for pages a PII scan covers
    (fail closed; DEC-369)."""
    async with tenant_session(tenant) as session:
        found = await masked_preview_for(
            session,
            evidence_version_id,
            inbox_file_id=inbox_file_id,
            renderer_version=MASKED_RENDERER_VERSION,
        ) or await preview_for(
            session,
            evidence_version_id=evidence_version_id,
            inbox_file_id=inbox_file_id,
            renderer_version=RENDERER_VERSION,
        )
        extracted = await newest_extraction(
            session, evidence_version_id=evidence_version_id, inbox_file_id=inbox_file_id
        )
        projection = await projection_of(
            session, evidence_version_id=evidence_version_id, inbox_file_id=inbox_file_id
        )
        layer = await pages_of(
            session,
            evidence_version_id=evidence_version_id,
            inbox_file_id=inbox_file_id,
            extractor_version=WORDS_VERSION,
        )
    if found is None:
        return PreviewView("pending", None, 0, False)
    sheets: tuple[tuple[str, tuple[tuple[str, ...], ...]], ...] = ()
    truncated = found.truncated
    if found.kind == "pages" and extracted is not None and extracted.storage_key is not None:
        stored = storage.StoredObject(
            extracted.storage_key,
            extracted.storage_version_id or "",
            extracted.fingerprint or "",
            extracted.size_bytes or 0,
        )
        document = json.loads(await storage.get(tenant.tenant_id, stored))
        lines = await masked_page_lines(
            tenant.tenant_id, page_lines_of(document), projection, layer
        )
        return PreviewView(found.kind, found.reason, found.page_count, truncated, (), lines)
    if found.kind == "table" and extracted is not None and extracted.storage_key is not None:
        stored = storage.StoredObject(
            extracted.storage_key,
            extracted.storage_version_id or "",
            extracted.fingerprint or "",
            extracted.size_bytes or 0,
        )
        document = json.loads(await storage.get(tenant.tenant_id, stored))
        tables = cast(list[dict[str, object]], document.get("tables") or [])
        built: list[tuple[str, tuple[tuple[str, ...], ...]]] = []
        for table in tables:
            rows = cast(list[list[object]], table.get("rows") or [])
            truncated = truncated or len(rows) > TABLE_ROWS
            shown = [tuple(str(c) for c in row) for row in rows[:TABLE_ROWS]]
            built.append((str(table.get("sheet") or ""), masked_rows(shown)))
        sheets = tuple(built)
    return PreviewView(found.kind, found.reason, found.page_count, truncated, sheets)


Line = tuple[str, tuple[float, float, float, float]]
_EDGE_PUNCTUATION: Final = re.compile(r"^[^0-9A-Za-z]+|[^0-9A-Za-z]+$")


def _plain(token: str) -> str:
    """A printed token without the punctuation around it, for matching across extractors."""
    return _EDGE_PUNCTUATION.sub("", unicodedata.normalize("NFKC", token))


async def masked_page_lines(
    tenant_id: UUID,
    pages: tuple[tuple[Line, ...], ...],
    projection: Projection,
    layer: Sequence[EvidencePage],
) -> tuple[tuple[Line, ...], ...]:
    """The extraction's printed lines as a reader may see them (P-03-T15; DEC-369): none for a
    page no PII scan covers or one with a `/Rotate` (its lines are read in another order and
    frame than the word layer's; fail closed). On the rest, every word a detected region covers
    in the word layer is replaced by that region's token wherever the line prints it (matched by
    text without edge punctuation, so the extraction's own geometry is never trusted), every line
    goes through the kernel's TIN scrub, and a page where some region's word can't be found as a
    token has no lines at all (review L4)."""
    by_page = {p.page_no: p for p in layer}
    out: list[tuple[Line, ...]] = []
    for number, lines in enumerate(pages, start=1):
        page = by_page.get(number)
        if page is None or page.rotation != 0 or not projection.readable(number):
            out.append(())
            continue
        regions = [r for r in projection.regions if r.page_no == number]
        tokens: dict[str, str] = {}
        if regions:
            raw = (await read_page_layer(tenant_id, page)).words
            for region in regions:
                for word in words_in(raw, region.box):
                    tokens[_plain(word.text)] = mask_token(region.kind, region.last4)
        kept: list[Line] = []
        seen: set[str] = set()
        for text, box in lines:
            parts: list[str] = []
            for part in text.split():
                key = _plain(part)
                if key in tokens:
                    seen.add(key)
                    parts.append(tokens[key])
                else:
                    parts.append(part)
            kept.append((scrub_tins(" ".join(parts)), box))
        # Review L4: a region's word the lines don't print as a token (split or joined
        # differently) could still be in them in the clear: the page's lines are left out.
        out.append(tuple(kept) if seen == set(tokens) else ())
    return tuple(out)


def page_lines_of(
    document: dict[str, object],
) -> tuple[tuple[tuple[str, tuple[float, float, float, float]], ...], ...]:
    """The extraction's line boxes (v3 and later); earlier extractions have none."""
    pages = cast(list[list[dict[str, object]]], document.get("page_lines") or [])
    out: list[tuple[tuple[str, tuple[float, float, float, float]], ...]] = []
    for lines in pages:
        kept: list[tuple[str, tuple[float, float, float, float]]] = []
        for line in lines:
            box = cast(list[float], line.get("box") or [])
            if len(box) == 4:
                kept.append((str(line.get("text") or ""), (box[0], box[1], box[2], box[3])))
        out.append(tuple(kept))
    return tuple(out)


async def preview_page_of(
    tenant: TenantContext,
    *,
    evidence_version_id: UUID | None,
    inbox_file_id: UUID | None,
    page_no: int,
) -> bytes:
    """One server-made PNG of the masked rendition only (P-03-T15; SPEC-322 AC-24), verified
    against its fingerprint by storage: 409 `preview_outdated` while only a pre-masking preview
    exists (until the backfill re-renders it), 404 when nothing is rendered."""
    async with tenant_session(tenant) as session:
        found = await masked_preview_for(
            session,
            evidence_version_id,
            inbox_file_id=inbox_file_id,
            renderer_version=MASKED_RENDERER_VERSION,
        )
        if found is None:
            legacy = await preview_for(
                session,
                evidence_version_id=evidence_version_id,
                inbox_file_id=inbox_file_id,
                renderer_version=RENDERER_VERSION,
            )
            if legacy is not None and legacy.kind in ("pages", "image"):
                raise PreviewOutdated
            raise NotFound("preview_page")
        page = await preview_page(session, found.id, page_no)
    if page is None:
        raise NotFound("preview_page")
    stored = storage.StoredObject(
        page.storage_key, page.storage_version_id, page.fingerprint, page.size_bytes
    )
    return await storage.get(tenant.tenant_id, stored)


async def upload_preview(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, version_id: UUID
) -> PreviewView:
    await _authorised_version(ctx, engagement_id, item_id, version_id)
    await refuse_unmasked_read(ctx, "evidence.read")  # `page_lines` is raw text (DEC-52)
    return await preview_of(ctx.tenant, evidence_version_id=version_id, inbox_file_id=None)


async def upload_preview_page(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, version_id: UUID, page_no: int
) -> bytes:
    await _authorised_version(ctx, engagement_id, item_id, version_id)
    await refuse_unmasked_read(ctx, "evidence.read")  # an unmasked page image (DEC-52)
    page = await preview_page_of(
        ctx.tenant, evidence_version_id=version_id, inbox_file_id=None, page_no=page_no
    )
    await record_content_read(ctx, engagement_id, "evidence_version", version_id)
    return page


# --- A version's preview without its request (TASK-334) ---------------------------------------


async def _authorised_any_version(ctx: AuthContext, engagement_id: UUID, version_id: UUID) -> None:
    """`evidence.read` through a request item the version fulfils, or on the engagement for a
    version no item holds (retrieved ledgers); the version must be the engagement's."""
    items = await items_of_version(ctx.tenant, version_id)
    if items:
        await _authorised_version(ctx, engagement_id, items[0].id, version_id)
        return
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, "evidence.read", engagement.resource())
    if (await version_view(ctx.tenant, version_id)).engagement_id != engagement_id:
        raise NotFound("evidence_version")


async def version_preview(ctx: AuthContext, engagement_id: UUID, version_id: UUID) -> PreviewView:
    await _authorised_any_version(ctx, engagement_id, version_id)
    await refuse_unmasked_read(ctx, "evidence.read")  # `page_lines` is raw text (DEC-52)
    return await preview_of(ctx.tenant, evidence_version_id=version_id, inbox_file_id=None)


async def version_preview_page(
    ctx: AuthContext, engagement_id: UUID, version_id: UUID, page_no: int
) -> bytes:
    await _authorised_any_version(ctx, engagement_id, version_id)
    await refuse_unmasked_read(ctx, "evidence.read")  # an unmasked page image (DEC-52)
    page = await preview_page_of(
        ctx.tenant, evidence_version_id=version_id, inbox_file_id=None, page_no=page_no
    )
    await record_content_read(ctx, engagement_id, "evidence_version", version_id)
    return page
