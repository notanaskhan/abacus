"""Record the trust layer backfill's replay history (P-03-T05; ADR-090). See `histories.py` for
the fixture rules.

Run: python -m abacus_tools.workflows.record_trust_layer_backfill <output-directory> [version]
[skipped]

Records one run of the real `TrustLayerBackfill` workflow against throwaway containers, with its
activities replaced by stubs (replay never runs activities): a batch of two uploads, a version
and an inbox file, each given a word layer; the batch isn't full, so the run ends
(`trust-layer-backfill-<version>-done.json`). With `skipped`, the version's step fails for good
and the run passes it and gives the inbox file its layer (`...-skipped.json`). Refuses to
overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.evidence.api import (
    UPLOAD_INBOX,
    UPLOAD_VERSION,
    BackfillInput,
    TrustLayerBackfill,
    UploadInput,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-0000-0000-000000000001"
_VERSION_ID = "00000000-0000-0000-0000-0000000000f1"
_INBOX_ID = "00000000-0000-0000-0000-0000000000f2"


@activity.defn(name="trust_layer.pending_words")
async def _pending_stub(given: BackfillInput) -> list[UploadInput]:
    return [
        UploadInput(_TENANT, UPLOAD_VERSION, _VERSION_ID),
        UploadInput(_TENANT, UPLOAD_INBOX, _INBOX_ID),
    ]


@activity.defn(name="upload.words")
async def _words_stub(given: UploadInput) -> int:
    return 1


@activity.defn(name="upload.words")
async def _words_failing_stub(given: UploadInput) -> int:
    if given.kind == UPLOAD_VERSION:
        raise ApplicationError("IntegrityError", non_retryable=True)
    return 1


def _file_name(version: str, outcome: str = "done") -> str:
    return f"trust-layer-backfill-{version}-{outcome}.json"


async def _record(out: Path, version: str, stack: Stack, outcome: str = "done") -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[TrustLayerBackfill],
        activities=[_pending_stub, _words_failing_stub if outcome == "skipped" else _words_stub],
    ):
        handle = await client.start_workflow(
            TrustLayerBackfill.run,
            BackfillInput(_TENANT),
            id=f"recorder-trust-layer-backfill-{version}-{outcome}",
            task_queue=_TASK_QUEUE,
        )
        await handle.result()
        scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
    path = out / _file_name(version, outcome)
    path.write_text(scrubbed.to_json())
    print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    outcome = argv[2] if len(argv) > 2 else "done"
    if outcome not in ("done", "skipped"):
        print("outcome is done or skipped")
        return 2
    if refuse_overwrite(out, [_file_name(version, outcome)]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack, outcome)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
