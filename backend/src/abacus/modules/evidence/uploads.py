"""Client uploads to request items (SPEC-020; TASK-035).

Uploaded files are hostile (ADR-052): the type comes from the leading bytes, never the name or
the request's header (D6); the file name is kept only as length-capped plain text; nothing here
opens, parses or renders a file. Each upload is a new evidence item (titled with the file name)
whose first version has provenance `uploaded` / `client_upload` (ADR-004).
"""

from __future__ import annotations

import io
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.evidence import storage
from abacus.modules.evidence.events import EvidenceUploaded
from abacus.modules.evidence.repository import fingerprint_among, uploaded_versions
from abacus.modules.evidence.service import NewItem, Provenance, add_version
from abacus.modules.identity.api import AuthContext, Resource, authorise, names_of
from abacus.modules.requests.api import (
    ItemNotFulfillable,
    RequestItemRef,
    fulfil_by_upload,
    item_ref,
    item_versions,
    read_item,
    read_item_versions,
)

MAX_UPLOAD_BYTES: Final = 25 * 1024 * 1024
MAX_NAME: Final = 200
SOURCE: Final = "client_upload"

PDF: Final = "application/pdf"
PNG: Final = "image/png"
JPEG: Final = "image/jpeg"
CSV: Final = "text/csv"
XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX: Final = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
OLE: Final = "application/x-ole-storage"  # legacy .xls and .doc
_OLE_MAGIC: Final = bytes.fromhex("d0cf11e0a1b11ae1")


class UploadTooLarge(DomainInvalid):
    code = "upload_too_large"


class UploadTypeNotAllowed(DomainInvalid):
    code = "upload_type_not_allowed"


class UploadEmpty(DomainInvalid):
    code = "upload_empty"


class DuplicateUpload(DomainConflict):
    """The same file (same SHA-256) is already on this item."""

    code = "duplicate_upload"


class ItemClosed(DomainConflict):
    """The item no longer takes evidence (ready for review or further on)."""

    code = "item_closed"


def sniff(content: bytes) -> str | None:
    """The allowed media type the content is, judged by its bytes alone (D6), or None."""
    if content.startswith(b"%PDF-"):
        return PDF
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if content.startswith(b"\xff\xd8\xff"):
        return JPEG
    if content.startswith(_OLE_MAGIC):
        return OLE
    if content.startswith(b"PK\x03\x04"):
        return _ooxml(content)
    return CSV if _is_text(content) else None


def _ooxml(content: bytes) -> str | None:
    """An Office Open XML package: a zip with `[Content_Types].xml` and a workbook or document
    part. Only the central directory is read; no member is extracted."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as package:
            names = set(package.namelist())
    except (zipfile.BadZipFile, ValueError):
        return None
    if "[Content_Types].xml" not in names:
        return None
    if "xl/workbook.xml" in names:
        return XLSX
    if "word/document.xml" in names:
        return DOCX
    return None


def _is_text(content: bytes) -> bool:
    if b"\x00" in content:
        return False
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


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


def _resource(item: RequestItemRef, base: Resource) -> Resource:
    return Resource.engagement(
        base.tenant_id,
        item.engagement_id,
        archived=base.archived,
        client_id=base.client_id,
        item=item.facts,
    )


async def check_upload(ctx: AuthContext, engagement_id: UUID, item_id: UUID) -> None:
    """Authorise before the body is read, so a stranger can't make the server take 25 MB."""
    engagement = await get_ref(ctx, engagement_id)
    item = await read_item(ctx.tenant, engagement_id, item_id)
    await authorise(ctx, "evidence.upload", _resource(item, engagement.resource()))


async def upload(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, *, file_name: str, content: bytes
) -> UploadView:
    """Store a client's file as new evidence on the item (AC-8), or refuse it (AC-9)."""
    engagement = await get_ref(ctx, engagement_id)
    item = await read_item(ctx.tenant, engagement_id, item_id)
    await authorise(ctx, "evidence.upload", _resource(item, engagement.resource()))
    if not content:
        raise UploadEmpty
    if len(content) > MAX_UPLOAD_BYTES:
        raise UploadTooLarge
    media_type = sniff(content)
    if media_type is None:
        raise UploadTypeNotAllowed
    digest = storage.fingerprint(content)
    async with tenant_session(ctx.tenant) as session:
        if await fingerprint_among(session, await read_item_versions(ctx.tenant, item_id), digest):
            raise DuplicateUpload
    stored = await storage.put(ctx.tenant_id, content)
    name = clean_name(file_name)
    async with uow(ctx.tenant) as tx:
        locked_engagement = await lock_ref(tx, engagement_id)
        locked = await item_ref(tx, item_id, lock=True)
        # Facts may have changed since the first check (hidden, reassigned): check again.
        await authorise(ctx, "evidence.upload", _resource(locked, locked_engagement.resource()))
        if locked.status not in ("open", "received", "needs_revision"):
            raise ItemClosed
        if await fingerprint_among(tx.session, await item_versions(tx, item_id), digest):
            raise DuplicateUpload
        version = await add_version(
            tx,
            engagement_id=engagement_id,
            item=NewItem(title=name),
            stored=stored,
            media_type=media_type,
            provenance=Provenance(source=SOURCE, method="uploaded"),
            requested_by=ctx.user_id,
        )
        try:
            await fulfil_by_upload(tx, request_item_id=item_id, evidence_version_id=version.id)
        except ItemNotFulfillable:
            raise ItemClosed from None
        tx.record(
            "evidence.uploaded",
            target=Target("evidence_version", version.id),
            after=Ref(request_item_id=item_id, fingerprint=digest, size=len(content)),
        )
        tx.emit(
            EvidenceUploaded(
                engagement_id=engagement_id,
                request_item_id=item_id,
                evidence_version_id=version.id,
                uploaded_by=ctx.user_id,
            )
        )
    names = await names_of([ctx.user_id])
    return UploadView(
        version.id,
        name,
        media_type,
        len(content),
        ctx.user_id,
        names.get(ctx.user_id, ""),
        datetime.now(UTC),
    )


async def uploads_for(ctx: AuthContext, engagement_id: UUID, item_id: UUID) -> list[UploadView]:
    """The item's uploads, newest first, for anyone allowed `evidence.read` on it."""
    engagement = await get_ref(ctx, engagement_id)
    item = await read_item(ctx.tenant, engagement_id, item_id)
    await authorise(ctx, "evidence.read", _resource(item, engagement.resource()))
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
        )
        for (version, evidence_item), uploader in zip(rows, uploaders, strict=True)
    ]


def _user(actor_id: str) -> UUID | None:
    try:
        return UUID(actor_id)
    except ValueError:
        return None
