"""The audit trail's platform jobs (Q-02-T20, Q-02-T21; ADR-016, ADR-017). Orchestration only:
activities by name, started only by their Schedules (overlap SKIP), so two workers never run one
twice.

- `AuditPartitions` (monthly): this month's and the next two months' `access_events` partitions.
- `AuditCheckpoint` (every 5 minutes): seals each firm's settled events into its next checkpoint.
- `AuditChainVerify` (nightly): recomputes each firm's chain; a mismatch fails the run (SEV1).
- `AuditLabelIndexer` (every 60 seconds; G-02-T10, G-02 §4.5, DEC-453): tails each firm's
  `audit_events` by `seq` into `audit_event_labels`; idempotent on `(tenant_id, seq)`. A search
  still catches its firm up by one batch first, as the fallback while a run is late or paused.

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
LABELS_ID: Final = "audit_labels:platform"
_LABELS_TIMEOUT: Final = timedelta(minutes=5)
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


@workflow.defn(name="AuditLabelIndexer")
class AuditLabelIndexerWorkflow:
    """v1 (G-02-T10 follow-up; ADR-090): one activity per run. A change to what it schedules goes
    behind `workflow.patched`, so `audit-labels-v1-indexed.json` keeps replaying."""

    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "audit_trail.index_labels",
            result_type=int,
            start_to_close_timeout=_LABELS_TIMEOUT,
            retry_policy=_RETRY,
        )
