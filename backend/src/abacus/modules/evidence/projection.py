"""What a reader of a source's words may see: the PII-masked projection, failing closed
(P-03-T08, T09; SPEC-322 AC-23, AC-24; DEC-52, DEC-266). PROTECTED.

One check for every reader of client text from the word layer (the manifest's `pii_scan`, the
in-document search, a citation's re-read quote): a page is readable only when a PII scan of the
source (`pii_scan_runs`, P-03-T13) lists it as scanned, and then only through `masking`. A page
no scan covers (none before T13; a scanned image before P-11's OCR) is `not_scannable`: never
searched and never quoted, so an unmasked identifier can't leave through text or hit positions.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.evidence.citations.matching import WordLike
from abacus.modules.evidence.masking import MaskedWord, MaskRegion, masked_words
from abacus.modules.evidence.pii import DETECTOR_VERSION
from abacus.modules.evidence.repository import pii_regions_of, scanned_pages


@dataclass(frozen=True)
class Projection:
    """A source's scanned pages and detected regions."""

    scanned: frozenset[int]
    regions: tuple[MaskRegion, ...]

    def readable(self, page_no: int) -> bool:
        """The page was scanned for PII: its masked words may be read."""
        return page_no in self.scanned

    def scan_state(self, page_no: int) -> str:
        return "done" if self.readable(page_no) else "not_scannable"

    def words(self, words: Sequence[WordLike], page_no: int) -> list[MaskedWord] | None:
        """The page's masked words, or None when the page may not be read (fail closed)."""
        if not self.readable(page_no):
            return None
        return masked_words(words, self.regions, page_no)


async def projection_of(
    session: AsyncSession,
    *,
    evidence_version_id: UUID | None = None,
    inbox_file_id: UUID | None = None,
) -> Projection:
    """For a caller that authorised on the source: what of its words may be read."""
    # Only the current detector's scan of the current word layer (P-03-T15 review): an earlier
    # scan's pages and boxes belong to an earlier layer.
    scanned = await scanned_pages(
        session,
        evidence_version_id=evidence_version_id,
        inbox_file_id=inbox_file_id,
        detector_version=DETECTOR_VERSION,
    )
    regions = await pii_regions_of(
        session,
        evidence_version_id=evidence_version_id,
        inbox_file_id=inbox_file_id,
        detector_version=DETECTOR_VERSION,
    )
    return Projection(
        frozenset(scanned),
        tuple(
            MaskRegion(
                r.page_no,
                (float(r.bbox[0]), float(r.bbox[1]), float(r.bbox[2]), float(r.bbox[3])),
                r.kind,
                r.last4,
            )
            for r in regions
        ),
    )


__all__ = ["Projection", "projection_of"]
