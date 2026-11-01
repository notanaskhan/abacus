"""Isolated extraction for methodology source documents (K-01-T20; K-01 §4.3, §4.4; DEC-1855).

The Methodology importer (K-01-T21) reads a firm's methodology PDF page by page. Everything that
touches the bytes runs in `kernel.pdf_pages`' isolated child (ADR-110): every page's words with
their boxes for the parse batches and the quote verifier, and a page image for the KNW-02 viewer.

- **Problems** become codes, never a crash: an encrypted file is 422 `source_encrypted`; a damaged
  or malformed one, or one that crashed or ran out of time in the child, is 422
  `source_malformed`; more than `MAX_PAGES` pages is 422 `source_too_long`.
- **PII hold** (`pii_hold`): before any model call, every page's text is scanned for unmasked SSN,
  ITIN and EIN forms (`kernel.tin_patterns`). A file with any is held: the importer stops there
  and calls no model (methodology content is firm content; a TIN in it is a mistake to correct).
  The hold names the pages and the forms, never the digits (Restricted).
- **Page and region reads** (`page_image`, `page_words`): a PDF source file of a version, one page
  at a time, for people with `methodology.read`; a DOCX has no page image (409
  `page_preview_unavailable`) and a page past the end is 422 `page_out_of_range`. Each read is
  audited; words come back with any TIN form masked.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from sqlalchemy import func, select

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.pdf_pages import (
    MAX_PAGES,
    PagePng,
    PageWords,
    PdfWords,
    Problem,
    Word,
    read_words_isolated,
    render_page_isolated,
)
from abacus.kernel.tin_patterns import find_tins, scrub_tins
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Resource, authorise
from abacus.modules.methodology.models import MethodologyImport, MethodologySourceFile
from abacus.modules.platform.api import read_stored

READ: Final = "methodology.read"
PDF_ROLE: Final = "document_pdf"
FILE: Final = "methodology_source_file"


class SourceEncrypted(DomainInvalid):
    """The PDF needs a password: the firm uploads it unlocked."""

    code = "source_encrypted"


class SourceMalformed(DomainInvalid):
    """The PDF could not be read (damaged, not a PDF, or it broke the isolated reader)."""

    code = "source_malformed"


class SourceTooLong(DomainInvalid):
    """More pages than the importer reads (`facts.max_pages`)."""

    code = "source_too_long"


class PagePreviewUnavailable(DomainConflict):
    """Only a PDF source has page images (a DOCX is read as text)."""

    code = "page_preview_unavailable"


class PageOutOfRange(DomainInvalid):
    """No such page (`facts.page_count`)."""

    code = "page_out_of_range"


def _raise_for(problem: Problem | str, page_count: int) -> None:
    if problem == "encrypted":
        raise SourceEncrypted(facts={"problem": problem})
    if problem == "too_many_pages":
        raise SourceTooLong(facts={"max_pages": MAX_PAGES, "page_count": page_count})
    if problem == "page_out_of_range":
        raise PageOutOfRange(facts={"page_count": page_count})
    raise SourceMalformed(facts={"problem": problem})


@dataclass(frozen=True)
class PiiHold:
    """Whether the file is held before any model call, on which pages and for which forms."""

    held: bool
    pages: tuple[int, ...] = ()
    forms: tuple[str, ...] = ()


def pii_hold(pages: Sequence[PageWords]) -> PiiHold:
    """Unmasked SSN, ITIN and EIN forms on any page hold the file (pure; digits never kept)."""
    held_pages: list[int] = []
    forms: set[str] = set()
    for page in pages:
        found = find_tins(page.text)
        if found:
            held_pages.append(page.page)
            forms.update(m.type for m in found)
    return PiiHold(bool(held_pages), tuple(held_pages), tuple(sorted(forms)))


@dataclass(frozen=True)
class ExtractedSource:
    page_count: int
    pages: tuple[PageWords, ...]
    hold: PiiHold


async def extract_source(content: bytes) -> ExtractedSource:
    """Every page's words in the isolated child, then the PII hold; a problem raises its code.
    The importer's `methodology.extract_pages` activity (K-01-T21) calls this before any batch."""
    words: PdfWords = await asyncio.to_thread(read_words_isolated, content)
    if words.problem is not None:
        _raise_for(words.problem, words.page_count)
    return ExtractedSource(words.page_count, words.pages, pii_hold(words.pages))


async def _pdf_source(ctx: AuthContext, version_id: UUID, file_id: UUID) -> bytes:
    """A version's PDF source file's verified bytes (the import it came from names the version)."""
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        found = (
            await session.execute(
                select(MethodologySourceFile)
                .join(MethodologyImport, MethodologyImport.id == MethodologySourceFile.import_id)
                .where(
                    MethodologySourceFile.id == file_id,
                    func.coalesce(MethodologySourceFile.version_id, MethodologyImport.version_id)
                    == version_id,
                )
            )
        ).scalar_one_or_none()
    if found is None:
        raise NotFound(FILE)
    if found.role != PDF_ROLE:
        raise PagePreviewUnavailable(facts={"role": found.role})
    return await read_stored(
        ctx.tenant_id, found.storage_key, found.storage_version_id, found.sha256, found.bytes
    )


async def _audit(
    ctx: AuthContext, file_id: UUID, version_id: UUID, page: int, words: bool
) -> None:
    after = Ref(version_id=version_id, page=page)
    async with uow(ctx.tenant) as tx:
        if words:
            tx.record(
                "methodology_source_file.words_read", target=Target(FILE, file_id), after=after
            )
        else:
            tx.record(
                "methodology_source_file.page_read", target=Target(FILE, file_id), after=after
            )


async def page_image(ctx: AuthContext, version_id: UUID, file_id: UUID, page: int) -> PagePng:
    """One page as a PNG for the KNW-02 viewer (audited)."""
    content = await _pdf_source(ctx, version_id, file_id)
    found: PagePng = await asyncio.to_thread(render_page_isolated, content, page)
    if found.problem is not None:
        _raise_for(found.problem, found.page_count)
    await _audit(ctx, file_id, version_id, page, words=False)
    return found


@dataclass(frozen=True)
class PageRegions:
    page: int
    page_count: int
    words: tuple[Word, ...]


async def page_words(ctx: AuthContext, version_id: UUID, file_id: UUID, page: int) -> PageRegions:
    """One page's words with their boxes (fractions of the page), TIN forms masked (audited)."""
    content = await _pdf_source(ctx, version_id, file_id)
    words: PdfWords = await asyncio.to_thread(read_words_isolated, content)
    if words.problem is not None:
        _raise_for(words.problem, words.page_count)
    if not 1 <= page <= words.page_count:
        raise PageOutOfRange(facts={"page_count": words.page_count})
    found = words.pages[page - 1]
    await _audit(ctx, file_id, version_id, page, words=True)
    return PageRegions(
        page,
        words.page_count,
        tuple(Word(scrub_tins(w.text), w.box) for w in found.words),
    )
