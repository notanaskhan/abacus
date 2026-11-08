"""A-05-T54 (ADR-090): `Form5500TieOut` replays its recorded history (offline; recorded by
`abacus_tools.workflows.record_form5500_tieout` with a stub activity)."""

from __future__ import annotations

from pathlib import Path

from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.assurance.form5500_workflow import Form5500TieOutWorkflow

HISTORY = Path(__file__).resolve().parent / "histories" / "form5500-tieout-v1-tied.json"


def test_the_history_is_committed() -> None:
    assert HISTORY.exists()


async def test_the_tieout_replays() -> None:
    history = WorkflowHistory.from_json("form5500_tieout:v1", HISTORY.read_text())
    await Replayer(workflows=[Form5500TieOutWorkflow]).replay_workflow(history)
