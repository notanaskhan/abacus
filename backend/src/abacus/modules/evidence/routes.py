"""Evidence routes (SPEC-000 §8; TASK-012 Q1). Provenance only: content is read through
`read_version`, never listed."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict

from abacus.kernel.classification import classified
from abacus.modules.evidence.service import EvidenceVersionSummary, evidence_versions_for
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

router = AbacusRouter(
    prefix="/v1/engagements/{engagement_id}/evidence-versions", tags=["evidence"]
)
Method = Literal["retrieved", "uploaded"]


class EvidenceVersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    evidence_item_id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, classified("internal")]
    method: Annotated[Method, classified("internal")]
    source: Annotated[str, classified("internal")]
    pulled_at: Annotated[datetime | None, classified("internal")]
    period_start: Annotated[date | None, classified("internal")]
    period_end: Annotated[date | None, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


def _out(version: EvidenceVersionSummary) -> EvidenceVersionOut:
    return EvidenceVersionOut.model_validate(version, from_attributes=True)


Ctx = Annotated[AuthContext, Depends(current_context)]


@router.get("", action="evidence.read", response_model=list[EvidenceVersionOut])
async def list_evidence_versions_route(engagement_id: UUID, ctx: Ctx) -> list[EvidenceVersionOut]:
    return [_out(v) for v in await evidence_versions_for(ctx, engagement_id)]
