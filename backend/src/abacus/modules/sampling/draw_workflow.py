"""`SampleDrawWorkflow` (A-03-T10; A-03 §4.4; ADR-340, ADR-090): one version's draw. Orchestration
only: the activity `sample_draw.run` re-checks the population's ties, selects with the frozen
sampler and persists the strata and items in one transaction, then marks the version a draft. A
failure after the retries marks it `failed` with its code, never a partial item list. Started
only through `kernel.dispatch` (DISPATCH-001); a change here lands behind `workflow.patched(...)`
so the recorded v1 histories keep replaying."""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from abacus.modules.sampling.draw_types import SampleDrawInput

_TIMEOUT = timedelta(minutes=10)
_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=3,
)


@workflow.defn(name="sample_draw")
class SampleDrawWorkflow:
    """Draws one `drawing` version to `draft`, or marks it `failed`."""

    @workflow.run
    async def run(self, input: SampleDrawInput) -> str:
        try:
            return await workflow.execute_activity(
                "sample_draw.run",
                input,
                result_type=str,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        except ActivityError:
            await workflow.execute_activity(
                "sample_draw.fail",
                input,
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(maximum_attempts=0),
            )
            return "failed"
