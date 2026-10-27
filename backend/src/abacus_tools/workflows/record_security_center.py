"""Record the G-02 security-center workflows' replay histories (G-02-T17 to T20; ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_security_center <output-directory> [version]

Records runs of the real workflows against throwaway containers, with their activities replaced
by stubs (replay never runs activities):
- `audit-export-<v>-ready.json`: the bundle built and `mark_ready`;
- `audit-export-<v>-failed.json`: the build fails `requester_not_member` (decided, not retried)
  and `mark_failed` records it;
- `incident-reminders-<v>-sent.json`: one reminder pass that sent two reminders;
- `firm-export-schedule-<v>-skipped.json`: one monthly run with no firm export starter yet;
- `wisp-pack-<v>-ready.json` and `wisp-pack-<v>-failed.json` (`wisp_missing`, decided).
Synthetic identifiers only. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHandle, WorkflowHistory
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.audit_trail.api import (
    AuditExportFacts,
    AuditExportFailure,
    AuditExportInput,
    AuditExportWorkflow,
)
from abacus.modules.evidence.api import FirmExportScheduleWorkflow
from abacus.modules.platform.api import (
    INCIDENT_REMINDERS_ID,
    IncidentClockRemindersWorkflow,
    WispPackFacts,
    WispPackFailure,
    WispPackInput,
    WispPackWorkflow,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-4000-8000-000000000001"
_READY = "00000000-0000-4000-8000-0000000000f1"
_FAILED = "00000000-0000-4000-8000-0000000000f2"
_NAMES = (
    "audit-export-{v}-ready.json",
    "audit-export-{v}-failed.json",
    "incident-reminders-{v}-sent.json",
    "firm-export-schedule-{v}-skipped.json",
    "wisp-pack-{v}-ready.json",
    "wisp-pack-{v}-failed.json",
)


@activity.defn(name="audit_export.build")
async def _build(given: AuditExportInput) -> AuditExportFacts:
    if given.export_id == _FAILED:
        raise ApplicationError(
            "requester_not_member", type="requester_not_member", non_retryable=True
        )
    return AuditExportFacts(
        tenant_id=given.tenant_id,
        export_id=given.export_id,
        row_count=1284,
        seq_from=10412,
        seq_to=11695,
        csv_sha256="1" * 64,
        manifest_sha256="2" * 64,
        bundle_bytes=184320,
        segment_count=1,
        signature_key_ref="alias/abacus/recorder/export-signing",
    )


@activity.defn(name="audit_export.mark_ready")
async def _export_ready(facts: AuditExportFacts) -> str:
    return "ready"


@activity.defn(name="audit_export.mark_failed")
async def _export_failed(failure: AuditExportFailure) -> str:
    return "failed"


@activity.defn(name="platform.incident_reminders")
async def _reminders() -> int:
    return 2


@activity.defn(name="evidence.firm_export_scheduled_run")
async def _scheduled(tenant_id: str) -> str:
    return "skipped"


@activity.defn(name="platform.wisp_pack_build")
async def _pack(given: WispPackInput) -> WispPackFacts:
    if given.pack_id == _FAILED:
        raise ApplicationError("wisp_missing", type="wisp_missing", non_retryable=True)
    return WispPackFacts(given.tenant_id, given.pack_id, 14, 2621440, 1)


@activity.defn(name="platform.wisp_pack_ready")
async def _pack_ready(facts: WispPackFacts) -> str:
    return "ready"


@activity.defn(name="platform.wisp_pack_failed")
async def _pack_failed(failure: WispPackFailure) -> str:
    return "failed"


async def _history(client: Client, name: str, arg: object, workflow_id: str) -> WorkflowHistory:
    """Start the workflow by its registered name (one helper for four signatures)."""
    handle: WorkflowHandle[object, object] = await client.start_workflow(
        name,
        args=[] if arg is None else [arg],
        id=workflow_id,
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    runs: tuple[tuple[str, str, object, str], ...] = (
        (
            _NAMES[0],
            "audit_export",
            AuditExportInput(_TENANT, _READY),
            f"audit_export:{_TENANT}:{_READY}",
        ),
        (
            _NAMES[1],
            "audit_export",
            AuditExportInput(_TENANT, _FAILED),
            f"audit_export:{_TENANT}:{_FAILED}",
        ),
        (_NAMES[2], "IncidentClockReminders", None, INCIDENT_REMINDERS_ID),
        (
            _NAMES[3],
            "FirmExportSchedule",
            _TENANT,
            f"firm_export_schedule:{_TENANT}",
        ),
        (
            _NAMES[4],
            "wisp_pack",
            WispPackInput(_TENANT, _READY),
            f"wisp_pack:{_TENANT}:{_READY}",
        ),
        (
            _NAMES[5],
            "wisp_pack",
            WispPackInput(_TENANT, _FAILED),
            f"wisp_pack:{_TENANT}:{_FAILED}",
        ),
    )
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[
            AuditExportWorkflow,
            IncidentClockRemindersWorkflow,
            FirmExportScheduleWorkflow,
            WispPackWorkflow,
        ],
        activities=[
            *(_build, _export_ready, _export_failed, _reminders, _scheduled),
            *(_pack, _pack_ready, _pack_failed),
        ],
    ):
        for name, run, arg, workflow_id in runs:
            scrubbed = await decoded_and_scrubbed(
                await _history(client, run, arg, workflow_id), payload_codec()
            )
            path = out / name.format(v=version)
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [name.format(v=version) for name in _NAMES]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
