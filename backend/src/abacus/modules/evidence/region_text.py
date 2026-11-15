"""Masked words inside page regions (T-07-T14; ADR-343; ADR-052, ADR-064): what an owner's agent
tool may read of a document region (a governing instrument's clause), for a caller that has
already authorised the read under its own context.

Only pages a PII scan covers are read (fail closed): a region on an unscanned page reads None.
Every word inside a detected region is its mask token (`masking.masked_words`), so a clear
identifier never reaches a tool or a model. The text is the words whose centres fall in the
region, in reading order. Client content stays hostile: the caller wraps it as untrusted.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.evidence.masking import masked_words
from abacus.modules.evidence.projection import projection_of
from abacus.modules.evidence.words import version_word_layers

Region = tuple[int, tuple[float, float, float, float]]


async def masked_region_text(
    tenant: TenantContext, version_id: UUID, regions: Sequence[Region]
) -> list[str | None]:
    """One text per region (None where its page was not scanned)."""
    async with tenant_session(tenant) as session:
        projection = await projection_of(session, evidence_version_id=version_id)
    pages = {p.page: p for p in await version_word_layers(tenant, version_id)}
    out: list[str | None] = []
    for page_no, (x0, top, x1, bottom) in regions:
        page = pages.get(page_no)
        if page is None or not projection.readable(page_no):
            out.append(None)
            continue
        words = masked_words(page.words, projection.regions, page_no)
        inside = [
            w.text
            for w in sorted(words, key=lambda w: (w.top, w.x0))
            if x0 <= (w.x0 + w.x1) / 2 <= x1 and top <= (w.top + w.bottom) / 2 <= bottom
        ]
        out.append(" ".join(inside))
    return out
