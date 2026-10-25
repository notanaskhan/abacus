"""TASK-1207 re-check, item 8 (DEC-52): the screener never reads a raw sheet for an offshore
member.

The screener reads a retrieved trial balance's raw sheet and sends its account names to the
model. Masked material has no sheets, so for an offshore initiator there is nothing it may send:
no run is started for them, and a run whose initiator has since turned offshore ends before any
model call. The control is the same requester onshore. A retrieved trial balance comes from the
real retrieval pipeline; the model is the recording fake.
"""

from __future__ import annotations

import uuid

import pytest

from abacus.ai_gateway import FakeModel, ModelRequest, ModelResponse, configure_provider
from abacus.kernel.errors import NotFound
from abacus.modules.agents.api import (
    create_screening_run,
    install_fake_responses,
    load_agent_context,
    screen,
)

from .support import Seeder, World, retrieve


class Recorder:
    def __init__(self) -> None:
        self.inner = FakeModel()
        install_fake_responses(self.inner)
        self.requests: list[ModelRequest] = []

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return await self.inner.complete(request)


@pytest.fixture
def model(fake_model: FakeModel) -> Recorder:
    recorder = Recorder()
    configure_provider(recorder)  # `fake_model` resets the provider on teardown
    return recorder


async def _offshore(seed: Seeder, world: World) -> None:
    await seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        world.tenant_id,
        world.requester.user_id,
    )


async def _runs(seed: Seeder, world: World) -> int:
    return int(
        str(
            await seed.value(
                "SELECT count(*) FROM agent_runs WHERE tenant_id = $1 AND agent_id = "
                "'evidence.screener'",
                world.tenant_id,
            )
        )
    )


async def test_review8_no_screening_run_starts_for_an_offshore_requester(
    seed: Seeder, world: World
) -> None:
    result = await retrieve(world)
    await _offshore(seed, world)
    started = await create_screening_run(
        world.tenant_id, result.evidence_version_id, uuid.uuid4(), world.requester.user_id
    )
    assert started is None
    assert await _runs(seed, world) == 0


async def test_review8_a_run_for_a_requester_now_offshore_ends_before_the_model(
    seed: Seeder, world: World, model: Recorder
) -> None:
    result = await retrieve(world)
    run_id = await create_screening_run(
        world.tenant_id, result.evidence_version_id, uuid.uuid4(), world.requester.user_id
    )
    assert run_id is not None  # the control: onshore, the run starts
    await _offshore(seed, world)
    agent = await load_agent_context(world.tenant_id, run_id)
    with pytest.raises(NotFound):
        await screen(agent)
    assert model.requests == []  # nothing of the sheet reached the model
    status = await seed.value("SELECT status FROM agent_runs WHERE id = $1", run_id)
    assert status == "failed"
    assert (
        await seed.value(
            "SELECT count(*) FROM screening_results WHERE tenant_id = $1", world.tenant_id
        )
        == 0
    )
