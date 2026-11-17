"""A spreadsheet's extracted cells as an agent reads them (A-09-T34; ADR-052, ADR-066; DEC-5522).

The proposer is shown the cells of one evidence version, masked as every agent reads them
(`masked_rows`), after the actor is allowed `evidence.read` on the version's engagement; a version
of another engagement reads as absent. The rows are client content: the caller marks them
untrusted for the model. The C4 verifier reads the same rows when it checks a cited cell.
"""

from __future__ import annotations

from uuid import UUID

from abacus.kernel.uow import uow
from abacus.modules.evidence.citations.registry import Anchor
from abacus.modules.evidence.citations.verifiers import extracted_sheets, readable_version
from abacus.modules.evidence.pii import masked_rows
from abacus.modules.identity.api import Actor

Rows = tuple[tuple[str, ...], ...]


async def sheet_rows_for(
    actor: Actor, engagement_id: UUID, version_id: UUID
) -> dict[str, Rows] | None:
    """Each sheet's masked rows, or None when the version is not readable on the engagement."""
    anchor = Anchor("evidence_version", version_id, engagement_id=engagement_id)
    async with uow(actor.tenant) as tx:
        version, refused = await readable_version(tx, actor, version_id, anchor)
        if version is None or refused is not None:
            return None
        raw = await extracted_sheets(tx, version_id)
    return {name: tuple(tuple(r) for r in masked_rows(rows)) for name, rows in raw.items()}
