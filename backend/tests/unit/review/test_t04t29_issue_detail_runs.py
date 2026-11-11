"""T-04-T29 (TASK-6822): the issue detail's read side from its runs (SHL-15 a', a'', d).

The detail names the person's sealed instructions, the latest fix run with its state and its
proposal, and every explanation with only the citations it kept (T-04-T31's `issue_runs`).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from abacus.modules.review import contract
from abacus.modules.review.issue_runs import ExplanationRead, FixInstructionsRead, FixRunRead

pytestmark = pytest.mark.asyncio
ISSUE, RUN, PROPOSAL, KEVIN, CITE = (uuid.uuid4() for _ in range(5))
AT = datetime(2026, 9, 14, 14, 51, tzinfo=UTC)


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
    monkeypatch.setattr("abacus.modules.agents.api.run_v2_status", state)
    monkeypatch.setattr(contract, "names_of", names)
    monkeypatch.setattr(contract, "_citation_labels", labels)
    ctx = object()
    instructions, run, explained = await contract._issue_runs_out(ctx, ISSUE)  # type: ignore[arg-type]  # pyright: ignore[reportPrivateUsage] -- the builder under test
    assert instructions is not None and instructions.set_by_name == "Kevin Osei"
    assert run is not None and (run.status, run.proposal_id) == ("succeeded", PROPOSAL)
    assert [c.label for c in explained[0].citations] == ["K-1 box 18A"]
    assert explained[0].pinned is False


async def test_nothing_set_reads_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    async def facts(_t: object, _i: uuid.UUID) -> object:
        return None, None, []

    monkeypatch.setattr("abacus.modules.review.issue_runs.issue_run_facts", facts)
    out = await contract._issue_runs_out(object(), ISSUE)  # type: ignore[arg-type]  # pyright: ignore[reportPrivateUsage] -- the builder under test
    assert out == (None, None, [])
