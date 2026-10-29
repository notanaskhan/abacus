"""R-01-T27 (DEC-954; ADR-090): the sender domain verification replays its recorded v1 history
(offline; recorded by `abacus_tools.workflows.record_sending_domain` with a stub activity). A
change to the workflow lands behind a `workflow.patched(...)` id, so this history keeps
replaying."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.communications.api import SendingDomainVerificationWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
RECORDED = sorted(HISTORIES.glob("sending-domain-v*.json"))


def test_the_history_is_committed() -> None:
    assert [p.stem for p in RECORDED] == ["sending-domain-v1-verified"]


@pytest.mark.parametrize("path", RECORDED, ids=[p.stem for p in RECORDED])
async def test_the_verification_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json(
        "recorder-sending-domain-v1", path.read_text(encoding="utf-8")
    )
    await Replayer(workflows=[SendingDomainVerificationWorkflow]).replay_workflow(history)
