"""`JeScoringWorkflow` (A-08-T12; SPEC-657 F1; ADR-090): one JE test's scoring run. Orchestration
only: the activity `je_scoring.run` reads the proved population, scores every entry with the
frozen engine and stores the run and its scores in one transaction; a failure after the retries
marks the test `failed` with its code, never a partial run. Started only through
`kernel.dispatch` (DISPATCH-001); a change here lands behind `workflow.patched(...)` so the
recorded v1 histories keep replaying."""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from abacus.modules.sampling.je_scoring_types import JeScoringInput

# AC-1.2's budget: a 412,903-line population scores within 10 minutes on staging.
_TIMEOUT = timedelta(minutes=10)
_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=2,
)


@workflow.defn(name="je_scoring")
class JeScoringWorkflow:
    """Scores one `scoring` test to `scored`, or marks it `failed`."""

    @workflow.run
    async def run(self, input: JeScoringInput) -> str:
        try:
            return await workflow.execute_activity(
                "je_scoring.run",
                input,
                result_type=str,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        except ActivityError:
            await workflow.execute_activity(
                "je_scoring.fail",
                input,
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(maximum_attempts=0),
            )
            return "failed"
