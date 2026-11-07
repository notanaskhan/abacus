"""Record the replay histories of four small workflows (Q-03-T195; ADR-090). See `histories.py`
for the fixture rules.

Run: python -m abacus_tools.workflows.record_simple_jobs <output-directory> [version]

Each runs for real against throwaway containers with its activities replaced by stubs (replay never
runs activities):
- `tax-calendar-sweep-<v>-sent.json`: the due-soon sweep sends 3 reminders;
- `reference-set-fan-out-<v>-announced.json`: a publication announced to 2 firms, 1 newly;
- `notice-analysis-<v>-ready.json` and `-failed.json`: the run answers, or fails and is marked;
- `knowledge-embedding-<v>-done.json` and `-waited.json`: embedded at once, or waits once first.
Synthetic identifiers only. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.agents.knowledge_workflow import KnowledgeEmbeddingWorkflow
from abacus.modules.agents.workflow_types import BatchOutcome, FailKnowledgeInput, KnowledgeInput
from abacus.modules.notices.api import NoticeAnalysisInput, NoticeAnalysisWorkflow
from abacus.modules.platform.api import FanOutInput, ReferenceSetFanOutWorkflow
from abacus.modules.tax.schedule_workflows import TaxCalendarSweepWorkflow
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE: Final = "abacus-recorder"
_TENANT: Final = "00000000-0000-4000-8000-000000000001"
_OTHER: Final = "00000000-0000-4000-8000-000000000002"
_NOTICE_OK: Final = "00000000-0000-4000-8000-0000000000e1"
_NOTICE_BAD: Final = "00000000-0000-4000-8000-0000000000e2"
_DOC_NOW: Final = "00000000-0000-4000-8000-0000000000f1"
_DOC_WAIT: Final = "00000000-0000-4000-8000-0000000000f2"
_NAMES: Final = (
    "tax-calendar-sweep-{v}-sent",
    "reference-set-fan-out-{v}-announced",
    "notice-analysis-{v}-ready",
    "notice-analysis-{v}-failed",
    "knowledge-embedding-{v}-done",
    "knowledge-embedding-{v}-waited",
)
_asked: dict[str, int] = {}


@activity.defn(name="tax_estimates.send_due_soon")
async def _send_due_soon() -> int:
    return 3


@activity.defn(name="platform.reference_set_announce")
async def _announce(tenant_id: str, request: FanOutInput) -> bool:
    del request
    return tenant_id == _TENANT


@activity.defn(name="notice_analysis.run")
async def _analyse(given: NoticeAnalysisInput) -> str:
    if given.notice_id == _NOTICE_BAD:
        raise ApplicationError("synthetic failure", non_retryable=True)
    return "ready"


@activity.defn(name="notice_analysis.mark_failed")
async def _mark_failed(given: NoticeAnalysisInput) -> str:
    del given
    return "failed"


@activity.defn(name="knowledge.embed_batch")
async def _embed(given: KnowledgeInput) -> BatchOutcome:
    _asked[given.document_id] = _asked.get(given.document_id, 0) + 1
    if given.document_id == _DOC_WAIT and _asked[given.document_id] == 1:
        return BatchOutcome(done=False, wait_seconds=1)
    return BatchOutcome(done=True)


@activity.defn(name="knowledge.fail")
async def _fail(given: FailKnowledgeInput) -> None:
    del given


async def _histories(client: Client) -> list[tuple[str, WorkflowHistory]]:
    """Each run, in `_NAMES` order, by its typed `run` method."""
    out: list[tuple[str, WorkflowHistory]] = []
    sweep = await client.start_workflow(
        TaxCalendarSweepWorkflow.run, id="rec-tax-sweep", task_queue=_TASK_QUEUE
    )
    await sweep.result()
    out.append((_NAMES[0], await sweep.fetch_history()))
    fanout = await client.start_workflow(
        ReferenceSetFanOutWorkflow.run,
        FanOutInput(
            "rec-version", "published", "us-legal-holidays", "op", "ap", [_TENANT, _OTHER]
        ),
        id="rec-fanout",
        task_queue=_TASK_QUEUE,
    )
    await fanout.result()
    out.append((_NAMES[1], await fanout.fetch_history()))
    for name, notice in ((_NAMES[2], _NOTICE_OK), (_NAMES[3], _NOTICE_BAD)):
        analysis = await client.start_workflow(
            NoticeAnalysisWorkflow.run,
            NoticeAnalysisInput(_TENANT, notice, 1),
            id=f"rec-analysis-{notice[-2:]}",
            task_queue=_TASK_QUEUE,
        )
        await analysis.result()
        out.append((name, await analysis.fetch_history()))
    for name, document in ((_NAMES[4], _DOC_NOW), (_NAMES[5], _DOC_WAIT)):
        embedding = await client.start_workflow(
            KnowledgeEmbeddingWorkflow.run,
            KnowledgeInput(_TENANT, document),
            id=f"rec-embed-{document[-2:]}",
            task_queue=_TASK_QUEUE,
        )
        await embedding.result()
        out.append((name, await embedding.fetch_history()))
    return out


async def _record_all(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[
            TaxCalendarSweepWorkflow,
            ReferenceSetFanOutWorkflow,
            NoticeAnalysisWorkflow,
            KnowledgeEmbeddingWorkflow,
        ],
        activities=[_send_due_soon, _announce, _analyse, _mark_failed, _embed, _fail],
    ):
        for name, history in await _histories(client):
            scrubbed = await decoded_and_scrubbed(history, payload_codec())
            path = out / f"{name.format(v=version)}.json"
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [f"{n.format(v=version)}.json" for n in _NAMES]):
        return 1

    async def record(stack: Stack) -> None:
        await _record_all(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
