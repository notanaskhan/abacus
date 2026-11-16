"""C-01-T19 (ADR-090): `RequestPublishWorkflow` replays its recorded history (offline; recorded by
`abacus_tools.workflows.record_request_publish` with stub activities: a wait, a `recompute` signal,
then the publish)."""

from __future__ import annotations

from pathlib import Path

from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.closes.api import RequestPublishWorkflow

HISTORY = Path(__file__).resolve().parent / "histories" / "request-publish-v1-recompute.json"


def test_the_history_is_committed() -> None:
    assert HISTORY.exists()


async def test_the_request_publish_replays() -> None:
    history = WorkflowHistory.from_json("close_requests:v1", HISTORY.read_text())
    await Replayer(workflows=[RequestPublishWorkflow]).replay_workflow(history)
