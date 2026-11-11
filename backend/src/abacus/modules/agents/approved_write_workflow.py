"""`ApprovedWriteWorkflow` (P-10-T38; SPEC-647 AC-P1 to AC-P3; ADR-090, ADR P-35; DEC-3402).
PROTECTED (agents). Id `approved_write:<tenant>:<grant>`; started only through `kernel.dispatch`
by `approved_writes.on_proposal_event` (DISPATCH-001).

It sleeps the Undo window (`not_before = decided_at + 10 s`), then runs one activity that spends
the grant through C17's runtime. Identifiers and codes only enter the history.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from temporalio import workflow
from temporalio.common import RetryPolicy

UNDO_WINDOW: Final = timedelta(seconds=10)  # DEC-24


@dataclass(frozen=True)
class ApprovedWriteInput:
    tenant_id: str
    run_id: str
    proposal_id: str
    grant_id: str
    tool: str


def approved_write_id(tenant_id: str, grant_id: str) -> str:
    return f"approved_write:{tenant_id}:{grant_id}"


@workflow.defn(name="ApprovedWriteWorkflow")
class ApprovedWriteWorkflow:
    """Sleeps the Undo window, then spends the grant once through C17 (identifiers only)."""

    @workflow.run
    async def run(self, p: ApprovedWriteInput) -> str:
        await workflow.sleep(UNDO_WINDOW + timedelta(seconds=1))
        return await workflow.execute_activity(
            "agents.approved_write.execute",
            args=[p],
            result_type=str,
            start_to_close_timeout=timedelta(minutes=2),
            # An early grant (`GrantNotYetDue`) or an outage retries; a refusal is an outcome.
            retry_policy=RetryPolicy(
                maximum_attempts=10,
                initial_interval=timedelta(seconds=2),
                backoff_coefficient=1.5,
            ),
        )
