"""Record `JeScoringWorkflow`'s replay histories (A-08-T12; ADR-090). See `histories.py`.

Run: python -m abacus_tools.workflows.record_je_scoring <output-directory>

`je-scoring-v1-scored.json`: the scoring activity returns `scored`.
`je-scoring-v1-failed.json`: the scoring activity fails both attempts; the fail activity marks the
test `failed`. Both activities are stubbed. A history on disk is never overwritten.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.sampling.api import JeScoringInput, JeScoringWorkflow
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

_TASK_QUEUE = "abacus-recorder"
TENANT = "00000000-0000-4000-8000-0000000000b1"
USER = "00000000-0000-4000-8000-0000000000a1"
SCORED = ("je-scoring-v1-scored.json", "00000000-0000-4000-8000-0000000018a1")
FAILED = ("je-scoring-v1-failed.json", "00000000-0000-4000-8000-0000000018a2")


@activity.defn(name="je_scoring.run")
async def _run(given: JeScoringInput) -> str:
    if given.je_test_id == FAILED[1]:
        raise ApplicationError("population_changed", non_retryable=True)
    return "scored"


@activity.defn(name="je_scoring.fail")
async def _fail(given: JeScoringInput) -> None:
    return None


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client, task_queue=_TASK_QUEUE, workflows=[JeScoringWorkflow], activities=[_run, _fail]
    ):
        for name, test_id in (SCORED, FAILED):
            if (out / name).exists():
                continue
            handle = await client.start_workflow(
                JeScoringWorkflow.run,
                JeScoringInput(TENANT, test_id, 1, USER),
                id=f"je_scoring:{TENANT}:{test_id}",
                task_queue=_TASK_QUEUE,
            )
            await handle.result()
            scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
            (out / name).write_text(scrubbed.to_json())
            print(f"recorded {out / name}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if all((out / name).exists() for name, _ in (SCORED, FAILED)):
        print("the JE scoring histories are recorded; nothing to do")
        return 0

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
