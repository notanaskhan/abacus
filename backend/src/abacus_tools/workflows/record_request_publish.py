"""Record `RequestPublishWorkflow`'s replay history (C-01-T19; ADR-090). See `histories.py`.

Run: python -m abacus_tools.workflows.record_request_publish <output-directory>

`request-publish-v1-recompute.json`: one close's run with both activities stubbed. The first ask
waits an hour; a `recompute` signal wakes it, the second ask says publish now, and the publish
creates three requests. A history on disk is never overwritten.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from temporalio import activity
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.closes.api import (
    PUBLISH_REQUESTS,
    RECOMPUTE_REQUESTS,
    REQUESTS_SECONDS_UNTIL,
    PublishInput,
    PublishResult,
    RequestPublishWorkflow,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

_TASK_QUEUE = "abacus-recorder"
NAME = "request-publish-v1-recompute.json"
TENANT = "00000000-0000-4000-8000-0000000000b1"
CLOSE = "00000000-0000-4000-8000-0000000019c1"
_ASKED: list[int] = []


@activity.defn(name=REQUESTS_SECONDS_UNTIL)
async def _seconds_until(given: PublishInput) -> int:
    _ASKED.append(1)
    return 3600 if len(_ASKED) == 1 else 0


@activity.defn(name=PUBLISH_REQUESTS)
async def _publish(given: PublishInput) -> PublishResult:
    return PublishResult(3, 1)


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[RequestPublishWorkflow],
        activities=[_seconds_until, _publish],
    ):
        handle = await client.start_workflow(
            RequestPublishWorkflow.run,
            PublishInput(TENANT, CLOSE),
            id=f"close_requests:{TENANT}:{CLOSE}",
            task_queue=_TASK_QUEUE,
        )
        while not _ASKED:  # the first ask has run: the timer is set
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.5)
        await handle.signal(RECOMPUTE_REQUESTS)
        await handle.result()
        scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
        (out / NAME).write_text(scrubbed.to_json())
        print(f"recorded {out / NAME}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if (out / NAME).exists():
        print("the request publish history is recorded; nothing to do")
        return 0

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
