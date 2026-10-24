"""The agents' citations as v2 rows (P-03-T10; SPEC-322 AC-1; ADR-166, ADR-066; DEC-267).
PROTECTED.

The screener, the upload reviewer and the matcher keep their prompts, outputs and legacy JSON;
in the same unit of work that records their handoff, each of their citations is also written as
one `citations` row through `evidence.api.record_citations`, as the agent (`created_by_kind`
agent, its run and initiator). Evidence's registered verifiers decide each row by code, on the
word layer: a verified quote carries the box of its words and resolves to a lit region; one that
fails is written unverified with its reason, and every reader shows it "Unverified". Nothing here
trusts what the model says it cites, and no quote text is stored.

Anchors (where the citation is used):
- screener: `screening_result:<result>`; its cells are `sheet_cell` claims on the version;
- upload reviewer: `upload_review:<review>`, `ref` `F<position>` of the flag; a page quote is
  `document_text`, a cell quote `sheet_cell`, on the version;
- matcher: `inbox_match:<match>`, `ref` `R<rank>` of the proposal; on the inbox file.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from abacus.kernel.uow import UnitOfWork
from abacus.modules.agents.handoff import Citation, DocumentCitation
from abacus.modules.evidence.api import (
    CitationAnchor,
    CitationClaim,
    RecordedCitation,
    record_citations,
)
from abacus.modules.identity.api import AgentContext


def cell_claims(version_id: UUID, citations: Sequence[Citation]) -> list[CitationClaim]:
    """The screener's cells on the trial balance it screened."""
    return [
        CitationClaim(
            "sheet_cell",
            {"evidence_version_id": str(version_id), "cell": c.cell},
            quote=c.quote,
            value=None if c.value is None else str(c.value),
        )
        for c in citations
    ]


def document_claims(
    citations: Sequence[DocumentCitation],
    *,
    evidence_version_id: UUID | None = None,
    inbox_file_id: UUID | None = None,
) -> list[CitationClaim]:
    """The reviewer's or matcher's quotes: a page is `document_text`, a cell `sheet_cell`."""
    source = (
        {"evidence_version_id": str(evidence_version_id)}
        if evidence_version_id is not None
        else {"inbox_file_id": str(inbox_file_id)}
    )
    claims: list[CitationClaim] = []
    for c in citations:
        if c.page is not None:
            claims.append(
                CitationClaim("document_text", {**source, "page": c.page}, quote=c.quote)
            )
        else:
            locator: dict[str, object] = {**source, "cell": c.cell}
            if c.sheet:
                locator["sheet"] = c.sheet
            claims.append(CitationClaim("sheet_cell", locator, quote=c.quote))
    return claims


async def record_agent_citations(
    tx: UnitOfWork,
    agent: AgentContext,
    *,
    anchor_type: str,
    anchor_id: UUID,
    ref: str | None,
    claims: Sequence[CitationClaim],
) -> list[RecordedCitation]:
    """Write `claims` as the agent, in its handoff's unit of work, on its engagement."""
    if not claims:
        return []
    anchor = CitationAnchor(anchor_type, anchor_id, ref, None, agent.engagement)
    return await record_citations(tx, actor=agent, anchor=anchor, claims=claims)


__all__ = ["cell_claims", "document_claims", "record_agent_citations"]
