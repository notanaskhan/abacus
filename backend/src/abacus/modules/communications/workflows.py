"""The SES delivery-event drain (Q-01-T46; ADR-017, ADR-090). PROTECTED.

Orchestration only: one activity by name per run. Run as `ses_events:platform` every minute; each
run drains what is queued (`deliveries.drain_ses_events`), idempotent on the provider event id.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

_TIMEOUT = timedelta(seconds=50)
_RETRY = RetryPolicy(maximum_attempts=3)


@workflow.defn(name="DrainSesEvents")
class DrainSesEventsWorkflow:
    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "communications.drain_ses_events",
            result_type=int,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
