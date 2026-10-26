"""The staff route that sets an agent's stage for a firm (Q-02-T07; SPEC-036 Q3).

`PUT /v1/platform/agent-stages/{firm_id}/{agent_id}`: platform staff only (STAFF), with a note.
The firm admin reads stages through identity's disclosure; nobody in a firm can set one.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.text import SingleLineText
from abacus.modules.agents.stage_admin import Stage, set_agent_stage
from abacus.modules.identity.api import STAFF, AbacusRouter, Staff, current_staff

AgentId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$", max_length=100)]

platform_stages_router = AbacusRouter(prefix="/v1/platform/agent-stages", tags=["agents"])


class AgentStageIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    stage: Annotated[Stage, classified("internal")]
    note: Annotated[SingleLineText, Field(min_length=1, max_length=500), classified("internal")]


class AgentStageOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    firm_id: Annotated[UUID, classified("internal")]
    agent_id: Annotated[str, classified("internal")]
    stage: Annotated[Stage, classified("internal")]


@platform_stages_router.put(
    "/{firm_id}/{agent_id}", action=STAFF, response_model=AgentStageOut, errors=(409,)
)
async def put_agent_stage(
    firm_id: UUID,
    agent_id: AgentId,
    body: AgentStageIn,
    staff: Annotated[Staff, Depends(current_staff)],
) -> AgentStageOut:
    """Shadow, live or off for this firm; `live` only after 50 shadow runs over 14 days."""
    stage_id = await set_agent_stage(staff.id, firm_id, agent_id, body.stage, body.note)
    return AgentStageOut(id=stage_id, firm_id=firm_id, agent_id=agent_id, stage=body.stage)
