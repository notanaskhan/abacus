"""Record `NoticeResponseWorkflow`'s replay history (N-04-T16; ADR-090). See `histories.py`.

Run: python -m abacus_tools.workflows.record_notice_response <output-directory> [version]

Records the real workflow with stubs: dates in the past so every timer fires at once, the
`sent` and
`agency_reply` signals, and the follow-up: `notice-response-<version>-replied.json`. Refuses to
overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.notices.api import (
    AlertInput,
    FollowUpInput,
    NoticeResponseInput,
    NoticeResponseWorkflow,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-0000-0000-000000000001"
_ITEM = "00000000-0000-0000-0000-0000000000e1"


@activity.defn(name="notice_response.alert")
async def _alert(given: AlertInput) -> None:
    return None


@activity.defn(name="notice_response.follow_up")
async def _follow_up(given: FollowUpInput) -> None:
    return None


async def _run(client: Client) -> WorkflowHistory:
    handle = await client.start_workflow(
        NoticeResponseWorkflow.run,
        NoticeResponseInput(_TENANT, _ITEM, "2000-01-08", "cp2000"),
        id="recorder-notice-response",
        task_queue=_TASK_QUEUE,
    )
    await handle.signal("sent", "2000-03-01")
    await handle.signal("agency_reply")
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[NoticeResponseWorkflow],
        activities=[_alert, _follow_up],
    ):
        scrubbed = await decoded_and_scrubbed(await _run(client), payload_codec())
    path = out / f"notice-response-{version}-replied.json"
    path.write_text(scrubbed.to_json())
    print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [f"notice-response-{version}-replied.json"]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
