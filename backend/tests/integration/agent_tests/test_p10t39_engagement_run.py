"""P-10-T39 (TASK-6804; SPEC-647 §3.6 AC-E1 to AC-E4; DEC-3404): the engagement run over HTTP.

The workflow is not started here (`dispatch` is captured): the start writes the run's row with its
code plan, which is what AUD-02b and SHL-13 state 1 project.
"""

from __future__ import annotations

import json
import uuid
from typing import cast

import httpx
import pytest

from abacus.kernel.flags import forget_flags
from abacus.modules.agents import engagement_run
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Person, Seeder, World
from .walls_support import Net

pytestmark = pytest.mark.asyncio


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


@pytest.fixture(autouse=True)
def dispatched(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    started: list[str] = []

    async def capture(_workflow: object, _input: object, *, id: str, **_: object) -> None:
        started.append(id)

    monkeypatch.setattr(engagement_run, "dispatch", capture)
    return started


async def _on(seed: Seeder, world: World) -> None:
    for flag in ("agent_runtime.v2", "engagement_run.enabled"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'p10-t39', 'P-10-T39') ON CONFLICT DO NOTHING",
            world.tenant_id,
            flag,
        )
    forget_flags()


async def _senior(seed: Seeder, world: World) -> Person:
    marcus = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, marcus, "senior")
    return marcus


async def _manager(seed: Seeder, world: World) -> Person:
    hannah = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, hannah, "manager")
    return hannah


async def test_ac_e1_the_run_projects_14_over_5_levels(
    net: Net, seed: Seeder, world: World, dispatched: list[str]
) -> None:
    await _on(seed, world)
    marcus = await _senior(seed, world)
    response = await net.call(
        "POST", f"/v1/engagements/{world.engagement_id}/runs", marcus, body={}
    )
    assert response.status_code == 202, response.text
    run_id = uuid.UUID(cast(dict[str, str], response.json())["run_id"])
    inputs = await seed.value("SELECT inputs FROM agent_runs WHERE id = $1", run_id)
    plan = cast(dict[str, list[dict[str, object]]], json.loads(str(inputs)))["plan"]
    levels = [sum(1 for s in plan if s["level"] == n) for n in range(1, 6)]
    assert levels == [1, 5, 1, 4, 3]
    assert len(dispatched) == 1 and str(run_id) in dispatched[0]
    row = await seed.rows(
        "SELECT agent_id, trigger_kind, state, mode FROM agent_runs WHERE id = $1", run_id
    )
    assert tuple(row[0]) == ("engagements.run", "engagement_plan", "queued", "run")


async def test_ac_e2_an_unregistered_step_kind_answers_409(
    net: Net, seed: Seeder, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _on(seed, world)
    monkeypatch.setattr(engagement_run, "_HANDLERS", {})
    marcus = await _senior(seed, world)
    response = await net.call(
        "POST", f"/v1/engagements/{world.engagement_id}/runs", marcus, body={}
    )
    assert response.status_code == 409, response.text
    assert "run_step_unavailable" in response.text


async def test_ac_e3_auto_mode_cannot_be_on_for_a_real_firm(
    net: Net, seed: Seeder, world: World
) -> None:
    await _on(seed, world)
    hannah = await _manager(seed, world)
    response = await net.call(
        "PUT",
        f"/v1/engagements/{world.engagement_id}/auto-mode",
        hannah,
        body={"enabled": True, "confirmed": True},
    )
    assert response.status_code == 409, response.text
    assert "auto_mode_not_available" in response.text


async def test_ac_e3_a_synthetic_firm_may_turn_it_on(net: Net, seed: Seeder, world: World) -> None:
    await _on(seed, world)
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", world.tenant_id)
    hannah = await _manager(seed, world)
    response = await net.call(
        "PUT",
        f"/v1/engagements/{world.engagement_id}/auto-mode",
        hannah,
        body={"enabled": True, "confirmed": True},
    )
    assert response.status_code == 200, response.text
    assert cast(dict[str, object], response.json())["enabled"] is True


async def test_ac_e4_a_person_off_the_team_cannot_start_it(
    net: Net, seed: Seeder, world: World
) -> None:
    await _on(seed, world)
    outsider = await seed.person(world.tenant_id)
    response = await net.call(
        "POST", f"/v1/engagements/{world.engagement_id}/runs", outsider, body={}
    )
    assert response.status_code in (403, 404), response.text
