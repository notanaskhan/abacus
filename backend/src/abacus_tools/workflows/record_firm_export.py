"""Record the firm export's replay histories (Q-02-T43; compliance-kernel §7; ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_firm_export <output-directory> [version]

Records runs of the real workflow against throwaway containers, with its activities replaced by
stubs (replay never runs activities):
- `firm-export-<version>-ready.json`: the package, then `mark_ready`;
- `firm-export-<version>-failed.json`: the package spends its retries, `mark_failed` records it.
Synthetic identifiers only. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.evidence.api import FirmExportFacts, FirmExportInput, FirmExportWorkflow
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-4000-8000-000000000001"
_EXPORTS = {
    "ready": "00000000-0000-4000-8000-0000000000f1",
    "failed": "00000000-0000-4000-8000-0000000000f2",
}
_NAME = "firm-export-{v}-{case}.json"


@activity.defn(name="firm_export.package")
async def _package(given: FirmExportInput) -> FirmExportFacts:
    if given.export_id == _EXPORTS["failed"]:
        raise ApplicationError("build_error", type="build_error", non_retryable=True)
    return FirmExportFacts(
        tenant_id=given.tenant_id,
        export_id=given.export_id,
        bundle_sha256="3" * 64,
        manifest_sha256="4" * 64,
        bytes=2048,
        segment_count=1,
        object_prefix=f"exports/{given.tenant_id}/firm-{given.export_id}/",
    )


@activity.defn(name="firm_export.mark_ready")
async def _ready(given: FirmExportFacts) -> str:
    return "ready"


@activity.defn(name="firm_export.mark_failed")
async def _failed(given: FirmExportInput) -> str:
    return "failed"


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[FirmExportWorkflow],
        activities=[_package, _ready, _failed],
    ):
        for case, export_id in _EXPORTS.items():
            handle = await client.start_workflow(
                FirmExportWorkflow.run,
                FirmExportInput(_TENANT, export_id),
                id=f"recorder-firm-export-{version}-{case}",
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
