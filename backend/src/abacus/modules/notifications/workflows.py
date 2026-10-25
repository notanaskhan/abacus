"""`NotificationEmail` (P-01-T12; C16; ADR-017, ADR-090): one notification's email, once.

Orchestration only, activities by name. Started by the fan-out (`email.py`) through
`kernel.dispatch` with the id `notification_email:<tenant>:<notification_id>`, so a redelivered
event starts nothing twice. Its two activities:
- `notifications.send_email` proves the delivery from its row (still `queued`, the kill switch
  still on, the recipient not walled), renders the C16 template and sends through
  communications (the sink rule and suppression apply there). Rendering happens inside it, so
  no name, address or text enters the workflow history.
- `notifications.record_delivery` writes the outcome on the delivery row with its audit event.
  It runs on every path, a failed send included, with unlimited retries, so a delivery never
  stays `queued`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

_SEND_TIMEOUT = timedelta(seconds=60)
_SEND_RETRY = RetryPolicy(maximum_attempts=5, non_retryable_error_types=["TransportRefused"])
_RECORD_TIMEOUT = timedelta(seconds=30)
_RECORD_RETRY = RetryPolicy(maximum_attempts=0)  # unlimited: the outcome is always written


@dataclass(frozen=True)
class NotificationEmailInput:
    tenant_id: str
    notification_id: str


@dataclass(frozen=True)
class DeliveryOutcome:
    tenant_id: str
    notification_id: str
    outcome: str  # sent | suppressed | failed | the row's status when it was no longer queued


def notification_email_id(tenant_id: str, notification_id: str) -> str:
    return f"notification_email:{tenant_id}:{notification_id}"


@workflow.defn(name="NotificationEmail")
class NotificationEmailWorkflow:
    @workflow.run
    async def run(self, given: NotificationEmailInput) -> str:
        try:
            outcome = await workflow.execute_activity(
                "notifications.send_email",
                given,
                result_type=str,
                start_to_close_timeout=_SEND_TIMEOUT,
                retry_policy=_SEND_RETRY,
            )
        except ActivityError:
            outcome = "failed"
        await workflow.execute_activity(
            "notifications.record_delivery",
            DeliveryOutcome(given.tenant_id, given.notification_id, outcome),
            result_type=str,
            start_to_close_timeout=_RECORD_TIMEOUT,
            retry_policy=_RECORD_RETRY,
        )
        return outcome


# Q-01-T26: the daily purge (SPEC-013 AC-10), one pass per run on a Schedule, never a worker loop.
NOTIFICATION_PURGE_ID = "notification_purge:platform"
_PURGE_TIMEOUT = timedelta(minutes=5)
_PURGE_RETRY = RetryPolicy(maximum_attempts=3)  # a failed day is retried by the next run


@workflow.defn(name="NotificationPurge")
class NotificationPurgeWorkflow:
    """`notification_purge:platform`: one purge pass, audited as the system. Started only by its
    Schedule (overlap SKIP), so two workers never purge twice."""

    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "notifications.purge_expired",
            result_type=int,
            start_to_close_timeout=_PURGE_TIMEOUT,
            retry_policy=_PURGE_RETRY,
        )
