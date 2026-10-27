"""What code knows about versions a request batch's screening is composed from (P-06-T20;
DEC-48, DEC-324; ADR-050).

Identifiers, dates and check outcomes only: no document text. A withdrawn version is absent
(ADR-162 §4), as from every evidence read. For a system caller composing the aggregate, or a
caller that authorised `upload_review.read` on the versions' engagement.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.evidence.repository import (
    citation_versions_among,
    get_item,
    get_version,
    latest_checks,
    newest_extraction,
    supported_citations_among,
    verified_citations_of,
)


@dataclass(frozen=True)
class ScreeningFacts:
    evidence_version_id: UUID
    file_name: str
    extraction_status: str | None  # None: not read yet
    period_start: date | None
    period_end: date | None
    as_of: date | None
    checks: tuple[tuple[str, str], ...]  # (check code, outcome) of the newest check run


async def screening_facts(
    tenant: TenantContext, version_ids: Sequence[UUID]
) -> dict[UUID, ScreeningFacts]:
    """Each live version's facts, keyed by id; withdrawn or unknown versions are left out."""
    found: dict[UUID, ScreeningFacts] = {}
    async with tenant_session(tenant) as session:
        for version_id in dict.fromkeys(version_ids):
            version = await get_version(session, version_id)
            if version is None:
                continue
            item = await get_item(session, version.evidence_item_id)
            row = await newest_extraction(session, evidence_version_id=version_id)
            checks = await latest_checks(session, version_id)
            found[version_id] = ScreeningFacts(
                version_id,
                item.title if item is not None else "",
                row.status if row is not None else None,
                row.period_start if row is not None else None,
                row.period_end if row is not None else None,
                row.as_of if row is not None else None,
                tuple((c.check_code, c.outcome) for c in checks),
            )
    return found


async def verified_citation_ids(
    tenant: TenantContext, cited_from_type: str, cited_from_ids: Sequence[UUID]
) -> dict[tuple[UUID, str | None], list[UUID]]:
    """The verified, live citations of each (anchor, ref), in order (C4 regions resolve by id)."""
    async with tenant_session(tenant) as session:
        rows = await verified_citations_of(session, cited_from_type, cited_from_ids)
    out: dict[tuple[UUID, str | None], list[UUID]] = {}
    for citation_id, anchor, ref in rows:
        out.setdefault((anchor, ref), []).append(citation_id)
    return out


async def supported_citations(
    tenant: TenantContext, engagement_id: UUID, citation_ids: Sequence[UUID]
) -> frozenset[UUID]:
    """P-04-T24 (C4, INV-2): the citations among `citation_ids` that are verified by code and
    still valid on `engagement_id` now. A proposal row or a suggestion whose citations are not
    all here is unsupported (`uncited_change`). For a caller authorised on the engagement."""
    async with tenant_session(tenant) as session:
        return await supported_citations_among(session, engagement_id, citation_ids)


async def citation_sources(
    tenant: TenantContext, citation_ids: Sequence[UUID]
) -> dict[UUID, UUID]:
    """P-04-T24: citation id -> the evidence version it quotes, for SHL-10's evidence list."""
    async with tenant_session(tenant) as session:
        return await citation_versions_among(session, citation_ids)
