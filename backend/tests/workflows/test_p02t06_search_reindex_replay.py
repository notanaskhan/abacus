"""P-02-T06 (ADR-090; DEC-4612): the search reindex replays its recorded histories (offline;
recorded by `abacus_tools.workflows.record_search_reindex` with stubs): every type paged, and a
fan-out's listed ids. A change to the workflow lands behind a `workflow.patched(...)` id."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.platform.search.workflows import SearchReindexWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("search-reindex-v*.json"))


def test_the_histories_are_committed() -> None:
    assert [p.stem for p in ALL] == ["search-reindex-v1-all", "search-reindex-v1-ids"]


@pytest.mark.parametrize("path", ALL, ids=[p.stem for p in ALL])
async def test_the_reindex_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("search_reindex", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[SearchReindexWorkflow]).replay_workflow(history)
