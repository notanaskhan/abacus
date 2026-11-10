"""P-10-T19 (TASK-6203; ADR-234; SPEC-647 AC-G1 to AC-G5; DEC-2803): `ai_gateway.converse()`.

Row acceptance: "Each refusal reason returns without a provider call, every attempt writes one
usage row and one model.called event, and an invalid tool argument never reaches a tool." Against
the migrated test database, on `FakeModel` trajectories (P-10-T12). Expectations come from the row
and ADR-234, not the implementation.
"""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Iterator
from decimal import Decimal
from typing import Literal

import pytest
from pydantic import BaseModel, Field

from abacus.ai_gateway import (
    Attribution,
    BudgetExceeded,
    DataBoundaryRefused,
    DataSubject,
    FakeModel,
    configure_provider,
)
from abacus.ai_gateway import boundary as gateway_boundary
from abacus.ai_gateway import providers as p
from abacus.ai_gateway.converse import ConverseCall, ConverseTool, converse
from abacus.kernel.db import TenantContext

from .support import Seeder, World

pytestmark = pytest.mark.asyncio
REF = "evidence.screen@v0"
AGENT_ID = "evidence.screener"


class ListItemsIn(BaseModel):
    engagement_id: str = Field(min_length=1)
    limit: int = Field(default=20, ge=1, le=200)


class Answer(BaseModel):
    summary: str
    open_items: int = Field(ge=0)


TOOL = ConverseTool(
    spec=p.ToolSpec(
        "requests.list_items",
        "tool.requests.list_items@v1",
        {"type": "object", "properties": {"engagement_id": {"type": "string"}}},
    ),
    input_model=ListItemsIn,
)


class Counting(FakeModel):
    """FakeModel that counts provider calls, so a refusal can be shown to make none."""

    def __init__(self) -> None:
        super().__init__()
        self.conversations = 0

    async def converse(self, request: p.ConverseRequest) -> p.ConverseResponse:
        self.conversations += 1
        return await super().converse(request)


@pytest.fixture(autouse=True)
async def _unblocked(seed: Seeder) -> None:
    await seed.run("DELETE FROM provider_capacity")


@pytest.fixture(autouse=True)
def _reset_provider() -> Iterator[None]:
    yield
    configure_provider(None)


def _install(*turns: p.ToolCallTurn | p.FinalTurn) -> Counting:
    fake = Counting()
    fake.script(REF, list(turns))
    configure_provider(fake)
    return fake


# The run the turns are attributed to: usage rows reference it (S31 end pass).
_RUN: list[uuid.UUID] = []


@pytest.fixture(autouse=True)
async def _agent_run(seed: Seeder, world: World) -> None:
    run = uuid.uuid4()
    await seed.run(
        "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope) VALUES ($1, $2, 'evidence.screener', 1, $3, $4, "
        "ARRAY['evidence.read'])",
        run,
        world.tenant_id,
        world.engagement_id,
        world.requester.user_id,
    )
    _RUN[:] = [run]


def _call(
    world: World,
    *,
    output: type[BaseModel] | None = None,
    budget: str = "1.00",
    subjects: tuple[DataSubject, ...] = (),
    step: uuid.UUID | None = None,
) -> ConverseCall[BaseModel]:
    run = _RUN[0]
    return ConverseCall(
        purpose="P-10-T19 conformance turn",
        prompt=REF,
        tier="small",
        budget_usd=Decimal(budget),
        attribution=Attribution(
            TenantContext(world.tenant_id, "agent", f"agent:{AGENT_ID}:{run}", uuid.uuid4()),
            world.engagement_id,
            AGENT_ID,
            run,
        ),
        work_class="interactive",
        essential=False,
        routes=("direct",),
        messages=(p.ConverseMessage("user", (p.TextBlock("What is still open on Northwind?"),)),),
        tools=(TOOL,),
        output_schema=output,
        data_subjects=subjects,
        step_id=step,
        session_id=None,
    )


async def _rows(seed: Seeder, run: uuid.UUID | None) -> list[tuple[str, uuid.UUID | None]]:
    found = await seed.rows(
        "SELECT outcome, step_id FROM usage_records WHERE agent_run_id = $1 ORDER BY created_at",
        run,
    )
    return [(r["outcome"], r["step_id"]) for r in found]


async def _model_called(seed: Seeder, run: uuid.UUID | None) -> int:
    return int(
        await seed.value(  # type: ignore[arg-type]  # count(*) is an int
            "SELECT count(*) FROM audit_events WHERE action = 'model.called' AND target_id IN "
            "(SELECT id::text FROM usage_records WHERE agent_run_id = $1)",
            run,
        )
    )


