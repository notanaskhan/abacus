"""An agent's stage for a real firm (SPEC-036 §4.5; TASK-076). PROTECTED.

A cleared agent starts in `shadow` for each firm: its runs happen and are recorded (marked
`agent_runs.shadow`) but nothing they produce is shown. The founder promotes it to `live`, or turns
it `off`, with `abacus_tools.ops.agent_stage` (D1); the newest `agent_stages` row is the stage.
Synthetic firms have no stages: their runs are never shadow.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.ai_gateway import is_synthetic
from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.agents.repository import stage_of
from abacus.modules.agents.spec import AGENTS, cleared_for_client_data
from abacus.modules.identity.api import Assistant


async def stage_for(tenant: TenantContext, agent_id: str) -> str | None:
    """For the gateway: the stage row, else `shadow` for a cleared agent, else None (refused)."""
    async with tenant_session(tenant) as session:
        found = await stage_of(session, agent_id)
    if found is not None:
        return found
    return "shadow" if cleared_for_client_data(agent_id) else None


async def starts_in_shadow(session: AsyncSession, tenant: TenantContext, agent_id: str) -> bool:
    """Whether a run starting now for this firm is a shadow run (D2: marked once, at start)."""
    if await is_synthetic(tenant):
        return False
    return await stage_of(session, agent_id) in (None, "shadow")


async def assistants(tenant: TenantContext) -> list[Assistant]:
    """For identity's disclosure: the agents cleared for client data, with their stage."""
    found: list[Assistant] = []
    for agent in AGENTS.values():
        if agent.client_data == "cleared":
            stage = await stage_for(tenant, agent.id) or "off"
            found.append(Assistant(agent.id, agent.purpose, stage))
    return found
