"""Setting an agent's stage for a firm from the staff route (Q-02-T07; SPEC-036 §4.5, Q1, Q3).

Platform staff only (the route's STAFF marker). One unit of work in the firm's
tenant: `agent_stage_set` (migration 0181) appends the stage row and refuses `live` before 50
shadow runs over 14 days (the application role cannot write `agent_stages` itself), and the unit
records `agent_stage.changed` and emits `ai_boundary.facts_changed`, so the worker forgets the
firm's boundary facts too (Q-02-T08); this process forgets them at once.
"""

from __future__ import annotations

from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.ai_gateway import BoundaryFactsChanged, forget_boundary_facts
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.spec import AGENTS

Stage = Literal["shadow", "live", "off"]
STAGES: Final = ("shadow", "live", "off")  # the audit names a stage by its index, as the command
_SET: Final = text("SELECT agent_stage_set(:tenant, :agent, :stage, :staff, :note)")


class StageNotReady(DomainConflict):
    """`live` needs 50 shadow runs of the agent for the firm over 14 days (SPEC-036 Q1)."""

    code = "stage_not_ready"


class UnknownAgent(DomainInvalid):
    """Only an agent the registry declares has a stage. Like the founder's command, a stage may be
    set before the agent is cleared for client data; the gateway reads it only once it is."""

    code = "unknown_agent"


async def set_agent_stage(
    staff_id: UUID, firm_id: UUID, agent_id: str, stage: Stage, note: str
) -> UUID:
    """The new stage row's id; 404 for an unknown firm, 409 `stage_not_ready`, 422
    `unknown_agent`."""
    if agent_id not in AGENTS:
        raise UnknownAgent(facts={"agent_id": agent_id})
    actor = f"staff:{staff_id}"
    try:
        async with uow(TenantContext(firm_id, "system", actor)) as tx:
            stage_id = (
                await tx.session.execute(
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
            tx.record(
                "agent_stage.changed",
                target=Target("agent_stage", UUID(str(stage_id))),
                after=Ref(stage=STAGES.index(stage)),
            )
            tx.emit(BoundaryFactsChanged())
    except DBAPIError as exc:
        message = str(exc.orig) if exc.orig is not None else ""
        if "firm_not_found" in message:
            raise NotFound("firm") from None
        if "stage_not_ready" in message:
            raise StageNotReady(facts={"agent_id": agent_id}) from None
        raise
    forget_boundary_facts(firm_id)
    return UUID(str(stage_id))
