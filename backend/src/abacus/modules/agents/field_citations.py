"""SHL-09's citations through C4 (P-04-T35; DEC-1050; ADR-166).

`review` never imports `evidence` (the module map); this module composes both, as it does for a
proposal's citations (DEC-602), and registers `review.api.register_field_citations`:

- `supported`: the citations that support a value now (`evidence.api.supported_citations`:
  verified by code, shown, on the engagement, never moved, broken or relinked).
- `describe`: each citation as a reference row, through the citation read (it authorises the
  reader and logs a re-read quote); one the reader may not see is left out.
- `cite_document`: "Add reference", a `document_text` claim that the page shows the field's value,
  verified and written in the person's unit of work; a failed claim is written `verified=false`
  and the caller refuses (its unit of work rolls the row back).
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import UnitOfWork
from abacus.modules.evidence.api import (
    CitationAnchor,
    CitationClaim,
    citation_display,
    record_citations,
    supported_citations,
)
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.review.api import (
    DocumentCitation,
    FieldCitation,
    FieldCitations,
    register_field_citations,
)

ANCHOR: Final = "field"  # the citing record: the field's own `field` target (review)


async def _supported(
    tenant: TenantContext, engagement_id: UUID, citation_ids: list[UUID]
) -> frozenset[UUID]:
    return await supported_citations(tenant, engagement_id, citation_ids)


def _kind(source_type: str) -> str:
    if source_type == "evidence_version":
        return "document"
    if source_type == "tax_return":
        return "engine_import"
    return "workpaper"


async def _describe(ctx: AuthContext, citation_ids: list[UUID]) -> dict[UUID, FieldCitation]:
    out: dict[UUID, FieldCitation] = {}
    for cid in citation_ids:
        try:
            view = await citation_display(ctx, cid)
        except (NotFound, Forbidden):
            continue
        out[cid] = FieldCitation(
            id=cid,
            kind=_kind(view.source.type),
            label=f"{view.title} · {view.loc}" if view.loc else view.title,
            detail=view.value_text,
            document_id=view.source.evidence_version_id,
            page=view.source.page,
        )
    return out


async def _cite_document(
    tx: UnitOfWork, ctx: AuthContext, claim: DocumentCitation
) -> tuple[UUID, bool]:
    locator: dict[str, object] = {"evidence_version_id": str(claim.document_id)}
    if claim.page is not None:
        locator["page"] = claim.page
    [recorded] = await record_citations(
        tx,
        actor=ctx,
        anchor=CitationAnchor(
            type=ANCHOR,
            id=claim.field_id,
            ref=claim.field_key,
            engagement_id=claim.engagement_id,
            work_item_id=claim.work_item_id,
            client_id=claim.client_id,
        ),
        claims=[CitationClaim(kind="document_text", locator=locator, value=claim.value)],
    )
    return recorded.id, recorded.verified


def register_field_citations_reader() -> None:
    register_field_citations(
        FieldCitations(supported=_supported, describe=_describe, cite_document=_cite_document)
    )
