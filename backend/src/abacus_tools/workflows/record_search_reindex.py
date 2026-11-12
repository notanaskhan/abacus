"""Record the search reindex's replay histories (P-02-T06; ADR-090). See `histories.py` for the
fixture rules.

Run: python -m abacus_tools.workflows.record_search_reindex <output-directory>

Records the real `SearchReindexWorkflow` against throwaway containers with its activities replaced
by stubs (replay never runs activities):
- `search-reindex-v1-all.json`: every registered type paged (two types, one with two pages);
- `search-reindex-v1-ids.json`: a fan-out's listed ids for one type.
Synthetic identifiers only. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.platform.search.workflows import (
    ReindexInput,
    ReindexPage,
    SearchReindexWorkflow,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-4000-8000-0000000005e1"
_FILES = ("search-reindex-v1-all.json", "search-reindex-v1-ids.json")
_IDS = [f"00000000-0000-4000-8000-0000000005{n:02x}" for n in range(2, 6)]


@activity.defn(name="platform.search_reindex_types")
async def _types(request: ReindexInput) -> list[str]:
    return ["client", "tax_return"]


@activity.defn(name="platform.search_list_ids")
async def _list_ids(request: ReindexInput, object_type: str, cursor: str | None) -> ReindexPage:
    if object_type == "client" and cursor is None:
        return ReindexPage(object_type, _IDS[:2], _IDS[1])
    return ReindexPage(object_type, _IDS[2:] if object_type == "client" else _IDS[:1], None)


@activity.defn(name="platform.search_index_batch")
async def _index(tenant_id: str, object_type: str, ids: list[str]) -> int:
    return len(ids)


@activity.defn(name="platform.search_reindex_completed")
async def _completed(request: ReindexInput, indexed: int) -> None:
    return None


async def _run(client: Client, request: ReindexInput, suffix: str) -> WorkflowHistory:
    handle = await client.start_workflow(
        SearchReindexWorkflow.run,
        request,
        id=f"search_reindex:{_TENANT}:{suffix}",
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[SearchReindexWorkflow],
        activities=[_types, _list_ids, _index, _completed],
    ):
        runs = (
            (ReindexInput(_TENANT), _FILES[0], "all"),
            (ReindexInput(_TENANT, "tax_return", None, _IDS), _FILES[1], "ids"),
        )
        for request, name, suffix in runs:
            history = await _run(client, request, suffix)
            scrubbed = await decoded_and_scrubbed(history, payload_codec())
            path = out / name
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if refuse_overwrite(out, list(_FILES)):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
