"""Record the engagement export's replay histories (A-01-T19; A-01 §4.5; ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_engagement_export <output-directory> [version]

Records runs of the real workflow against throwaway containers, with its activities replaced by
stubs (replay never runs activities): the Undo window's timer (a second here, from the input),
then
- `engagement-export-<version>-ready.json`: the grant consumed, the snapshot, the package and
  `mark_ready`;
- `engagement-export-<version>-undone.json`: an Undo voided the grant, so the run ends there;
- `engagement-export-<version>-integrity-mismatch.json`: the package fails `integrity_mismatch`
  (decided, not retried) and `mark_failed` records it.
Synthetic identifiers only. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.evidence.api import (
    EngagementExportInput,
    EngagementExportWorkflow,
    ExportBuildFailure,
    ExportPackageFacts,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-4000-8000-000000000001"
_EXPORTS = {
    "ready": "00000000-0000-4000-8000-0000000000e1",
    "undone": "00000000-0000-4000-8000-0000000000e2",
    "integrity-mismatch": "00000000-0000-4000-8000-0000000000e3",
}
_NAME = "engagement-export-{v}-{case}.json"


@activity.defn(name="engagement_export.consume_grant")
async def _consume(given: EngagementExportInput) -> str:
    return "undone" if given.export_id == _EXPORTS["undone"] else "packaging"


@activity.defn(name="engagement_export.snapshot")
async def _snapshot(given: EngagementExportInput) -> int:
    return 48211


@activity.defn(name="engagement_export.package")
async def _package(given: EngagementExportInput) -> ExportPackageFacts:
    if given.export_id == _EXPORTS["integrity-mismatch"]:
        raise ApplicationError("integrity_mismatch", type="integrity_mismatch", non_retryable=True)
    return ExportPackageFacts(
        tenant_id=given.tenant_id,
        export_id=given.export_id,
        bundle_sha256="1" * 64,
        manifest_sha256="2" * 64,
        bytes=18874368,
        file_count=12,
        request_count=24,
        segment_count=1,
        object_prefix=f"exports/{given.tenant_id}/{given.export_id}/",
    )


@activity.defn(name="engagement_export.mark_ready")
async def _ready(given: ExportPackageFacts) -> str:
    return "ready"


@activity.defn(name="engagement_export.mark_failed")
async def _failed(given: ExportBuildFailure) -> str:
    return "failed"


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[EngagementExportWorkflow],
        activities=[_consume, _snapshot, _package, _ready, _failed],
    ):
        for case, export_id in _EXPORTS.items():
            handle = await client.start_workflow(
                EngagementExportWorkflow.run,
                EngagementExportInput(_TENANT, export_id, 1),
                id=f"recorder-engagement-export-{version}-{case}",
                task_queue=_TASK_QUEUE,
            )
            await handle.result()
            scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
            path = out / _NAME.format(v=version, case=case)
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [_NAME.format(v=version, case=case) for case in _EXPORTS]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
