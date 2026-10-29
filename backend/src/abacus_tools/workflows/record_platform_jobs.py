"""Record the platform jobs' replay histories (Q-01-T26; ADR-090). See `histories.py` for the
fixture rules.

Run: python -m abacus_tools.workflows.record_platform_jobs <output-directory>

Records the real `SpendAnomalyWorkflow`, `NotificationPurgeWorkflow`, `DrainSesEventsWorkflow`,
`AccessEndSweepWorkflow`, the audit trail's five jobs and the export expiry sweep against
throwaway containers, with their activities replaced by stubs (replay never runs activities):
- `spend-anomaly-v1-flagged.json`: one pass that flagged one engagement;
- `notification-purge-v1-purged.json`: one pass that purged three notifications;
- `ses-drain-v1-drained.json`: one drain that recorded two delivery events (Q-01-T46's workflow,
  first started by its Schedule in Q-01-T26);
- `access-end-v1-swept.json`: one access-end pass that ended five members (G-01-T13);
- `audit-partitions-v1-ensured.json`, `audit-checkpoint-v1-sealed.json`,
  `audit-chain-verify-v1-verified.json`, `audit-anchor-v1-anchored.json`: one pass of each
  (Q-02-T20, T21);
- `audit-labels-v1-indexed.json`: one label-index pass that indexed seven events (G-02-T10,
  DEC-453);
- `auth-session-purge-v1-purged.json`: one purge pass that deleted six staff sessions (G-02-T14).
- `export-expiry-v1-swept.json`: one export expiry sweep that expired four exports (A-01-T22).
- `home-activity-prune-v1-pruned.json`: one Home client-activity prune that deleted five rows
  (I-01-T12).
Each run is started the way its Schedule starts it: no argument, its own id. A history already on
disk is never overwritten: only the missing ones are recorded.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHandle, WorkflowHistory
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.audit_trail.api import (
    CHECKPOINT_ID,
    LABELS_ID,
    PARTITIONS_ID,
    VERIFY_ID,
    AuditChainVerifyWorkflow,
    AuditCheckpointWorkflow,
    AuditLabelIndexerWorkflow,
    AuditPartitionsWorkflow,
)
from abacus.modules.communications.api import SES_EVENTS_ID, DrainSesEventsWorkflow
from abacus.modules.evidence.api import (
    ANCHOR_ID,
    EXPORT_EXPIRY_ID,
    AuditAnchorWorkflow,
    ExportExpirySweepWorkflow,
)
from abacus.modules.identity.api import (
    ACCESS_END_ID,
    AUTH_SESSION_PURGE_ID,
    AccessEndSweepWorkflow,
    AuthSessionPurgeWorkflow,
)
from abacus.modules.notifications.api import NOTIFICATION_PURGE_ID, NotificationPurgeWorkflow
from abacus.modules.platform.api import SPEND_ANOMALY_ID, SpendAnomalyWorkflow
from abacus.modules.practice.api import HOME_ACTIVITY_PRUNE_ID, HomeActivityPruneWorkflow
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

_TASK_QUEUE = "abacus-recorder"
_FILES = (
    "spend-anomaly-v1-flagged.json",
    "notification-purge-v1-purged.json",
    "ses-drain-v1-drained.json",
    "access-end-v1-swept.json",
    "audit-partitions-v1-ensured.json",
    "audit-checkpoint-v1-sealed.json",
    "audit-chain-verify-v1-verified.json",
    "audit-anchor-v1-anchored.json",
    "audit-labels-v1-indexed.json",
    "auth-session-purge-v1-purged.json",
    "export-expiry-v1-swept.json",
    "home-activity-prune-v1-pruned.json",
)


@activity.defn(name="platform.flag_spend_anomalies")
async def _flag() -> int:
    return 1


@activity.defn(name="notifications.purge_expired")
async def _purge() -> int:
    return 3


@activity.defn(name="communications.drain_ses_events")
async def _drain() -> int:
    return 2


@activity.defn(name="identity.sweep_access_ends")
async def _sweep() -> int:
    return 5


@activity.defn(name="audit_trail.ensure_partitions")
async def _partitions() -> int:
    return 3


@activity.defn(name="audit_trail.seal_checkpoints")
async def _seal() -> int:
    return 2


@activity.defn(name="audit_trail.verify_chains")
async def _verify() -> int:
    return 4


@activity.defn(name="evidence.anchor_chains")
async def _anchor() -> int:
    return 2


@activity.defn(name="audit_trail.index_labels")
async def _labels() -> int:
    return 7


@activity.defn(name="identity.purge_auth_sessions")
async def _purge_sessions() -> int:
    return 6


@activity.defn(name="engagement_export.expire_sweep")
async def _expire() -> int:
    return 4


@activity.defn(name="practice.prune_home_activity")
async def _prune_activity() -> int:
    return 5


async def _run(client: Client, workflow: type, workflow_id: str) -> WorkflowHistory:
    handle: WorkflowHandle[object, int] = await client.start_workflow(
        workflow.run,  # pyright: ignore[reportUnknownArgumentType,reportUnknownMemberType] -- a @workflow.defn class
        id=workflow_id,
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[
            SpendAnomalyWorkflow,
            NotificationPurgeWorkflow,
            DrainSesEventsWorkflow,
            AccessEndSweepWorkflow,
            AuditPartitionsWorkflow,
            AuditCheckpointWorkflow,
            AuditChainVerifyWorkflow,
            AuditAnchorWorkflow,
            AuditLabelIndexerWorkflow,
            AuthSessionPurgeWorkflow,
            ExportExpirySweepWorkflow,
            HomeActivityPruneWorkflow,
        ],
        activities=[
            *(_flag, _purge, _drain, _sweep, _partitions, _seal, _verify, _anchor, _labels),
            _purge_sessions,
            _expire,
            _prune_activity,
        ],
    ):
        runs = (
            (SpendAnomalyWorkflow, SPEND_ANOMALY_ID, _FILES[0]),
            (NotificationPurgeWorkflow, NOTIFICATION_PURGE_ID, _FILES[1]),
            (DrainSesEventsWorkflow, SES_EVENTS_ID, _FILES[2]),
            (AccessEndSweepWorkflow, ACCESS_END_ID, _FILES[3]),
            (AuditPartitionsWorkflow, PARTITIONS_ID, _FILES[4]),
            (AuditCheckpointWorkflow, CHECKPOINT_ID, _FILES[5]),
            (AuditChainVerifyWorkflow, VERIFY_ID, _FILES[6]),
            (AuditAnchorWorkflow, ANCHOR_ID, _FILES[7]),
            (AuditLabelIndexerWorkflow, LABELS_ID, _FILES[8]),
            (AuthSessionPurgeWorkflow, AUTH_SESSION_PURGE_ID, _FILES[9]),
            (ExportExpirySweepWorkflow, EXPORT_EXPIRY_ID, _FILES[10]),
            (HomeActivityPruneWorkflow, HOME_ACTIVITY_PRUNE_ID, _FILES[11]),
        )
        for workflow, workflow_id, name in runs:
            if (out / name).exists():
                continue
            scrubbed = await decoded_and_scrubbed(
                await _run(client, workflow, workflow_id), payload_codec()
            )
            path = out / name
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if all((out / name).exists() for name in _FILES):
        print("every platform-job history is recorded; nothing to do")
        return 0

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
