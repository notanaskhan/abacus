"""P-10-T14 (ADR-090): `AgentRunBackfill` replays its recorded histories (offline; recorded by
`abacus_tools.workflows.record_agent_run_backfill` with a stub activity). A change to the workflow
lands behind a `workflow.patched(...)` id, so these v1 histories keep replaying."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.agents.api import AgentRunBackfillWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
BACKFILL = sorted(HISTORIES.glob("agent-run-backfill-v*.json"))


def test_the_histories_are_committed() -> None:
    assert [p.stem for p in BACKFILL] == [
        "agent-run-backfill-v1-completed",
        "agent-run-backfill-v1-resumed",
    ]


@pytest.mark.parametrize("path", BACKFILL, ids=lambda p: p.stem)
async def test_the_backfill_replays(path: Path) -> None:
    history = WorkflowHistory.from_json(f"agent_run_backfill:{path.stem}", path.read_text())
    await Replayer(workflows=[AgentRunBackfillWorkflow]).replay_workflow(history)
