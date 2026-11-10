"""Q-03-T195 (ADR-090): four small workflows replay their recorded histories (offline; recorded by
`abacus_tools.workflows.record_simple_jobs` with stub activities): the tax due-soon sweep, the
reference-set fan-out, the notice analysis (answered and failed) and knowledge embedding (at once,
and after one wait)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.agents.knowledge_workflow import KnowledgeEmbeddingWorkflow
from abacus.modules.notices.api import NoticeAnalysisWorkflow
from abacus.modules.platform.api import ReferenceSetFanOutWorkflow
from abacus.modules.tax.schedule_workflows import TaxCalendarSweepWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
PREFIXES = (
    "tax-calendar-sweep",
    "reference-set-fan-out",
    "notice-analysis",
    "knowledge-embedding",
)
ALL = sorted(p for prefix in PREFIXES for p in HISTORIES.glob(f"{prefix}-v*.json"))
IDS = [p.stem for p in ALL]
WORKFLOWS = [
    TaxCalendarSweepWorkflow,
    ReferenceSetFanOutWorkflow,
    NoticeAnalysisWorkflow,
    KnowledgeEmbeddingWorkflow,
]


def test_the_histories_are_committed() -> None:
    assert IDS == [
        "knowledge-embedding-v1-done",
        "knowledge-embedding-v1-waited",
        "notice-analysis-v1-failed",
        "notice-analysis-v1-ready",
        "reference-set-fan-out-v1-announced",
        "tax-calendar-sweep-v1-sent",
    ]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json(f"test-{path.stem}", path.read_text(encoding="utf-8"))
    await Replayer(workflows=WORKFLOWS).replay_workflow(history)
