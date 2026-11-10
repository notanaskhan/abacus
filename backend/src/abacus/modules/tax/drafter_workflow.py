"""`ReturnDrafterWorkflow` (T-04-T25; T-04 §6; ADR-017, ADR-090). RED, v1. PROTECTED.

Orchestration only, identifiers in and out; the draft is one activity (`tax.drafter.draft`, in
`drafter_run.py` through `drafter.py`'s code rules). One run per draft
(`return-drafter:<tenant>:<run>`, reuse rejected):

1. the run is `running` (P-10's `agents.run_v2.set_state`, the run's own event sequence);
2. `tax.drafter.draft`: a missing §7216 consent answers `waiting_on_inputs`: the run waits,
   `blocked_on {kind: inputs, needs: [consent_7216]}`, with no model call, until the signal
   `inputs_ready` (the consent capture's) or a person stops it (`stop`), then drafts again;
3. a proposal ends the run `succeeded` (the proposal and its "Initial draft" checkpoint wait on
   the preparer: nothing changes until they approve); nothing to propose also ends `succeeded`
   (the self-check issues stand); a refusal ends `failed` with its code.

Versioned (ADR-090): a later change to the steps is a `workflow.patched` marker; histories are
recorded by `abacus_tools/workflows/record_return_drafter.py` (the S35 end pass, on Docker).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Final
from uuid import UUID

from sqlalchemy import text
from temporalio import activity, workflow
from temporalio.common import RetryPolicy

from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes

if TYPE_CHECKING:
    from abacus.modules.identity.api import AuthContext

with workflow.unsafe.imports_passed_through():
    from abacus.modules.tax.drafter import DRAFTER

_TIMEOUT: Final = timedelta(minutes=5)
_SHORT: Final = timedelta(seconds=30)
_RETRY: Final = RetryPolicy(maximum_attempts=3)
MAX_WAITS: Final = 3  # a run re-checks inputs at most this often before it ends failed


@dataclass(frozen=True)
class DraftInput:
    tenant_id: str
    run_id: str
    client_entity_id: str
    tax_year: int


@dataclass(frozen=True)
class DraftOutcome:
    outcome: str  # proposed · waiting_on_inputs · nothing_to_propose · refused
    needs: list[str]
    proposal_id: str | None = None
    checkpoint_id: str | None = None
    issues: int = 0
    code: str | None = None


def drafter_workflow_id(tenant_id: str, run_id: str) -> str:
    return f"return-drafter:{tenant_id}:{run_id}"


@workflow.defn(name="ReturnDrafterWorkflow")
class ReturnDrafterWorkflow:
    def __init__(self) -> None:
        self._inputs = False
        self._stop = False

    @workflow.signal(name="inputs_ready")
    def inputs_ready(self) -> None:
        """A consent was recorded for the taxpayer and year: the draft tries again."""
        self._inputs = True

    @workflow.signal(name="stop")
    def stop(self) -> None:
        self._stop = True

    async def _state(
        self, p: DraftInput, state: str, reason: str | None, blocked: dict[str, object] | None
    ) -> None:
        await workflow.execute_activity(
            "agents.run_v2.set_state",
            args=[p.tenant_id, p.run_id, state, reason, blocked],
            result_type=int,
            start_to_close_timeout=_SHORT,
            retry_policy=_RETRY,
        )

    @workflow.run
    async def run(self, p: DraftInput) -> str:
        await self._state(p, "running", None, None)
        for _ in range(MAX_WAITS + 1):
            outcome = await workflow.execute_activity(
                "tax.drafter.draft",
                p,
                result_type=DraftOutcome,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
            if outcome.outcome != "waiting_on_inputs":
                break
            await self._state(
                p, "waiting_on_inputs", "inputs", {"kind": "inputs", "needs": outcome.needs}
            )
            self._inputs = False
            await workflow.wait_condition(lambda: self._inputs or self._stop)
            if self._stop:
                await self._state(p, "cancelled", "stopped", None)
                return "cancelled"
            await self._state(p, "running", None, None)
        else:
            await self._state(p, "failed", "inputs_missing", None)
            return "failed"
        if outcome.outcome == "refused":
            await self._state(p, "failed", outcome.code or "refused", None)
            return "failed"
        await self._state(p, "succeeded", None, None)
        return outcome.outcome


@activity.defn(name="tax.drafter.draft")
async def draft_activity(p: DraftInput) -> DraftOutcome:
    from abacus.modules.agents.api import AgentRunNotRunning, load_run_v2_context
    from abacus.modules.tax.drafter_run import draft

    try:
        agent = await load_run_v2_context(UUID(p.tenant_id), UUID(p.run_id))
    except AgentRunNotRunning:
        return DraftOutcome("refused", [], code="run_ended")
    result = await draft(agent, UUID(p.client_entity_id), p.tax_year)
    return DraftOutcome(
        result.outcome,
        list(result.needs),
        str(result.proposal_id) if result.proposal_id else None,
        str(result.checkpoint_id) if result.checkpoint_id else None,
        len(result.issue_ids),
        result.code,
    )


WORKFLOWS: dict[type, WorkClass] = {ReturnDrafterWorkflow: "background"}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (draft_activity,)


async def start_draft(ctx: AuthContext, tax_return_id: UUID) -> UUID:
    """TAX-04 "Draft with Agent" (J06 step 6): a run of `tax.return_drafter` on the return's
    engagement for the person who asked (`agent_run.start`), then its workflow. Returns the run."""
    from abacus.kernel.db import tenant_session
    from abacus.kernel.errors import NotFound
    from abacus.modules.agents.api import open_capability_run
    from abacus.modules.engagements.api import entity_of

    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text("SELECT engagement_id, tax_year FROM tax_returns WHERE work_item_id = :r"),
                {"r": tax_return_id},
            )
        ).first()
    if row is None:
        raise NotFound("tax_return")
    entity = await entity_of(ctx.tenant, row.engagement_id)
    if entity is None:
        raise NotFound("tax_return")
    run_id = await open_capability_run(
        ctx,
        agent_id=DRAFTER,
        engagement_id=row.engagement_id,
        inputs={"client_entity_id": str(entity), "tax_year": int(row.tax_year)},
        work_item_ref=f"tax_return:{tax_return_id}",
    )
    await dispatch(
        ReturnDrafterWorkflow,
        DraftInput(str(ctx.tenant_id), str(run_id), str(entity), int(row.tax_year)),
        id=drafter_workflow_id(str(ctx.tenant_id), str(run_id)),
    )
    return run_id


__all__ = [
    "ACTIVITIES",
    "DRAFTER",
    "WORKFLOWS",
    "DraftInput",
    "DraftOutcome",
    "ReturnDrafterWorkflow",
    "draft_activity",
    "drafter_workflow_id",
    "start_draft",
]
