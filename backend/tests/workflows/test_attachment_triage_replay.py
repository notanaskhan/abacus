"""N-01-T12 (ADR-090): `AttachmentTriage` replays its recorded histories (offline; recorded by
`abacus_tools.workflows.record_attachment_triage` with stub activities): every step succeeds and
the attachment waits; the word layer fails and the steps after it still run."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.communications.api import AttachmentTriageWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("attachment-triage-v*.json"))
IDS = [p.stem for p in ALL]


def test_the_histories_are_committed() -> None:
    assert IDS == ["attachment-triage-v1-step-failed", "attachment-triage-v1-waiting"]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("test-attachment-triage", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[AttachmentTriageWorkflow]).replay_workflow(history)
