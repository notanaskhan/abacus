"""A-07-T42 (ADR-090): `SealVerifyWorkflow` and `SealVerifySweepWorkflow` replay their recorded
histories (offline; recorded by `abacus_tools.workflows.record_seal_verify` with stub activities,
the S35 end pass)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.assurance.api import SealVerifySweepWorkflow, SealVerifyWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
CASES = (
    ("seal-verify-v1-matched.json", SealVerifyWorkflow),
    ("seal-verify-sweep-v1-swept.json", SealVerifySweepWorkflow),
)


@pytest.mark.parametrize(("name", "found"), CASES, ids=[c[0] for c in CASES])
def test_the_history_is_committed(name: str, found: type) -> None:
    assert (HISTORIES / name).exists()


@pytest.mark.parametrize(("name", "found"), CASES, ids=[c[0] for c in CASES])
async def test_the_seal_verification_replays(name: str, found: type) -> None:
    history = WorkflowHistory.from_json(name, (HISTORIES / name).read_text())
    await Replayer(workflows=[found]).replay_workflow(history)
