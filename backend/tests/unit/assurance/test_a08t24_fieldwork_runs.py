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
    from abacus.modules.agents import section_draft

    started: list[object] = []

    async def refused(*args: object) -> tuple[uuid.UUID, None]:
        raise agents.DraftingNotEnabled

    async def dispatched(*args: object, **kwargs: object) -> None:
        started.append(args[0])

    monkeypatch.setattr(section_draft, "_record", refused)
    monkeypatch.setattr(section_draft, "dispatch", dispatched)
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


@pytest.mark.asyncio
async def test_a_fan_out_records_every_run_then_starts_them_eight_at_a_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-08-T24 rest (A-08 §5): every run is recorded first, then one fan-out workflow starts the
    new ones at most 8 in flight; a replayed key starts nothing more."""
    from abacus.modules.agents import section_draft
    from abacus.modules.agents.workflow_types import SectionDraftChild, SectionDraftInput

    tenant = uuid.uuid4()
    made: dict[str, uuid.UUID] = {}
    started: list[tuple[object, object]] = []

    async def record(
        ctx: object, engagement: object, paper: object, mode: str, section: str, key: str
    ) -> tuple[uuid.UUID, SectionDraftChild | None]:
        if key in made:
            return made[key], None
        made[key] = uuid.uuid4()
        child = SectionDraftChild(
            SectionDraftInput(str(tenant), str(made[key]), str(paper), mode, section),
            f"section_draft:{made[key]}",
        )
        return made[key], child

    async def dispatched(workflow: object, given: object, **kwargs: object) -> None:
        started.append((workflow, given))

    class _Ctx:
        tenant_id = tenant

    monkeypatch.setattr(section_draft, "_record", record)
    monkeypatch.setattr(section_draft, "dispatch", dispatched)
    sections = [f"item:{n}" for n in range(1, 13)]
    first = await section_draft.start_many(
        _Ctx(),  # type: ignore[arg-type] -- only the tenant id is read
        uuid.uuid4(),
        uuid.uuid4(),
        "fieldwork_attribute",
        sections,
        "begin",
    )
    assert len(first) == 12
    assert len(started) == 1
    workflow, given = started[0]
    assert workflow is section_draft.SectionDraftFanOutWorkflow
    assert isinstance(given, section_draft.SectionDraftFanOutInput)
    assert given.max_parallel == 8
    assert [c.input.section_key for c in given.children] == sections
    again = await section_draft.start_many(
        _Ctx(),  # type: ignore[arg-type] -- only the tenant id is read
        uuid.uuid4(),
        uuid.uuid4(),
        "fieldwork_attribute",
        sections,
        "begin",
    )
    assert again == first
    assert len(started) == 1
