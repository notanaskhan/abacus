"""A person's run of a v2 capability that code drives inline (A-09-T29; DEC-5409): the run row
(attributed "<person> via Agent", shadow when the stage says so), its agent context, and its end.
The capability's own module calls the gateway and the C17 tools; this module only opens and
closes the run, so no other module touches `agent_runs` (P-39)."""

from __future__ import annotations

from uuid import UUID, uuid4

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, uow
from abacus.modules.agents.events import RunNeedsInput
from abacus.modules.agents.repository import finish_run, insert_run
from abacus.modules.agents.service import load_agent_context
from abacus.modules.agents.spec_v2 import spec_v2
from abacus.modules.agents.stages import starts_in_shadow
from abacus.modules.identity.api import AgentContext, AuthContext


async def start_capability_run(
    person: AuthContext, capability: str, engagement_id: UUID | None
) -> AgentContext | None:
    """The run's agent context for `person`, or None when the run could not be recorded."""
    found = spec_v2(capability)
    reader = TenantContext(person.tenant_id, "system", f"agents:{capability}")
    run_id: UUID | None = None
    try:
        async with uow(reader) as tx:
            run_id = await insert_run(
                tx.session,
                tenant_id=person.tenant_id,
                agent_id=capability,
                shadow=await starts_in_shadow(tx.session, reader, capability),
                spec_version=found.version,
                engagement_id=engagement_id,
                evidence_version_id=None,
                initiator_user_id=person.user_id,
                source_event_id=uuid4(),
                task_scope=sorted(found.task_scope),
            )
            if run_id is not None:
                tx.record(
                    "agent_run.started",
                    target=Target("agent_run", run_id),
                    after=Ref(initiator=person.user_id),
                )
    except MissingAuditEvent:
        pass
    if run_id is None:
        return None
    return await load_agent_context(person.tenant_id, run_id)


async def end_capability_run(
    agent: AgentContext, *, status: str, output: dict[str, object] | None = None
) -> None:
    """`succeeded`, `escalated` or `failed`, once; the output is identifiers and counts. S48 rest
    (C-01-T30): an escalated run waits on its person (C6 v2 `needs_input`), so it also emits
    `agent_run.needs_input` and C16 tells the initiator (`run_needs_input`)."""
    async with uow(agent.tenant) as tx:
        if await finish_run(tx.session, agent.agent_run_id, status=status, output=output):
            tx.record(f"agent_run.{status}", target=Target("agent_run", agent.agent_run_id))
            if status == "escalated" and agent.engagement_id is not None:
                tx.emit(
                    RunNeedsInput(
                        run_id=agent.agent_run_id,
                        engagement_id=agent.engagement_id,
                        user_id=agent.initiator.user_id,
                    )
                )
