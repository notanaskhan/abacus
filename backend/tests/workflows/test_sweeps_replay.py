"""Q-03-T195 (ADR-090): the client import and four scheduled sweeps replay their recorded histories
(offline; recorded by `abacus_tools.workflows.record_sweeps` with stub activities): the import
applied and failed, the import-file erase, connection health, evidence integrity, pilot metrics."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.connections.workflows import ConnectionHealthWorkflow
from abacus.modules.engagements.workflows import ClientImportEraseWorkflow, ClientImportWorkflow
from abacus.modules.platform.workflows import PilotMetricsWorkflow
from abacus.modules.signatures.workflows import EvidenceIntegrityWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
PREFIXES = ("client-import", "connection-health", "evidence-integrity", "pilot-metrics")
ALL = sorted({p for prefix in PREFIXES for p in HISTORIES.glob(f"{prefix}-*v*.json")})
IDS = [p.stem for p in ALL]
WORKFLOWS = [
    ClientImportWorkflow,
    ClientImportEraseWorkflow,
    ConnectionHealthWorkflow,
    EvidenceIntegrityWorkflow,
    PilotMetricsWorkflow,
]


def test_the_histories_are_committed() -> None:
    assert IDS == [
        "client-import-erase-v1-erased",
        "client-import-v1-applied",
        "client-import-v1-failed",
        "connection-health-v1-checked",
        "evidence-integrity-v1-swept",
        "pilot-metrics-v1-snapshotted",
    ]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json(f"test-{path.stem}", path.read_text(encoding="utf-8"))
    await Replayer(workflows=WORKFLOWS).replay_workflow(history)
