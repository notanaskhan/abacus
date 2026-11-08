"""Record `BringDown`'s replay history (A-07-T23; ADR-090). See `histories.py` for the rules.

Run: python -m abacus_tools.workflows.record_bring_down <output-directory>

`bring-down-v1-fired.json`: one bring-down whose 09:00 instant has passed, with the activity
stubbed (four procedures, all performed through the report date; five reconfirmations asked).
A history on disk is never overwritten.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.assurance.bring_down import (
    BRING_DOWN_ID_PREFIX,
    BringDownInput,
    BringDownResult,
    BringDownWorkflow,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

_TASK_QUEUE = "abacus-recorder"
NAME = "bring-down-v1-fired.json"


@activity.defn(name="assurance.bring_down")
async def _bring_down(
    tenant_id: str, work_item_id: str, engagement_id: str, report_date: str
) -> BringDownResult:
    return BringDownResult(report_date, 4, 4, 5)


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client, task_queue=_TASK_QUEUE, workflows=[BringDownWorkflow], activities=[_bring_down]
    ):
        work_item = "00000000-0000-4000-8000-0000000004a1"
        handle = await client.start_workflow(
            BringDownWorkflow.run,
            BringDownInput(
                "00000000-0000-4000-8000-0000000000b1",
                work_item,
                "00000000-0000-4000-8000-0000000004e1",
                "2026-10-09",
                "2026-10-09T14:00:00+00:00",
            ),
            id=f"{BRING_DOWN_ID_PREFIX}{work_item}",
            task_queue=_TASK_QUEUE,
        )
        await handle.result()
        scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
        (out / NAME).write_text(scrubbed.to_json())
        print(f"recorded {out / NAME}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if (out / NAME).exists():
        print("the bring-down history is recorded; nothing to do")
        return 0

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
