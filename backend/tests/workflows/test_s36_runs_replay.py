"""S36 (ADR-090): `ApprovedWriteWorkflow` (P-10-T38), `FixRunWorkflow` and `IssueExplainWorkflow`
(T-04-T31) replay their recorded histories (offline; recorded by
`abacus_tools.workflows.record_s36_runs` with stubbed activities)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.agents.approved_write_workflow import ApprovedWriteWorkflow
from abacus.modules.tax.explain import IssueExplainWorkflow
from abacus.modules.tax.fix_runner import FixRunWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
NAMES = [
    "approved-write-v1-saved.json",
    "fix-run-v1-proposed.json",
    "fix-run-v1-consent-waited.json",
    "issue-explain-v1-explained.json",
]


@pytest.mark.parametrize("name", NAMES)
def test_the_history_is_committed(name: str) -> None:
    assert (HISTORIES / name).exists()


@pytest.mark.parametrize("name", NAMES)
async def test_the_s36_workflows_replay(name: str) -> None:
    history = WorkflowHistory.from_json(f"s36:{name}", (HISTORIES / name).read_text())
    workflows = [ApprovedWriteWorkflow, FixRunWorkflow, IssueExplainWorkflow]
    await Replayer(workflows=workflows).replay_workflow(history)
