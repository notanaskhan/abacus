"""The due-soon half of TaxCalendarSweep (T-03-T07; T-03 §3 F5; DEC-2350), on a daily platform
Schedule. The date half runs on `reference_set.published` (`extensions.recompute_open_lines`).
Orchestration only: the Temporal sandbox imports this module, so anything else lives in
`schedule_jobs.py`."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from temporalio import workflow
from temporalio.common import RetryPolicy

DUE_SOON_ID: Final = "tax_estimates_due_soon:platform"
_TIMEOUT: Final = timedelta(minutes=10)
_RETRY: Final = RetryPolicy(maximum_attempts=3)


@workflow.defn(name="TaxCalendarSweepWorkflow")
class TaxCalendarSweepWorkflow:
    """Started only by its Schedule (overlap SKIP); the event's key makes a repeat harmless."""

    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "tax_estimates.send_due_soon",
            result_type=int,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
