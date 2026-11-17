"""A-08-T24 (TASK-8403; SPEC-657 F9): the run rows' fixed words and the DF-04 refusal: a firm
whose data boundary is closed gets 409 `drafting_not_enabled` before any run is recorded."""

from __future__ import annotations

import uuid

import pytest

from abacus.modules.assurance import fieldwork_runs as runs


def test_the_analytics_run_rows_read_as_the_handoff() -> None:
    assert runs.LABELS["tie_out"] == (
        "Compare the trial balance to the ledger and source documents, and show what doesn't tie"
    )
    assert runs.LABELS["client_questions"] == "Prepare client questions for unexplained movements"
    assert runs.ANALYTICS_PAPER == ("AN-1", "Analytics")


@pytest.mark.asyncio
async def test_attribution_names_the_initiator(monkeypatch: pytest.MonkeyPatch) -> None:
    user = uuid.uuid4()

    async def names(ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        return {user: "Simone Baptiste"}

    monkeypatch.setattr(runs, "names_of", names)
    assert await runs._initiator(user) == "Simone Baptiste via Agent"  # pyright: ignore[reportPrivateUsage] -- the private helper under test


@pytest.mark.asyncio
async def test_df04_refuses_before_any_run(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.modules.agents import api as agents

    started: list[str] = []

    async def refused(*args: object) -> uuid.UUID:
        raise agents.DraftingNotEnabled

    monkeypatch.setattr(agents, "start_section_draft", refused)
    with pytest.raises(agents.DraftingNotEnabled) as caught:
        await runs._fan_out(  # pyright: ignore[reportPrivateUsage] -- the private helper under test
            object(),  # type: ignore[arg-type] -- unused by the refusing start
            uuid.uuid4(),
            uuid.uuid4(),
            "flux_explain",
            ["line:3", "line:5"],
            "key",
        )
    assert caught.value.code == "drafting_not_enabled"
    assert started == []
