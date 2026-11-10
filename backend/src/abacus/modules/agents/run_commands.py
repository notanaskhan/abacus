"""What a person's command does to a running v2 run (P-10-T32; SPEC-647 §3.4 AC-W5, AC-W6, AC-W10).
PROTECTED (agents). P-10-T33's routes authorise the person, write their row, then call these.

- `wake(..., kind)`: the run's workflow is told a person acted (`question_answered`, `stop`,
  `redirected`); the workflow reads the rows itself, so a lost signal is caught up by the next one
  and nothing is decided by the signal (kernel.dispatch's best effort, DEC-3180).
- `retry_step`: one failed step runs again as a new row (`retry_of_step_id`).
- `retry_run` (whole-run retry): a **child run** (`parent_run_id`) with the same agent,
  engagement, task scope and inputs, started for the person who asked; the ended run is never
  reopened.

No function here decides for anyone: a context that is not a live person is refused (ADR-005).
"""

from __future__ import annotations

from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.dispatch import dispatch, signal_workflow
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.run_waits import run_workflow_id
from abacus.modules.agents.run_workflow import AgentRunInput, AgentRunWorkflow
from abacus.modules.identity.api import AuthContext, Forbidden

Wake = Literal["question_answered", "stop", "redirected"]
_ENDED: Final = frozenset({"succeeded", "failed", "cancelled"})


class RunNotEnded(DomainConflict):
    """A whole-run retry is for an ended run; a running one retries its steps."""

    code = "run_not_ended"


class StepNotFailed(DomainConflict):
    code = "step_not_failed"


def _person(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden(action, "role")


async def wake(tenant_id: UUID, run_id: UUID, kind: Wake) -> None:
    await signal_workflow(run_workflow_id(str(tenant_id), str(run_id)), kind)


async def retry_step(ctx: AuthContext, run_id: UUID, step_seq: int) -> str:
    """AC-W6: the failed step at `step_seq` runs again; returns its plan key. The route has
    authorised `agent_run.retry_step` on the run's engagement."""
    _person(ctx, "agent_run.retry_step")
    async with uow(ctx.tenant) as tx:
        row = (
            await tx.session.execute(
                text(
                    "SELECT plan_step_key, state FROM agent_run_steps "
                    "WHERE run_id = :run AND seq = :seq"
                ),
                {"run": run_id, "seq": step_seq},
            )
        ).first()
        if row is None:
            raise NotFound("agent_run_step")
        if row.state != "failed" or not row.plan_step_key:
            raise StepNotFailed(facts={"state": str(row.state)})
        tx.record(
            "agent_run_step.retry_requested",
            target=Target("agent_run", run_id),
            after=Ref(seq=step_seq),
        )
    await signal_workflow(
        run_workflow_id(str(ctx.tenant_id), str(run_id)), "step_retry", str(row.plan_step_key)
    )
    return str(row.plan_step_key)


async def retry_run(ctx: AuthContext, run_id: UUID) -> UUID:
    """The whole-run retry: a child run of an ended run, started for this person."""
    _person(ctx, "agent_run.retry")
    async with uow(ctx.tenant) as tx:
        parent = (
            await tx.session.execute(
                text(
                    "SELECT agent_id, spec_version, engagement_id, task_scope, state, "
                    "client_scope, inputs FROM agent_runs WHERE id = :run"
                ),
                {"run": run_id},
            )
        ).first()
        if parent is None:
            raise NotFound("agent_run")
        if parent.state not in _ENDED:
            raise RunNotEnded(facts={"state": str(parent.state)})
        child = (
            await tx.session.execute(
                text(
                    "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
                    "initiator_user_id, task_scope, client_scope, inputs, parent_run_id, "
                    "trigger_kind) VALUES (:t, :agent, :spec, :eng, :by, :scope, :clients, "
                    ":inputs, :parent, 'retry') RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "agent": parent.agent_id,
                    "spec": parent.spec_version,
                    "eng": parent.engagement_id,
                    "by": ctx.user_id,
                    "scope": list(parent.task_scope or []),
                    "clients": parent.client_scope,
                    "inputs": parent.inputs,
                    "parent": run_id,
                },
            )
        ).scalar_one()
        tx.record(
            "agent_run.retried",
            target=Target("agent_run", run_id),
            after=Ref(child=UUID(str(child))),
        )
    child_id = UUID(str(child))
    await dispatch(
        AgentRunWorkflow,
        AgentRunInput(str(ctx.tenant_id), str(child_id)),
        id=run_workflow_id(str(ctx.tenant_id), str(child_id)),
    )
    return child_id


__all__ = ["RunNotEnded", "StepNotFailed", "Wake", "retry_run", "retry_step", "wake"]
