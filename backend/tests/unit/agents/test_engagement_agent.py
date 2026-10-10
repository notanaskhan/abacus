"""SPEC-027 (TASK-050): the engagement agent's policies, as a decision table. Each reads fresh
and checks, in order: paused (firm, then engagement), archived, the flag, then its own rule."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from abacus.modules.agents import engagement_agent as agent
from abacus.modules.agents.models import AgentActivity
from abacus.modules.agents.workflow_types import HandleInput

TENANT, ENGAGEMENT, EVENT = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
VERSION, PERSON, ITEM, FILE = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


@dataclass
class World:
    archived: bool | None = False
    paused: str | None = None
    on: bool = True
    level: int = 1
    retrieval: str = "done"
    skipped: list[AgentActivity] = field(default_factory=list[AgentActivity])
    screened: list[tuple[uuid.UUID, uuid.UUID, uuid.UUID | None]] = field(
        default_factory=list[tuple[uuid.UUID, uuid.UUID, uuid.UUID | None]]
    )
    retrieved: list[uuid.UUID | None] = field(default_factory=list[uuid.UUID | None])


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> World:
    made = World()

    async def is_archived(tenant: object, engagement_id: uuid.UUID) -> bool | None:
        return made.archived

    async def paused(tenant: object, engagement_id: uuid.UUID) -> str | None:
        return made.paused

    async def agent_on(tenant_id: uuid.UUID) -> bool:
        return made.on

    async def autonomy_level(tenant_id: uuid.UUID) -> int:
        return made.level

    async def screen(
        tenant: object, version: uuid.UUID, source: uuid.UUID, who: uuid.UUID | None
    ) -> None:
        made.screened.append((version, source, who))

    async def retrieve(
        tenant_id: uuid.UUID, engagement_id: uuid.UUID, only: uuid.UUID | None
    ) -> str:
        made.retrieved.append(only)
        return made.retrieval

    async def skipped(tenant: object, engagement_id: uuid.UUID) -> list[AgentActivity]:
        return made.skipped

    monkeypatch.setattr(agent, "is_archived", is_archived)
    monkeypatch.setattr(agent, "_paused", paused)
    monkeypatch.setattr(agent, "agent_on", agent_on)
    monkeypatch.setattr(agent, "autonomy_level", autonomy_level)
    monkeypatch.setattr(agent, "_screen", screen)
    monkeypatch.setattr(agent, "run_auto_retrieval", retrieve)
    monkeypatch.setattr(agent, "_skipped_screenings", skipped)
    return made


def _event(kind: str, **payload: str) -> HandleInput:
    return HandleInput(str(TENANT), str(ENGAGEMENT), kind, str(EVENT), payload)


def _evidence() -> HandleInput:
    return _event(
        "evidence_version.created", evidence_version_id=str(VERSION), requested_by=str(PERSON)
    )


async def test_ac1_an_engagement_created_starts_its_agent(world: World) -> None:
    rows, end = await agent.apply_policy(_event("engagement.created"))
    assert [(r.policy, r.action, r.outcome) for r in rows] == [("P-0", "agent.started", "done")]
    assert not end


@pytest.mark.parametrize("archived", [True, None])
async def test_ac1_an_archived_or_missing_engagement_ends_the_agent(
    world: World, archived: bool | None
) -> None:
    world.archived = archived
    assert await agent.apply_policy(_evidence()) == ([], True)
    assert world.screened == []


async def test_ac2_p1_screens_new_evidence_with_its_initiator(world: World) -> None:
    [row], _ = await agent.apply_policy(_evidence())
    assert (row.policy, row.outcome, row.record_id, row.for_user) == (
        "P-1",
        "done",
        VERSION,
        PERSON,
    )
    assert world.screened == [(VERSION, EVENT, PERSON)]


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"paused": "paused"}, "paused"),
        ({"paused": "firm_paused"}, "firm_paused"),
        ({"on": False}, "agent_off"),
        ({"level": 0}, "advise"),
    ],
)
async def test_ac2_p1_skips_with_its_reason(
    world: World, change: dict[str, object], reason: str
) -> None:
    for key, value in change.items():
        setattr(world, key, value)
    [row], _ = await agent.apply_policy(_evidence())
    assert (row.outcome, row.reason) == ("skipped", reason)
    assert row.for_user == PERSON  # kept, so a resume can screen it for the same person
    assert world.screened == []


@pytest.mark.parametrize(
    ("found", "outcome", "reason"),
    [
        ("done", "done", None),
        ("not_open", "skipped", "not_open"),
        ("flag_off", "skipped", "auto_retrieval_off"),
        ("no_connection", "skipped", "no_connection"),
        ("advise", "skipped", "advise"),
    ],
)
async def test_p2_retrieval_records_why(
    world: World, found: str, outcome: str, reason: str | None
) -> None:
    world.retrieval = found
    [row], _ = await agent.apply_policy(
        _event("request_item.classified", request_item_id=str(ITEM))
    )
    assert (row.policy, row.outcome, row.reason, row.record_id) == ("P-2", outcome, reason, ITEM)
    assert world.retrieved == [ITEM]


async def test_ac5_p2_never_runs_while_paused(world: World) -> None:
    world.paused = "paused"
    [row], _ = await agent.apply_policy(_event("connection.created", connection_id=str(ITEM)))
    assert (row.outcome, row.reason) == ("skipped", "paused")
    assert world.retrieved == []


async def test_p3_records_the_suggestion_count_and_never_assigns(world: World) -> None:
    [row], _ = await agent.apply_policy(
        _event("inbox_file.added", inbox_file_id=str(FILE), suggestions="3")
    )
    assert (row.policy, row.action, row.outcome, row.item_count, row.record_id) == (
        "P-3",
        "match.suggested",
        "done",
        3,
        FILE,
    )


def _skipped_row(version: uuid.UUID, source: uuid.UUID) -> AgentActivity:
    return AgentActivity(
        tenant_id=TENANT,
        engagement_id=ENGAGEMENT,
        policy="P-1",
        policy_version=1,
        action="screening.start",
        outcome="skipped",
        reason="paused",
        record_type="evidence_version",
        record_id=version,
        for_user=PERSON,
        source_event_id=source,
        created_at=datetime.now(UTC),
    )


async def test_ac6_resume_screens_what_arrived_while_paused_once_and_retrieves_once(
    world: World,
) -> None:
    first, second = uuid.uuid4(), uuid.uuid4()
    world.skipped = [_skipped_row(VERSION, first), _skipped_row(ITEM, second)]
    rows, _ = await agent.apply_policy(_event(agent.RESUMED))
    assert [(r.policy, r.action) for r in rows] == [
        ("P-0", "agent.resume_checked"),
        ("P-1", "screening.replayed"),
        ("P-2", "retrieval.start"),
    ]
    assert rows[1].item_count == 2
    # The original event as the screening's source: a screening already run isn't repeated.
    assert world.screened == [(VERSION, first, PERSON), (ITEM, second, PERSON)]
    assert world.retrieved == [None]


async def test_ac6_a_resume_while_still_paused_does_nothing(world: World) -> None:
    world.paused = "firm_paused"
    world.skipped = [_skipped_row(VERSION, uuid.uuid4())]
    [row], _ = await agent.apply_policy(_event(agent.FIRM_RESUMED))
    assert (row.outcome, row.reason) == ("skipped", "firm_paused")
    assert world.screened == [] and world.retrieved == []


async def test_ac6_resume_at_advise_screens_nothing(world: World) -> None:
    world.level = 0
    world.skipped = [_skipped_row(VERSION, uuid.uuid4())]
    rows, _ = await agent.apply_policy(_event(agent.RESUMED))
    assert [r.policy for r in rows] == ["P-0", "P-2"]
    assert world.screened == []


async def test_an_unknown_event_records_nothing(world: World) -> None:
    assert await agent.apply_policy(_event("budget.anomaly")) == ([], False)
