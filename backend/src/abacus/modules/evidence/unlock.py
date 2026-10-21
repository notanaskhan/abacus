"""Unlocking a password-protected PDF upload (TASK-323; ADR-052, ADR-004).

Card and bank e-statements often arrive with a password. The person who has it types it once:
PDFium opens the stored file in an isolated child with that password and saves a copy without
security; the copy is uploaded to the same request item as a new version through the ordinary
upload path (scan, store, extract, check). The original version stays as it was. The password
is used once in memory and never stored, logged or audited.
"""

from __future__ import annotations

import asyncio
import io
from typing import Final, Literal, Protocol, cast
from uuid import UUID

from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.isolation import IsolationFailed, run_isolated
from abacus.modules.evidence import storage
from abacus.modules.evidence.extraction import PDF
from abacus.modules.evidence.service import version_view
from abacus.modules.evidence.uploads import (
    UploadView,
    authorise_upload,
    is_staff_on,
    upload,
    uploads_for,
)
from abacus.modules.identity.api import AuthContext

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


Outcome = Literal["unlocked", "wrong_password", "not_locked", "damaged"]


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
