"""A-06-T25: the relay's events start the statements workflows, under the ids A-06 §4.5 names, and
a repeated tie-out on a version runs again."""

from __future__ import annotations

import uuid

import pytest

from abacus.kernel.uow import OutboxEvent
from abacus.modules.reporting import statements_jobs
from abacus.modules.reporting.statements_workflow_types import FsDraftInput, TieOutInput
from abacus.modules.reporting.statements_workflows import FsDraftWorkflow, TieOutWorkflow

TENANT = uuid.UUID(int=1)


@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch) -> list[tuple[object, object, str]]:
    calls: list[tuple[object, object, str]] = []

    async def dispatch(workflow: object, given: object, *, id: str, **_: object) -> None:
        calls.append((workflow, given, id))

    monkeypatch.setattr(statements_jobs, "dispatch", dispatch)
    return calls


async def test_ac_a_draft_request_starts_its_workflow_once_per_run(
    started: list[tuple[object, object, str]],
) -> None:
    run, engagement, item = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await statements_jobs.on_draft_requested(
        OutboxEvent(
            uuid.uuid4(),
            TENANT,
            "statement.draft_requested",
            {"run_id": str(run), "engagement_id": str(engagement), "work_item_id": str(item)},
        )
    )
    assert started == [
        (
            FsDraftWorkflow,
            FsDraftInput(str(TENANT), str(run), str(engagement), str(item)),
            f"fs_draft:{TENANT}:{run}",
        )
    ]


async def test_ac_two_tie_outs_on_a_version_are_two_workflows(
    started: list[tuple[object, object, str]],
) -> None:
    version = uuid.uuid4()
    for _ in range(2):
        await statements_jobs.on_tie_out_requested(
            OutboxEvent(
                uuid.uuid4(),
                TENANT,
                "statement.tie_out_requested",
                {"statement_version_id": str(version)},
            )
        )
    assert [c[0] for c in started] == [TieOutWorkflow, TieOutWorkflow]
    assert started[0][1] == TieOutInput(str(TENANT), str(version))
    assert started[0][2] != started[1][2]
