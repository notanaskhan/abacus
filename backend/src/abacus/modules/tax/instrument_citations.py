"""The `instrument_clause` citable (T-07-T11; TASK-8038; ADR-343; SPEC-656 AC-1.4, AC-6.2; C4
v1.2). PROTECTED (red path: citations, INV-2).

- **Locator** `{instrument_id, segmentation_id, clause_id}`, ids only; the stored row adds the
  quote's hash (`quote_sha256`). No instrument text is stored anywhere (ADR-343 §2). The match id
  is server-derived: `ic:<segmentation_id>#<clause_id>`.
- **Verifier** (§3), inside the writer's unit of work: the clause is resolved in the named
  segmentation and the segmentation in the named instrument (`source_not_found` when any is
  missing, `locator_invalid` when they do not belong together); then each of the clause's regions,
  in order, is re-read as a `document_text` claim on the instrument's evidence version through
  evidence's own verifier, which authorises `evidence.read` on the anchor's engagement before it
  reads anything (never an oracle) and reads the masked word layer. The quote verifies when it is
  inside one of the regions; found only elsewhere on those pages it is `bbox_mismatch`, nowhere
  `quote_not_found`. The quote is never stored, logged or returned.
- **Display** (§4): the clause's code-held label and heading, "Art. III(a)", with "Trust
  agreement · pages 3 to 4" with an en dash (never model text).
- **Regions** (§4): `regions?match_ids=ic:…` lights the clause's regions on the instrument's
  version, labelled with the clause label (`register_region_source`).
- **Moved** (§5): when an instrument is superseded (an amendment or restatement attached as a new
  `governing_instruments` row), `move_clause_citations` moves every clause citation of the old
  instrument's segmentations in the attaching unit of work (C-07-T12's instrument service calls
  it); re-segmenting the same version is not a move.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import tenant_session
from abacus.kernel.uow import UnitOfWork
from abacus.modules.evidence.api import (
    CitationAnchor,
    CitationClaim,
    CitationLabel,
    CitationVerdict,
    RegionHit,
    mark_sources_superseded,
    register_citable,
    register_region_source,
    verify_document_citation,
)
from abacus.modules.identity.api import Actor, AuthContext

KIND: Final = "instrument_clause"
SOURCE: Final = "instrument_segmentation"
NIL: Final = UUID(int=0)
PREFIX: Final = "ic:"
INSTRUMENT_TITLE: Final = "Trust agreement"

_CLAUSE: Final = text(
    "SELECT c.id, c.segmentation_id, c.label, c.heading, c.page_from, c.page_to, c.regions, "
    "s.instrument_id, g.evidence_version_id "
    "FROM instrument_clauses c "
    "JOIN instrument_segmentations s ON s.id = c.segmentation_id "
    "JOIN governing_instruments g ON g.id = s.instrument_id "
    "WHERE c.id = :clause"
)
_SEGMENTATION: Final = text(
    "SELECT s.id, s.instrument_id FROM instrument_segmentations s WHERE s.id = :seg"
)


def match_id(segmentation_id: UUID, clause_id: UUID) -> str:
    return f"{PREFIX}{segmentation_id}#{clause_id}"


def _locator(raw: Mapping[str, object]) -> tuple[UUID, UUID, UUID] | None:
    try:
        return (
            UUID(str(raw["instrument_id"])),
            UUID(str(raw["segmentation_id"])),
            UUID(str(raw["clause_id"])),
        )
    except (KeyError, ValueError):
        return None


def _regions(raw: object) -> list[tuple[int, list[float]]]:
    """The clause's `[{page, bbox}]` as (page, box); anything malformed is dropped (none
    verifies then)."""
    out: list[tuple[int, list[float]]] = []
    for item in cast(list[object], raw) if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        region = cast(dict[str, object], item)
        page, box = region.get("page"), region.get("bbox")
        if (
            isinstance(page, int)
            and isinstance(box, list)
            and len(cast(list[object], box)) == 4
            and all(isinstance(v, (int, float)) for v in cast(list[object], box))
        ):
            out.append((page, [float(v) for v in cast(list[float], box)]))
    return out


async def verify_instrument_clause(
    tx: UnitOfWork, actor: Actor, claim: CitationClaim, anchor: CitationAnchor
) -> CitationVerdict:
    at = _locator(claim.locator)
    if at is None or not claim.quote:
        return CitationVerdict("locator_invalid", SOURCE, NIL)
    instrument_id, segmentation_id, clause_id = at
    kept: dict[str, object] = {
        "instrument_id": str(instrument_id),
        "segmentation_id": str(segmentation_id),
        "clause_id": str(clause_id),
    }
    segmentation = (await tx.session.execute(_SEGMENTATION, {"seg": segmentation_id})).first()
    row = (await tx.session.execute(_CLAUSE, {"clause": clause_id})).first()
    if segmentation is None or row is None:
        return CitationVerdict("source_not_found", SOURCE, segmentation_id, kept)
    if row.segmentation_id != segmentation_id or segmentation.instrument_id != instrument_id:
        return CitationVerdict("locator_invalid", SOURCE, segmentation_id, kept)
    regions = _regions(row.regions)
    if not regions:
        return CitationVerdict("locator_invalid", SOURCE, segmentation_id, kept)
    outside = False
    for page, box in regions:
        verdict = await verify_document_citation(
            tx,
            actor,
            CitationClaim(
                "document_text",
                {"evidence_version_id": str(row.evidence_version_id), "page": page, "bbox": box},
                quote=claim.quote,
            ),
            anchor,
        )
        if verdict.verified:
            return CitationVerdict(
                None,
                SOURCE,
                segmentation_id,
                kept,
                source_version=str(segmentation_id),
                match_id=match_id(segmentation_id, clause_id),
                quote_sha256=verdict.quote_sha256,
            )
        if verdict.reason in ("source_not_visible", "source_not_found"):
            return CitationVerdict(verdict.reason, SOURCE, segmentation_id, kept)
        outside = outside or verdict.reason == "bbox_mismatch"
    return CitationVerdict(
        "bbox_mismatch" if outside else "quote_not_found", SOURCE, segmentation_id, kept
    )


def _pages(page_from: int, page_to: int) -> str:
    return f"page {page_from}" if page_from == page_to else f"pages {page_from}–{page_to}"  # noqa: RUF001


async def display_instrument_clause(
    session: AsyncSession, locator: Mapping[str, object], engagement_id: UUID | None
) -> CitationLabel:
    """'Art. III(a)' and 'Trust agreement · pages 3 to 4' (an en dash), from the clause record
    (INV-2). The clause is named only to a reader of a citation in an engagement (security
    review #3)."""
    at = _locator(locator)
    if at is None or engagement_id is None:
        return CitationLabel(INSTRUMENT_TITLE, "")
    row = (await session.execute(_CLAUSE, {"clause": at[2]})).first()
    if row is None or row.segmentation_id != at[1]:
        return CitationLabel(INSTRUMENT_TITLE, "")
    title = row.label if not row.heading else f"{row.label} · {row.heading}"
    return CitationLabel(title, f"{INSTRUMENT_TITLE} · {_pages(row.page_from, row.page_to)}")


_REGIONS_OF: Final = text(
    "SELECT c.id, c.segmentation_id, c.label, c.regions FROM instrument_clauses c "
    "JOIN instrument_segmentations s ON s.id = c.segmentation_id "
    "JOIN governing_instruments g ON g.id = s.instrument_id "
    "WHERE c.id = ANY(:ids) AND g.evidence_version_id = :version"
)


async def clause_regions(
    ctx: AuthContext, version_id: UUID, match_ids: Sequence[str]
) -> list[RegionHit]:
    """The lavender passage (TXT-01): each named clause's regions on this version, labelled.
    Evidence has already checked the reader may see the version (`visible_version`)."""
    wanted: dict[UUID, tuple[UUID, str]] = {}
    for m in match_ids:
        seg, _, clause = m.removeprefix(PREFIX).partition("#")
        try:
            wanted[UUID(clause)] = (UUID(seg), m)
        except ValueError:
            continue
    if not wanted:
        return []
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(_REGIONS_OF, {"ids": list(wanted), "version": version_id})
        ).all()
    out: list[RegionHit] = []
    for r in rows:
        seg, match = wanted[r.id]
        if seg != r.segmentation_id:
            continue
        for page, box in _regions(r.regions):
            out.append((match, page, (box[0], box[1], box[2], box[3]), r.label))
    return out


_SEGMENTATIONS_OF: Final = text(
    "SELECT id FROM instrument_segmentations WHERE instrument_id = :instrument ORDER BY created_at"
)


async def move_clause_citations(
    tx: UnitOfWork, old_instrument_id: UUID, new_instrument_id: UUID
) -> int:
    """§5: an instrument superseded by a new one moves every clause citation of the old
    instrument's segmentations (in the caller's unit of work). Returns the citations moved."""
    moved = 0
    for segmentation in await tx.session.scalars(
        _SEGMENTATIONS_OF, {"instrument": old_instrument_id}
    ):
        moved += await mark_sources_superseded(
            tx,
            source_type=SOURCE,
            source_id=segmentation,
            old=str(segmentation),
            new=f"instrument:{new_instrument_id}",
        )
    return moved


def register() -> None:
    register_citable(KIND, verify_instrument_clause, display_instrument_clause)
    register_region_source(PREFIX, clause_regions)
