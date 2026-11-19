"""`PostingBatchWorkflow` (C-02-T18; ADR-344; ADR-090; red): `posting:<tenant>:<batch>`, time
sensitive.

It waits out the approval grant's 10-second hold on a durable timer, then runs
`adjustments.run_posting_batch` once: the activity consumes the grant, re-reads the switches and
posts each entry with its own idempotency key, so a retried activity or a replayed history never
writes a second journal entry (an entry posted by an earlier attempt is skipped). A grant that is
not yet due raises inside the activity and is retried; a voided or refused grant fails the batch
closed with nothing written.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from abacus.modules.adjustments.posting_types import RUN, PostingInput, PostingResult

HOLD_SECONDS = 10
_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=8,
    non_retryable_error_types=["ApprovalGrantMismatch", "W1Refused", "NotFound"],
)


@workflow.defn(name="PostingBatchWorkflow")
class PostingBatchWorkflow:
    @workflow.run
    async def run(self, given: PostingInput) -> PostingResult:
        await workflow.sleep(timedelta(seconds=HOLD_SECONDS))
        status = await workflow.execute_activity(
            RUN,
            given,
            result_type=str,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=_RETRY,
        )
        return PostingResult(status)
