"""C5 additive: a person resolves a flagged duplicate upload (T-02-T17; DEC-58 g; TAX-03 e;
DEC-1371). Contract: `docs/contracts/c5-requests-binders.md` §"Duplicate uploads".

`POST /v1/engagements/{engagement_id}/request-items/{item_id}/evidence-versions/{version_id}/
duplicate-resolution` with `keep_newer` or `discard_duplicate` (`evidence.resolve_duplicate`).
Behind `evidence.duplicate_review` (off: 404). A client principal is 404; the agent, the system and
support are refused. 409 `not_a_duplicate`, `duplicate_resolved`, `evidence_accepted`.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict

from abacus.kernel._flags import EVIDENCE_DUPLICATE_REVIEW
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.modules.evidence import duplicates
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]


class DuplicateResolutionIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: Annotated[Literal["keep_newer", "discard_duplicate"], classified("internal")]


class DuplicateResolutionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_version_id: Annotated[UUID, classified("internal")]
    kept_version_id: Annotated[UUID, classified("internal")]
    decision: Annotated[Literal["keep_newer", "discard_duplicate"], classified("internal")]


duplicates_router = AbacusRouter(prefix="/v1/engagements/{engagement_id}", tags=["evidence"])


@duplicates_router.post(
    "/request-items/{item_id}/evidence-versions/{version_id}/duplicate-resolution",
    action="evidence.resolve_duplicate",
    response_model=DuplicateResolutionOut,
    errors=(409,),
)
async def resolve_duplicate_route(
    engagement_id: UUID,
    item_id: UUID,
    version_id: UUID,
    body: DuplicateResolutionIn,
    ctx: Ctx,
) -> DuplicateResolutionOut:
    """TAX-03 e: Keep newer or Discard duplicate; a discard voids and hides, never deletes."""
    if ctx.client:
        raise NotFound("evidence_version")
    if not await flag_enabled(ctx.tenant, EVIDENCE_DUPLICATE_REVIEW):
        raise NotFound(EVIDENCE_DUPLICATE_REVIEW.name)
    kept = await duplicates.resolve(ctx, engagement_id, item_id, version_id, body.decision)
    return DuplicateResolutionOut(
        evidence_version_id=version_id, kept_version_id=kept, decision=body.decision
    )
