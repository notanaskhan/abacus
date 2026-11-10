"""`NoticeAnalysisWorkflow` (`notice_analysis:<tenant>:<notice>:<n>`; N-04-T11, N-04 §4.5; ADR-090;
DEC-2359). Background. A person's Run wrote a `running` version and the outbox started this; one
activity loads, computes, locates citations, runs the agent step and writes the `ready` version,
retried because it answers the same on the same inputs. Out of retries, a `failed` version stops
NOT-02's spinner. Temporal being down delays the analysis and never fails the person's click; a
change lands behind `workflow.patched(...)`.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from abacus.modules.notices.analysis_workflow_types import NoticeAnalysisInput

_RETRY = RetryPolicy(maximum_attempts=5)
_RUN_TIMEOUT = timedelta(minutes=5)
_MARK_TIMEOUT = timedelta(minutes=1)


@workflow.defn(name="notice_analysis")
class NoticeAnalysisWorkflow:
    @workflow.run
    async def run(self, given: NoticeAnalysisInput) -> str:
        try:
            return await workflow.execute_activity(
                "notice_analysis.run",
                given,
                result_type=str,
                start_to_close_timeout=_RUN_TIMEOUT,
                retry_policy=_RETRY,
            )
        except ActivityError:
            return await workflow.execute_activity(
                "notice_analysis.mark_failed",
                given,
                result_type=str,
                start_to_close_timeout=_MARK_TIMEOUT,
                retry_policy=_RETRY,
            )
