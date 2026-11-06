"""Records `LongOcr` and `OcrBackfill` histories with stubbed activities (P-11-T25; ADR-090).

python -m abacus_tools.workflows.record_ocr_long tests/workflows/histories v1
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.evidence.api import BackfillInput, LongOcr, OcrBackfill, UploadInput
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-0000-0000-000000000001"
_VERSION = "00000000-0000-0000-0000-0000000000c1"


@activity.defn(name="upload.ocr")
async def _ocr(given: UploadInput) -> int:
    del given
    return 21


@activity.defn(name="upload.ocr_finished")
async def _finished(given: UploadInput) -> None:
    del given


@activity.defn(name="upload.pending_ocr")
async def _pending(given: BackfillInput) -> list[UploadInput]:
    return [UploadInput(given.tenant_id, "version", _VERSION)]


@activity.defn(name="upload.pii_scan")
async def _scan(given: UploadInput) -> int:
    del given
    return 1


@activity.defn(name="upload.masked_preview")
async def _masked(given: UploadInput) -> str:
    del given
    return "pages"


async def _record(out: Path, version: str, stack: Stack) -> None:
    client: Client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[LongOcr, OcrBackfill],
        activities=[_ocr, _finished, _pending, _scan, _masked],
    ):
        long_scan = await client.start_workflow(
            LongOcr.run,
            UploadInput(_TENANT, "version", _VERSION),
            id="recorder-long-ocr",
            task_queue=_TASK_QUEUE,
        )
        await long_scan.result()
        history = await decoded_and_scrubbed(await long_scan.fetch_history(), payload_codec())
        (out / f"long-ocr-{version}-read.json").write_text(history.to_json())
        backfill = await client.start_workflow(
            OcrBackfill.run,
            BackfillInput(_TENANT),
            id="recorder-ocr-backfill",
            task_queue=_TASK_QUEUE,
        )
        await backfill.result()
        history = await decoded_and_scrubbed(await backfill.fetch_history(), payload_codec())
        (out / f"ocr-backfill-{version}-read.json").write_text(history.to_json())
    print(f"recorded in {out}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    names = [f"long-ocr-{version}-read.json", f"ocr-backfill-{version}-read.json"]
    if refuse_overwrite(out, names):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
