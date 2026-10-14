"""SPEC-033 AC-3, AC-4 (TASK-066): the engagement agent's P-7 starts the matcher on an extracted
inbox file only when the flag, a real model, the autonomy level and code's indecision allow it,
for the engagement partner; a decisive file records nothing (D3)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pytest

from abacus.modules.agents import engagement_agent as agent
from abacus.modules.agents.workflow_types import HandleInput

TENANT, ENGAGEMENT, EVENT, FILE = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


@dataclass
class World:
    paused: str | None = None
    flag: bool = True
    model: bool = True
    level: int = 1
    worth: bool = True
    partner: bool = True
    started: list[uuid.UUID] = field(default_factory=list[uuid.UUID])


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> World:
    made = World()

    async def is_archived(tenant: object, engagement_id: uuid.UUID) -> bool | None:
        return False

    async def paused(tenant: object, engagement_id: uuid.UUID) -> str | None:
        return made.paused

    async def match_on(tenant_id: uuid.UUID) -> bool:
        return made.flag

    async def autonomy_level(tenant_id: uuid.UUID) -> int:
        return made.level

    async def worth(tenant: object, file_id: uuid.UUID) -> bool:
        return made.worth

    async def start(
        tenant: object, engagement: uuid.UUID, file_id: uuid.UUID, src: uuid.UUID
    ) -> bool:
        if made.partner:
            made.started.append(file_id)
        return made.partner

    monkeypatch.setattr(agent, "is_archived", is_archived)
    monkeypatch.setattr(agent, "_paused", paused)
    monkeypatch.setattr(agent, "_match_on", match_on)
    monkeypatch.setattr(agent, "_matcher_available", lambda: made.model)
    monkeypatch.setattr(agent, "autonomy_level", autonomy_level)
    monkeypatch.setattr(agent, "_match_worth", worth)
    monkeypatch.setattr(agent, "_match", start)
    return made


def _extracted() -> HandleInput:
    return HandleInput(
        str(TENANT),
        str(ENGAGEMENT),
        "inbox_file.extracted",
        str(EVENT),
        {"engagement_id": str(ENGAGEMENT), "inbox_file_id": str(FILE)},
    )


async def test_ac3_p7_starts_the_matcher_for_the_file(world: World) -> None:
    [row], end = await agent.apply_policy(_extracted())
    assert (row.policy, row.action, row.outcome, row.record_id) == (
        "P-7",
        "inbox_match.start",
        "done",
        FILE,
    )
    assert world.started == [FILE] and not end


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"paused": "paused"}, "paused"),
        ({"flag": False}, "matching_off"),
        ({"model": False}, "no_real_model"),
        ({"level": 0}, "advise"),
        ({"partner": False}, "no_partner"),
    ],
)
async def test_ac3_p7_skips_with_its_reason(
    world: World, change: dict[str, object], reason: str
) -> None:
    for key, value in change.items():
        setattr(world, key, value)
    [row], _ = await agent.apply_policy(_extracted())
    assert (row.outcome, row.reason) == ("skipped", reason)
    assert world.started == []


async def test_q3_a_file_code_already_decided_records_nothing(world: World) -> None:
    world.worth = False
    assert await agent.apply_policy(_extracted()) == ([], False)
    assert world.started == []
