"""The audit trail's platform jobs (Q-02-T20, Q-02-T21; ADR-016, ADR-017). Orchestration only:
activities by name, started only by their Schedules (overlap SKIP), so two workers never run one
twice.

- `AuditPartitions` (monthly): this month's and the next two months' `access_events` partitions.
- `AuditCheckpoint` (every 5 minutes): seals each firm's settled events into its next checkpoint.
- `AuditChainVerify` (nightly): recomputes each firm's chain; a mismatch fails the run (SEV1).

The daily anchor to the records bucket is evidence's (`evidence/anchor_job.py`): evidence owns
the records bucket and the audit trail may not depend on it (ADR-008).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from temporalio import workflow
from temporalio.common import RetryPolicy

PARTITIONS_ID: Final = "audit_partitions:platform"
CHECKPOINT_ID: Final = "audit_checkpoint:platform"
VERIFY_ID: Final = "audit_chain_verify:platform"
_TIMEOUT: Final = timedelta(minutes=10)
_VERIFY_TIMEOUT: Final = timedelta(minutes=50)
_RETRY: Final = RetryPolicy(maximum_attempts=3)  # a failed run is retried by the next one
# A mismatch is a finding, not a fault: retrying would only report it again.
_VERIFY_RETRY: Final = RetryPolicy(
    maximum_attempts=3, non_retryable_error_types=["AuditChainMismatch"]
)


@workflow.defn(name="AuditPartitions")
class AuditPartitionsWorkflow:
    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "audit_trail.ensure_partitions",
            result_type=int,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )


@workflow.defn(name="AuditCheckpoint")
class AuditCheckpointWorkflow:
    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "audit_trail.seal_checkpoints",
            result_type=int,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )


@workflow.defn(name="AuditChainVerify")
class AuditChainVerifyWorkflow:
    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "audit_trail.verify_chains",
            result_type=int,
            start_to_close_timeout=_VERIFY_TIMEOUT,
            retry_policy=_VERIFY_RETRY,
        )
