"""P-10-T40 (TASK-6803; SPEC-647 §3.3; DEC-3403): `runtime.conformance` end to end on FakeModel
against the migrated database: one read through C17, then a cited answer; a real firm can't run it.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator

import pytest

from abacus.ai_gateway import FakeModel, configure_provider
from abacus.ai_gateway import providers as p
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import forget_flags
from abacus.modules.agents.conformance import CAPABILITY, run_conformance

from .support import Seeder, World

pytestmark = pytest.mark.asyncio
REF = "runtime.conformance@v1"


@pytest.fixture(autouse=True)
def _reset_provider() -> Iterator[None]:
    yield
    configure_provider(None)


@pytest.fixture(autouse=True)
async def _unblocked(seed: Seeder) -> None:
    await seed.run("DELETE FROM provider_capacity")


async def _run(seed: Seeder, world: World) -> uuid.UUID:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'agent_runtime.v2', 'true', 'p10-t40', 'P-10-T40') ON CONFLICT DO NOTHING",
        world.tenant_id,
    )
    forget_flags()
    run_id = uuid.uuid4()
    client = await seed.value(
        "SELECT client_id FROM engagements WHERE id = $1", world.engagement_id
    )
    await seed.run(
        "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope, state, mode, trigger_kind, run_number, client_scope) "
        "VALUES ($1, $2, $3, 1, $4, $5, ARRAY['engagement.read', 'request_item.read'], 'running', "
        "'run', 'test', 4200, ARRAY[$6::uuid])",
        run_id,
        world.tenant_id,
        CAPABILITY,
        world.engagement_id,
        world.requester.user_id,
        client,
    )
    return run_id


def _script() -> None:
    fake = FakeModel()
    fake.script(
        REF,
        [
            p.ToolCallTurn((("engagements.read", {}),)),
            p.FinalTurn(
                json.dumps(
                    {
                        "blocks": {
                            "version": 1,
                            "parts": [
                                {
                                    "kind": "p",
                                    "segments": [
                                        {"kind": "text", "text": "The engagement is open."}
                                    ],
                                }
                            ],
                        }
                    }
                )
            ),
        ],
    )
    configure_provider(fake)


async def test_ac_it_runs_end_to_end_on_fake_model(seed: Seeder, world: World) -> None:
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", world.tenant_id)
    run_id = await _run(seed, world)
    _script()
    outcome = await run_conformance(world.tenant_id, run_id, "Is this engagement open?")
    assert outcome.status == "completed", outcome.failure
    assert outcome.tool_log == ("engagements.read",)
    assert outcome.turns == 2 and outcome.tool_calls == 1
    called = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'model.called'",
        world.tenant_id,
    )
    assert int(str(called)) >= 2


async def test_ac_a_real_firm_cannot_run_it(seed: Seeder, world: World) -> None:
    run_id = await _run(seed, world)
    _script()
    with pytest.raises(NotFound):
        await run_conformance(world.tenant_id, run_id, "Is this engagement open?")
