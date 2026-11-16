"""`RequestPublishWorkflow` (C-01-T19; C-01 §4.5; ADR-090; amber): `close_requests:<tenant>:<close>`.

Started when a close is generated. It asks `closes.requests_seconds_until` how long to sleep (the
BD1 09:00 firm-time instant is computed in the activity, from the practice calendar and the firm's
zone, so replay stays deterministic), sleeps on a durable timer, then runs
`closes.publish_requests` (pin, generate, publish; idempotent). A `recompute` signal (a plan
published before BD1) wakes it to ask again: only the wait changes, never what was published. It
ends once the requests are published or there is nothing to do (-1).
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from abacus.modules.closes.request_publish_types import (
        PUBLISH,
        RECOMPUTE,
        SECONDS_UNTIL,
        PublishInput,
        PublishResult,
    )

_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=0,  # publishing at BD1 must not give up; each attempt is idempotent
)


@workflow.defn(name="RequestPublishWorkflow")
class RequestPublishWorkflow:
    def __init__(self) -> None:
        self._recompute = False

    @workflow.signal(name=RECOMPUTE)
    def recompute(self) -> None:
        self._recompute = True

    @workflow.run
    async def run(self, given: PublishInput) -> PublishResult:
        while True:
            self._recompute = False
            wait = await workflow.execute_activity(
                SECONDS_UNTIL,
                given,
                result_type=int,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=10),
            )
            if wait < 0:
                return PublishResult(0)
            if wait > 0:
                try:
                    await workflow.wait_condition(
                        lambda: self._recompute, timeout=timedelta(seconds=wait)
                    )
                    continue  # a plan changed before BD1: ask again
                except TimeoutError:
                    pass
            return await workflow.execute_activity(
                PUBLISH,
                given,
                result_type=PublishResult,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=_RETRY,
            )
