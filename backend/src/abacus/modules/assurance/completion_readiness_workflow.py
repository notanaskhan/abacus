"""CompletionReadinessWorkflow (#4231; A-07 §4.5; S33 partials round of A-07-T32; DEC-3138):
`completion_readiness:<tenant>:<work item>`, class `interactive`.

The checklist projector starts it when a burst of facts changes an item (the first change of a
burst; later changes attach to the waiting run, `USE_EXISTING`). It waits 60 seconds so the burst
settles, then runs the code-only readiness check as the engagement partner via Agent (the timer
has no person; A-07 §6 #4231): narration only, nothing decided. A run already finished lets the
next burst start a new one (`ALLOW_DUPLICATE`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Final
from uuid import UUID

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from abacus.kernel.db import TenantContext

DEBOUNCE: Final = timedelta(seconds=60)
ID_PREFIX: Final = "completion_readiness:"


@dataclass(frozen=True)
class ReadinessInput:
    tenant_id: str
    work_item_id: str


def workflow_id(tenant_id: UUID, work_item_id: UUID) -> str:
    return f"{ID_PREFIX}{tenant_id}:{work_item_id}"


@activity.defn(name="assurance.completion_readiness")
async def readiness_activity(params: ReadinessInput) -> str | None:
    from abacus.modules.assurance.agent_capabilities import record_readiness_as_partner

    tenant = TenantContext(UUID(params.tenant_id), "system", "completion_readiness")
    run = await record_readiness_as_partner(tenant, UUID(params.work_item_id))
    return None if run is None else str(run)


@workflow.defn(name="CompletionReadinessWorkflow")
class CompletionReadinessWorkflow:
    """Wait out the burst, then the readiness run (#4231)."""

    @workflow.run
    async def run(self, params: ReadinessInput) -> str | None:
        await workflow.sleep(DEBOUNCE)
        return await workflow.execute_activity(
            "assurance.completion_readiness",
            params,
            result_type=str | None,  # type: ignore[arg-type]  # an optional run id
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )


WORKFLOWS: Final[dict[type, str]] = {CompletionReadinessWorkflow: "interactive"}
ACTIVITIES: Final[tuple[object, ...]] = (readiness_activity,)
