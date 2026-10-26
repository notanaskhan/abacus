"""Setting an agent's stage for a firm from the staff route (Q-02-T07; SPEC-036 §4.5, Q1, Q3).

Platform staff only (the route's STAFF marker). The write is `agent_stage_set` (migration 0181),
which appends the stage row and its audit event and refuses `live` before 50 shadow runs over 14
days; the application role cannot write `agent_stages` itself. The firm's boundary facts are then
forgotten here and, through `ai_boundary.facts_changed`, in the worker (Q-02-T08).
"""

from __future__ import annotations

from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.ai_gateway import BoundaryFactsChanged, forget_boundary_facts
from abacus.kernel.db import TenantContext, platform_transaction
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import uow
from abacus.modules.agents.spec import cleared_for_client_data

Stage = Literal["shadow", "live", "off"]
_SET: Final = text("SELECT agent_stage_set(:tenant, :agent, :stage, :staff, :note)")


class StageNotReady(DomainConflict):
    """`live` needs 50 shadow runs of the agent for the firm over 14 days (SPEC-036 Q1)."""

    code = "stage_not_ready"


class AgentNotCleared(DomainInvalid):
    """Only an agent cleared for client data has a stage (SPEC-036 §4.4)."""

    code = "agent_not_cleared"


async def set_agent_stage(
    staff_id: UUID, firm_id: UUID, agent_id: str, stage: Stage, note: str
) -> UUID:
    """The new stage row's id; 404 for an unknown firm, 409 `stage_not_ready`, 422
    `agent_not_cleared`."""
    if not cleared_for_client_data(agent_id):
        raise AgentNotCleared(facts={"agent_id": agent_id})
    actor = f"staff:{staff_id}"
    try:
        async with platform_transaction(actor) as conn:
            stage_id = (
                await conn.execute(
                    _SET,
                    {
                        "tenant": firm_id,
                        "agent": agent_id,
                        "stage": stage,
                        "staff": actor,
                        "note": note,
                    },
                )
            ).scalar_one()
    except DBAPIError as exc:
        message = str(getattr(exc.orig, "args", ("",))[0] if exc.orig else "")
        if "firm_not_found" in message:
            raise NotFound("firm") from None
        if "stage_not_ready" in message:
            raise StageNotReady(facts={"agent_id": agent_id}) from None
        raise
    async with uow(TenantContext(firm_id, "system", actor)) as tx:
        tx.emit(BoundaryFactsChanged())
    forget_boundary_facts(firm_id)
    return UUID(str(stage_id))
