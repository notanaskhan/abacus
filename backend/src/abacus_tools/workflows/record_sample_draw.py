"""Record the sample draw workflow's replay histories (A-03-T10; A-03 §4.4; ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_sample_draw <output-directory> [version]

Records the real `SampleDrawWorkflow` against throwaway containers with its activities replaced
by stubs (replay never runs activities):
- `sample-draw-<version>-drafted.json`: the draw persists its items and the version is a draft;
- `sample-draw-<version>-failed.json`: the draw fails after its retries and is marked failed.
Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.sampling.api import SampleDrawInput, SampleDrawWorkflow
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-0000-0000-000000000001"
_GOOD = "00000000-0000-0000-0000-0000000000a1"
_BAD = "00000000-0000-0000-0000-0000000000a2"
_PERSON = "00000000-0000-0000-0000-0000000000b1"
_NAMES = ("drafted", "failed")


@activity.defn(name="sample_draw.run")
async def _run_draw(given: SampleDrawInput) -> str:
    if given.version_id == _BAD:
        raise ApplicationError("DrawRefused", type="DrawRefused", non_retryable=True)
    return "draft"


@activity.defn(name="sample_draw.fail")
async def _fail(given: SampleDrawInput) -> None:
    return None


async def _run(client: Client, name: str, version_id: str) -> WorkflowHistory:
    handle = await client.start_workflow(
        SampleDrawWorkflow.run,
        SampleDrawInput(_TENANT, version_id, _PERSON),
        id=f"recorder-sample-draw-{name}",
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[SampleDrawWorkflow],
        activities=[_run_draw, _fail],
    ):
        for name, version_id in (("drafted", _GOOD), ("failed", _BAD)):
            scrubbed = await decoded_and_scrubbed(
                await _run(client, name, version_id), payload_codec()
            )
            path = out / f"sample-draw-{version}-{name}.json"
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [f"sample-draw-{version}-{n}.json" for n in _NAMES]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
