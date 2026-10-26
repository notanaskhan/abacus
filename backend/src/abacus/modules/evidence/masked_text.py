"""A document's masked text, the only page text an agent reads (DEC-322; DEC-52; P-03-T15,
SPEC-322 AC-25, AC-40).

Each PII-scanned page's words with every detected region replaced by its token, then the kernel's
TIN scrub as a backstop; a page no scan covers is left out (fail closed). Until the scan has run
there is no text at all. For the system or a caller that authorised on the source.
"""

from __future__ import annotations

from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.tin_patterns import scrub_tins
from abacus.modules.evidence.pii import DETECTOR_VERSION
from abacus.modules.evidence.projection import projection_of
from abacus.modules.evidence.repository import pages_of, scan_run_for
from abacus.modules.evidence.words import WORDS_VERSION, read_page_layer


async def masked_pages(
    tenant: TenantContext,
    *,
    evidence_version_id: UUID | None = None,
    inbox_file_id: UUID | None = None,
) -> dict[int, str] | None:
    """The source's scanned pages as masked text, or None when no PII scan has run on it."""
    if (evidence_version_id is None) == (inbox_file_id is None):
        raise ValueError("name exactly one source")
    async with tenant_session(tenant) as session:
        run = await scan_run_for(
            session,
            evidence_version_id=evidence_version_id,
            inbox_file_id=inbox_file_id,
            detector_version=DETECTOR_VERSION,
        )
        if run is None:
            return None
        pages = await pages_of(
            session,
            evidence_version_id=evidence_version_id,
            inbox_file_id=inbox_file_id,
            extractor_version=WORDS_VERSION,
        )
        projection = await projection_of(
            session, evidence_version_id=evidence_version_id, inbox_file_id=inbox_file_id
        )
    out: dict[int, str] = {}
    for page in pages:
        if not page.has_text_layer or not projection.readable(page.page_no):
            continue
        layer = await read_page_layer(tenant.tenant_id, page)
        words = projection.words(layer.words, page.page_no) or []
        out[page.page_no] = scrub_tins(" ".join(w.text for w in words))
    return out
