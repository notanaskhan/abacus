"""`FsDraftWorkflow` and `TieOutWorkflow` (A-06-T25; A-06 §4.5; ADR-090): code does the work in one
activity each, proving its context from the rows. Nothing but Temporal and the input types is
imported here, so the sandbox can load this module. A change goes behind `workflow.patched(...)`.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from abacus.modules.reporting.statements_workflow_types import FsDraftInput, TieOutInput

_RETRY = RetryPolicy(maximum_attempts=5)
_TIMEOUT = timedelta(minutes=5)
DRAFT_ACTIVITY = "statements.draft"
DRAFT_FAILED_ACTIVITY = "statements.draft_failed"
TIE_OUT_ACTIVITY = "statements.tie_out"


@workflow.defn(name="fs_draft")
class FsDraftWorkflow:
    @workflow.run
    async def run(self, given: FsDraftInput) -> str:
        try:
            return await workflow.execute_activity(
                DRAFT_ACTIVITY,
                given,
                result_type=str,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        except ActivityError:
            await workflow.execute_activity(
                DRAFT_FAILED_ACTIVITY,
                given,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
            raise


@workflow.defn(name="tie_out")
class TieOutWorkflow:
    @workflow.run
    async def run(self, given: TieOutInput) -> str:
        return await workflow.execute_activity(
            TIE_OUT_ACTIVITY,
            given,
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
