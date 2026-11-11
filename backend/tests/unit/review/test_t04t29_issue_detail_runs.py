"""T-04-T29 (TASK-6822): the issue detail's read side from its runs (SHL-15 a', a'', d).

The detail names the person's sealed instructions, the latest fix run with its state and its
proposal, and every explanation with only the citations it kept (T-04-T31's `issue_runs`).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest

from abacus.modules.identity.api import AuthContext
from abacus.modules.review import contract
from abacus.modules.review.issue_runs import ExplanationRead, FixInstructionsRead, FixRunRead

pytestmark = pytest.mark.asyncio
ISSUE, RUN, PROPOSAL, KEVIN, CITE = (uuid.uuid4() for _ in range(5))
AT = datetime(2026, 9, 14, 14, 51, tzinfo=UTC)
CTX = cast(AuthContext, SimpleNamespace(tenant=None))  # a context double: only `.tenant` is read
RUNS_OUT = contract._issue_runs_out  # pyright: ignore[reportPrivateUsage] -- the builder under test


async def test_the_detail_reads_instructions_run_and_explanations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def facts(_t: object, _i: uuid.UUID) -> object:
        return (
            FixInstructionsRead(
                "Add 1,550 to line 2a and IT-201 line 20", "this_issue", KEVIN, AT
            ),
            FixRunRead(RUN, PROPOSAL),
            [ExplanationRead(uuid.uuid4(), "K-1 box 18A reports 1,550.", RUN, AT, (CITE,))],
        )

    async def state(_t: object, _r: uuid.UUID) -> str:
        return "succeeded"

    async def names(_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        return {KEVIN: "Kevin Osei"}

    async def labels(_ctx: object, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        return dict.fromkeys(ids, "K-1 box 18A")

    monkeypatch.setattr("abacus.modules.review.issue_runs.issue_run_facts", facts)
    monkeypatch.setattr("abacus.modules.review.slots.run_status", state)
    monkeypatch.setattr(contract, "names_of", names)
    monkeypatch.setattr(contract, "_citation_labels", labels)
    instructions, run, explained = await RUNS_OUT(CTX, ISSUE)
    assert instructions is not None and instructions.set_by_name == "Kevin Osei"
    assert run is not None and (run.status, run.proposal_id) == ("succeeded", PROPOSAL)
    assert [c.label for c in explained[0].citations] == ["K-1 box 18A"]
    assert explained[0].pinned is False


async def test_nothing_set_reads_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    async def facts(_t: object, _i: uuid.UUID) -> tuple[None, None, list[ExplanationRead]]:
        return None, None, []

    monkeypatch.setattr("abacus.modules.review.issue_runs.issue_run_facts", facts)
    instructions, run, explained = await RUNS_OUT(CTX, ISSUE)
    assert (instructions, run, explained) == (None, None, [])
