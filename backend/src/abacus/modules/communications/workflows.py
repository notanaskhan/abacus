"""The SES delivery-event drain (Q-01-T46) and a sender domain's verification (R-01-T27; ADR-017,
ADR-090). PROTECTED.

Orchestration only, activities by name. `DrainSesEvents` runs as `ses_events:platform` every
minute; each run drains what is queued (`deliveries.drain_ses_events`), idempotent on the
provider event id. `SendingDomainVerification` (`sending_domain:<tenant>:<domain>`, started when a
domain is created) checks the domain every 15 minutes until it is no longer `pending_dns`: the
activity (`sending_domains.refresh`) fails it after 72 hours. One day of checks per run, then
`ContinueAsNew`. v1, recorded in its replay history.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Final

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


CHECK_EVERY: Final = timedelta(minutes=15)
CHECKS_PER_RUN: Final = 96  # one day
_CHECK_TIMEOUT = timedelta(minutes=2)
_CHECK_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=10),
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=5,
    non_retryable_error_types=["NotFound"],
)


@dataclass(frozen=True)
class SendingDomainVerificationInput:
    """Identifiers only (ADR-017): the firm and its domain row."""

    tenant_id: str
    domain_id: str
    checks: int = 0  # checks made by earlier runs (ContinueAsNew)


@workflow.defn(name="SendingDomainVerification")
class SendingDomainVerificationWorkflow:
    @workflow.run
    async def run(self, given: SendingDomainVerificationInput) -> str:
        checks = 0
        while True:
            status = await workflow.execute_activity(
                "communications.check_sending_domain",
                given,
                result_type=str,
                start_to_close_timeout=_CHECK_TIMEOUT,
                retry_policy=_CHECK_RETRY,
            )
            checks += 1
            if status != "pending_dns":
                return status
            if checks >= CHECKS_PER_RUN:
                workflow.continue_as_new(
                    SendingDomainVerificationInput(
                        given.tenant_id, given.domain_id, given.checks + checks
                    )
                )
            await workflow.sleep(CHECK_EVERY)
