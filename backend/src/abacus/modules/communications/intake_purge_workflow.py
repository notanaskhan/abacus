"""`IntakeWithdrawalPurge` (N-01-T14; ADR-162 §7; DEC-1060): P-06's withdrawal purge, for a portal
intake upload. `intake_withdrawal:<tenant>:<upload>`: sleep through the 30 days on a durable
timer, then ask the erase activity, which destroys each withdrawn file's key and answers 0, or
how many seconds to wait (a day while a hold covers a file or no hold check is registered: fail
closed). Identifiers only in the history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

_TIMEOUT = timedelta(minutes=2)
_RETRY = RetryPolicy(maximum_attempts=0, maximum_interval=timedelta(hours=1))
WINDOW_SECONDS = 30 * 24 * 3600
ATTEMPTS_PER_RUN = 30


@dataclass(frozen=True)
class IntakePurgeInput:
    tenant_id: str
    upload_id: str
    wait_seconds: int = WINDOW_SECONDS
    attempts: int = 0


def intake_purge_id(tenant_id: str, upload_id: str) -> str:
    return f"intake_withdrawal:{tenant_id}:{upload_id}"


@workflow.defn(name="IntakeWithdrawalPurge")
class IntakeWithdrawalPurgeWorkflow:
    @workflow.run
    async def run(self, given: IntakePurgeInput) -> int:
        wait, attempts = given.wait_seconds, given.attempts
        while True:
            if wait > 0:
                await workflow.sleep(timedelta(seconds=wait))
            wait = await workflow.execute_activity(
                "communications.erase_withdrawn_intake",
                given,
                result_type=int,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
            attempts += 1
            if wait <= 0:
                return attempts
            if attempts - given.attempts >= ATTEMPTS_PER_RUN:
                workflow.continue_as_new(
                    IntakePurgeInput(given.tenant_id, given.upload_id, wait, attempts)
                )
