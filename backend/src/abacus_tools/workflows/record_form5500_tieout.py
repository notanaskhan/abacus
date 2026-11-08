"""Record `Form5500TieOut`'s replay history (A-05-T54; ADR-090). See `histories.py` for the rules.

Run: python -m abacus_tools.workflows.record_form5500_tieout <output-directory>

`form5500-tieout-v1-tied.json`: one tie-out over Northwind's draft with the activity stubbed (11
lines tied, one inconsistent until Note 8 documents it, no Part IV inconsistency).
A history on disk is never overwritten.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.assurance.form5500_workflow import (
    TIEOUT_ID_PREFIX,
    Form5500TieOutWorkflow,
    TieOutCounts,
    TieOutInput,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

_TASK_QUEUE = "abacus-recorder"
NAME = "form5500-tieout-v1-tied.json"


@activity.defn(name="ebp.form5500_tieout")
async def _tie(tenant_id: str, draft_id: str) -> TieOutCounts:
    return TieOutCounts(ties=11, reconciling=0, inconsistent=1, part_iv_inconsistent=0)


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client, task_queue=_TASK_QUEUE, workflows=[Form5500TieOutWorkflow], activities=[_tie]
    ):
        draft = "00000000-0000-4000-8000-000000000507"
        handle = await client.start_workflow(
            Form5500TieOutWorkflow.run,
            TieOutInput("00000000-0000-4000-8000-0000000000b1", draft),
            id=f"{TIEOUT_ID_PREFIX}{draft}",
            task_queue=_TASK_QUEUE,
        )
        await handle.result()
        scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
        (out / NAME).write_text(scrubbed.to_json())
        print(f"recorded {out / NAME}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if (out / NAME).exists():
        print("the form5500-tieout history is recorded; nothing to do")
        return 0

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
