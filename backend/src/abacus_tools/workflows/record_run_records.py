"""Record the specialist workflows' run-record histories (Q-02-T41, TASK-1287; ADR-169 §3,
ADR-090). See `histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_run_records [output-directory]

Since `run_record_v1`, every specialist workflow persists its run's record
(`agents.persist_run_record`) once the run has ended, before releasing its slot. This records the
real workflows against a throwaway Temporal container only (no database: activities are stubs,
and replay never runs activities), two histories each:
- `<name>-<version>-completed.json`: create, slot, the specialist's activity, persist, release;
- `<name>-<version>-failed.json`: the specialist's activity fails without retry, so `fail_run`
  ends the run, then persist and release.

Versions: screening v3, upload-review v2, inbox-match v2, guidance-draft v3, entry-assess v2.
Refuses to overwrite an existing file.
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker
from testcontainers.core.container import DockerContainer

from abacus.kernel.temporal import data_converter, payload_codec
from abacus.modules.agents.api import (
    EntryAssessInput,
    EntryAssessWorkflow,
    GuidanceDraftInput,
    GuidanceDraftWorkflow,
    InboxMatchWorkflow,
    MatchInput,
    RunInput,
    ScreeningInput,
    ScreeningWorkflow,
    SlotGrant,
    UploadReviewWorkflow,
)
from abacus_tools.quality.schema_check import compose_image
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-0000-0000-000000000001"
_RUN = "00000000-0000-0000-0000-0000000000a1"
_SUBJECT = "00000000-0000-0000-0000-0000000000f1"
_ENGAGEMENT = "00000000-0000-0000-0000-0000000000d1"
_PERSON = "00000000-0000-0000-0000-0000000000b1"
_CASES = ("completed", "failed")
# (history name, version, workflow, its run activity, its input)
_WORKFLOWS: tuple[tuple[str, str, type, str, object], ...] = (
    (
        "screening",
        "v3",
        ScreeningWorkflow,
        "screening.screen",
        ScreeningInput(_TENANT, _SUBJECT, "e1", _PERSON),
    ),
    (
        "upload-review",
        "v2",
        UploadReviewWorkflow,
        "upload_review.review",
        ScreeningInput(_TENANT, _SUBJECT, "e1", _PERSON),
    ),
    (
        "inbox-match",
        "v2",
        InboxMatchWorkflow,
        "inbox_match.match",
        MatchInput(_TENANT, _SUBJECT, "e1", _PERSON),
    ),
    (
        "guidance-draft",
        "v3",
        GuidanceDraftWorkflow,
        "guidance_draft.draft",
        GuidanceDraftInput(_TENANT, _ENGAGEMENT, _SUBJECT, "e1", _PERSON),
    ),
    (
        "entry-assess",
        "v2",
        EntryAssessWorkflow,
        "entry_assess.assess",
        EntryAssessInput(_TENANT, _ENGAGEMENT, _SUBJECT, "e1", _PERSON),
    ),
)
_failing: dict[str, bool] = {"now": False}


def _create(name: str) -> Callable[..., object]:
    @activity.defn(name=name)
    async def create(given: dict[str, Any]) -> str:  # Any: each workflow's own input; unread
        return _RUN

    return create


def _work(name: str) -> Callable[..., object]:
    @activity.defn(name=name)
    async def work(given: dict[str, Any]) -> dict[str, object]:  # Any: unread stub input
        if _failing["now"]:
            raise ApplicationError("ProviderError", type="ProviderError", non_retryable=True)
        return {"status": "completed", "run_id": _RUN}  # the workflow's run outcome, as data

    return work


@activity.defn(name="screening.acquire_slot")
async def _acquire(given: RunInput) -> SlotGrant:
    return SlotGrant(True, 600)


@activity.defn(name="screening.fail_run")
async def _fail(given: dict[str, Any]) -> dict[str, object]:  # Any: unread stub input
    return {"status": "failed", "run_id": _RUN, "failure_code": "provider_unavailable"}


@activity.defn(name="agents.persist_run_record")
async def _persist(given: RunInput) -> None:
    return None


@activity.defn(name="screening.release_slot")
async def _release(given: RunInput) -> None:
    return None


async def _one(client: Client, workflow: str, given: object, wid: str) -> WorkflowHistory:
    handle = await client.start_workflow(
        workflow,
        given,
        id=wid,
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, target: str) -> None:
    client = await Client.connect(target, data_converter=data_converter())
    activities: list[Callable[..., object]] = [_acquire, _fail, _persist, _release]
    for _, _, _, work, _ in _WORKFLOWS:
        activities.append(_work(work))
    for create in sorted({w[3].split(".")[0] + ".create_run" for w in _WORKFLOWS}):
        activities.append(_create(create))
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[w[2] for w in _WORKFLOWS],
        activities=activities,
    ):
        for name, version, _, _, given in _WORKFLOWS:
            for case in _CASES:
                _failing["now"] = case == "failed"
                defined = name.replace("-", "_")  # each workflow's registered name
                history = await _one(client, defined, given, f"recorder-{name}-{case}")
                scrubbed = await decoded_and_scrubbed(history, payload_codec())
                path = out / f"{name}-{version}-{case}.json"
                path.write_text(scrubbed.to_json())
                print(f"recorded {path}")


def _names() -> list[str]:
    return [f"{n}-{v}-{c}.json" for n, v, *_ in _WORKFLOWS for c in _CASES]


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if refuse_overwrite(out, _names()):
        return 1
    temporal = (
        DockerContainer(compose_image("temporal"))
        .with_command("server start-dev --ip 0.0.0.0")
        .with_exposed_ports(7233)
    )
    with temporal:
        for _ in range(90):
            if temporal.exec(["temporal", "operator", "cluster", "health"]).exit_code == 0:
                break
            time.sleep(1)
        target = f"{temporal.get_container_host_ip()}:{temporal.get_exposed_port(7233)}"
        asyncio.run(_record(out, target))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
