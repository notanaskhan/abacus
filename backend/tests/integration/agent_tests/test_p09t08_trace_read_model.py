"""P-09-T08 (TASK-6305; SPEC-648; P-09 §4.3, Stories 4.1 to 4.2; DEC-87, DEC-3005): the v2 trace
over HTTP, on run #4127 written by the synthetic-only recorder.

Row: "Trace read model: summary, timeline, step detail with samples, records read, writes;
content and metadata projections; region and training from the register; TRI masking."
"""

from __future__ import annotations

import uuid
from typing import cast

import httpx
import pytest

from abacus.modules.agents.run_recorder import record_synthetic_run
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Seeder, World
from .test_p09t07_run_read_model import (  # shared seed
    _initiator,  # pyright: ignore[reportPrivateUsage] -- the shared seed
    _run_4127,  # pyright: ignore[reportPrivateUsage] -- the shared seed
    _synthetic,  # pyright: ignore[reportPrivateUsage] -- the shared seed
)
from .walls_support import Net

pytestmark = pytest.mark.asyncio
Json = dict[str, object]


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


async def _recorded(seed: Seeder, world: World) -> uuid.UUID:
    await _synthetic(seed, world)
    return await record_synthetic_run(_initiator(world), _run_4127(world))


async def test_the_4127_trace_reads_its_plan_and_steps(
    net: Net, seed: Seeder, world: World
) -> None:
    run_id = await _recorded(seed, world)
    response = await net.call("GET", f"/v1/agent-runs/{run_id}/trace", world.requester)
    assert response.status_code == 200, response.text
    body = cast(Json, response.json())
    rows = cast(list[Json], body["rows"])
    assert [r["kind"] for r in rows] == ["plan", "step", "step", "step", "step"]
    assert [r["mark"] for r in rows] == ["plan", "done", "blocked", "running", "waiting"]
    assert str(rows[1]["title"]).endswith("Trial balance")
    assert rows[2]["detail"] == "engagement_partner"
    summary = cast(Json, body["summary"])
    assert summary["run_number"] == 4127 and summary["citations"] == 3
    assert body["region"] == "United States (data and inference)"
    assert body["runtime"] == "Accrued Agent runtime"


async def test_a_metadata_reader_sees_kinds_not_labels(
    net: Net, seed: Seeder, world: World
) -> None:
    run_id = await _recorded(seed, world)
    security = await net.person(world.tenant_id, "security_admin")
    response = await net.call("GET", f"/v1/agent-runs/{run_id}/trace", security)
    assert response.status_code == 200, response.text
    body = cast(Json, response.json())
    assert body["access"] == "metadata"
    rows = cast(list[Json], body["rows"])
    assert [r["title"] for r in rows[1:]] == ["Execute", "Propose", "Execute", "Execute"]
    assert all(r["detail"] is None for r in rows)
    assert body["model_text"] is None


async def test_the_step_detail_answers_404_while_the_flag_is_off(
    net: Net, seed: Seeder, world: World
) -> None:
    run_id = await _recorded(seed, world)
    step_id = await seed.value(
        "SELECT id FROM agent_run_steps WHERE run_id = $1 AND seq = 1", run_id
    )
    response = await net.call(
        "GET", f"/v1/agent-runs/{run_id}/trace/steps/{step_id}", world.requester
    )
    assert response.status_code == 404


async def test_records_read_and_writes_answer_for_a_v2_run(
    net: Net, seed: Seeder, world: World
) -> None:
    run_id = await _recorded(seed, world)
    read = await net.call("GET", f"/v1/agent-runs/{run_id}/trace/records-read", world.requester)
    assert read.status_code == 200 and read.json() == []  # the recorded steps read nothing
    writes = await net.call("GET", f"/v1/agent-runs/{run_id}/trace/writes", world.requester)
    assert writes.status_code == 200 and writes.json() == []