async def test_ac_a_valid_tool_call_is_returned_validated_and_recorded_once(
    world: World, seed: Seeder
) -> None:
    good = p.ToolCallTurn((("requests.list_items", {"engagement_id": "nw-py2025"}),))
    fake = _install(good, good, good)  # turns 0 and 1 are the intercepted one's; turn 2 answers
    step = uuid.uuid4()
    c = _call(world, step=step)
    result = await converse(c)
    assert result.status == "tool_use"
    assert [t.name for t in result.tool_calls] == ["requests.list_items"]
    assert isinstance(result.tool_calls[0].arguments, ListItemsIn)
    assert fake.conversations == 1
    rows = await _rows(seed, c.attribution.agent_run_id)
    assert rows == [("ok", step)]
    assert await _model_called(seed, c.attribution.agent_run_id) == 1


async def test_ac_g4_an_invalid_tool_argument_never_reaches_a_tool(
    world: World, seed: Seeder
) -> None:
    bad = p.ToolCallTurn((("requests.list_items", {"engagement_id": ""}),))
    fake = _install(bad, bad)
    c = _call(world)
    result = await converse(c)
    assert result.status == "escalated"
    assert result.tool_calls == ()
    assert result.failure == "tool_arguments_invalid"
    assert result.failure_where == "requests.list_items.engagement_id"
    assert fake.conversations == 2  # one repair, then escalated
    assert [o for o, _ in await _rows(seed, c.attribution.agent_run_id)] == ["invalid", "invalid"]
    assert await _model_called(seed, c.attribution.agent_run_id) == 2


async def test_an_unknown_tool_is_repaired_once_and_a_good_second_turn_passes(
    world: World, seed: Seeder
) -> None:
    # FakeModel's scripts can't name a tool that wasn't offered; a real model can, so the first
    # turn is answered here as a provider would (S31 end pass).
    good = p.ToolCallTurn((("requests.list_items", {"engagement_id": "nw-py2025"}),))
    fake = _install(good, good)  # turn 1 is the intercepted one's; turn 2 answers the repair
    real = fake.converse

    async def hallucinating(request: p.ConverseRequest) -> p.ConverseResponse:
        if fake.conversations == 0:
            fake.conversations += 1
            return p.ConverseResponse(
                (p.ToolUseBlock("toolu_x", "evidence.delete_everything", {}),),
                "tool_use", 10, 5, 0, 0, request.model,
            )  # fmt: skip
        return await real(request)

    fake.converse = hallucinating  # a provider's hallucinated tool
    c = _call(world)
    result = await converse(c)
    assert result.status == "tool_use"
    assert result.attempts == 2
    assert [o for o, _ in await _rows(seed, c.attribution.agent_run_id)] == ["invalid", "repaired"]


async def test_a_structured_final_turn_validates_against_its_schema(
    world: World, seed: Seeder
) -> None:
    _install(p.FinalTurn('{"summary": "3 requests open", "open_items": 3}'))
    c = _call(world, output=Answer)
    result = await converse(c)
    assert result.status == "ok"
    assert result.output == Answer(summary="3 requests open", open_items=3)
    assert len(await _rows(seed, c.attribution.agent_run_id)) == 1


async def test_ac_g2_a_spent_budget_refuses_without_a_provider_call(
    world: World, seed: Seeder
) -> None:
    fake = _install(p.FinalTurn('{"summary": "x", "open_items": 0}'))
    c = _call(world, output=Answer, budget="0.000001")
    with pytest.raises(BudgetExceeded):
        await converse(c)
    assert fake.conversations == 0
    assert [o for o, _ in await _rows(seed, c.attribution.agent_run_id)] == ["budget_refused"]


async def test_ac_g1_tri_without_consent_refuses_before_any_provider_call(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(p.FinalTurn('{"summary": "x", "open_items": 0}'))

    async def declined(*_a: object, **_k: object) -> None:
        raise DataBoundaryRefused("consent_7216")

    monkeypatch.setattr("abacus.ai_gateway.converse.enforce_tri_consent", declined)
    with pytest.raises(DataBoundaryRefused):
        await converse(_call(world, output=Answer, subjects=(DataSubject(uuid.uuid4(), 2025),)))
    assert fake.conversations == 0


async def test_ac_g3_the_ai_pause_refuses_every_turn_without_a_provider_call(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _install(p.FinalTurn('{"summary": "x", "open_items": 0}'))

    async def paused(_name: str, _tenant_id: object = None, **_: object) -> Literal["on"]:
        return "on"

    monkeypatch.setattr(gateway_boundary, "control_state", paused)
    gateway_boundary.clear_cache()
    with pytest.raises(DataBoundaryRefused):
        await converse(_call(world, output=Answer))
    assert fake.conversations == 0


async def test_a_turn_must_end_on_the_users_message(world: World) -> None:
    from abacus.ai_gateway import GatewayRefused

    c = _call(world)
    bad = dataclasses.replace(c, messages=(p.ConverseMessage("assistant", (p.TextBlock("hi"),)),))
    with pytest.raises(GatewayRefused):
        await converse(bad)
