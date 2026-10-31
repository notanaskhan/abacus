"""`K1ReleaseWorkflow` (T-02-T21; T-02 §4.11; ADR-017, ADR-090; DEC-1476). RED, v1.

Orchestration only, identifiers in and out; every read and write is an activity in
`tax/k1_release.py`. One run per release (`k1_release:<tenant>:<return>:<release_id>`, reuse
rejected):

1. sleep out the Undo window on a durable timer (the business clock decides in the activity);
2. `schedule_k_release.start` consumes the single-use approval grant: an Undo voided it, so the
   run ends `undone` with nothing sent; a refused grant ends `failed`;
3. one `schedule_k_release.deliver` per package, in order, each idempotent on
   `(release_id, package_id)` through the release's ledger: contact, the `k1_recipient` grant or
   invitation, `released`, the "Deliverable ready" email (sent once: a replay finds it recorded),
   and the hand-off drafts replaced by the final with its values copied;
4. `schedule_k_release.complete`.

A delivery that fails after its retries ends the run in `schedule_k_release.fail`; the recipients
already delivered stay released, and a second release of what is left sends nothing twice. No
model call anywhere (DEC-79).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

DELIVERY_FAILED = "delivery_failed"
START_FAILED = "start_failed"


@dataclass(frozen=True)
class K1ReleaseInput:
    """The release, and how long its Undo window still runs."""

    tenant_id: str
    release_id: str
    wait_seconds: int


@dataclass(frozen=True)
class K1DeliveryInput:
    tenant_id: str
    release_id: str
    package_id: str


@dataclass(frozen=True)
class K1ReleaseFailure:
    tenant_id: str
    release_id: str
    failure_code: str


_TIMEOUT = timedelta(minutes=3)
# The grant answers "not yet" until `not_before` on the database's clock: retried, never voided.
_START_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=20,
)
_DELIVER_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=2),
    maximum_attempts=8,
    non_retryable_error_types=["DeliveryRefused"],
)
# Stamping the outcome is retried until it lands: a release never stays `running`.
_STAMP_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=10),
    maximum_attempts=0,
)


def workflow_id(tenant_id: str, return_id: str, release_id: str) -> str:
    return f"k1_release:{tenant_id}:{return_id}:{release_id}"


@workflow.defn(name="k1_release")
class K1ReleaseWorkflow:
    @workflow.run
    async def run(self, given: K1ReleaseInput) -> str:
        if given.wait_seconds > 0:
            await workflow.sleep(timedelta(seconds=given.wait_seconds))
        try:
            started = await workflow.execute_activity(
                "schedule_k_release.start",
                given,
                result_type=str,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_START_RETRY,
            )
        except ActivityError:
            return await self._failed(given, START_FAILED)
        if started != "running":
            return started
        packages = await workflow.execute_activity(
            "schedule_k_release.packages",
            given,
            result_type=list[str],
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_STAMP_RETRY,
        )
        for package_id in packages:
            try:
                await workflow.execute_activity(
                    "schedule_k_release.deliver",
                    K1DeliveryInput(given.tenant_id, given.release_id, package_id),
                    result_type=str,
                    start_to_close_timeout=_TIMEOUT,
                    retry_policy=_DELIVER_RETRY,
                )
            except ActivityError:
                return await self._failed(given, DELIVERY_FAILED)
        return await workflow.execute_activity(
            "schedule_k_release.complete",
            given,
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_STAMP_RETRY,
        )

    async def _failed(self, given: K1ReleaseInput, code: str) -> str:
        return await workflow.execute_activity(
            "schedule_k_release.fail",
            K1ReleaseFailure(given.tenant_id, given.release_id, code),
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_STAMP_RETRY,
        )


__all__ = [
    "DELIVERY_FAILED",
    "START_FAILED",
    "K1DeliveryInput",
    "K1ReleaseFailure",
    "K1ReleaseInput",
    "K1ReleaseWorkflow",
    "workflow_id",
]
