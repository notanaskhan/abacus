"""Agent routes (SPEC-000 §8; TASK-012 Q1): screening results for the evidence board. Read-only:
agents propose, and nothing here lets anyone act on a proposal (ADR-005)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict

from abacus.kernel.classification import classified
from abacus.modules.agents.service import ScreeningResultView, screening_results_for
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

router = AbacusRouter(prefix="/v1/engagements/{engagement_id}/screening-results", tags=["agents"])
Action = Literal["ready_for_review", "needs_revision"]
Reason = Literal["cell_not_found", "quote_mismatch", "value_mismatch"]


class CitationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    cell: Annotated[str, classified("internal")]
    quote: Annotated[str | None, classified("confidential")]
    value: Annotated[str | None, classified("confidential")]
    verified: Annotated[bool, classified("internal")]
    reason: Annotated[Reason | None, classified("internal")]


class ScreeningResultOut(BaseModel):
    """Model text (`rationale`, `quote`, `unverified`) is untrusted: render as plain text."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]
    action: Annotated[Action, classified("internal")]
    confidence: Annotated[Decimal, classified("internal")]
    rationale: Annotated[str, classified("confidential")]
    citations: Annotated[list[CitationOut], classified("confidential")]
    unverified: Annotated[list[str], classified("confidential")]
    created_at: Annotated[datetime, classified("internal")]


def _out(result: ScreeningResultView) -> ScreeningResultOut:
    return ScreeningResultOut.model_validate(result, from_attributes=True)


Ctx = Annotated[AuthContext, Depends(current_context)]


@router.get("", action="evidence.read", response_model=list[ScreeningResultOut])
async def list_screening_results_route(engagement_id: UUID, ctx: Ctx) -> list[ScreeningResultOut]:
    return [_out(r) for r in await screening_results_for(ctx, engagement_id)]
