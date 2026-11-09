"""P-09-T07 (TASK-6304; SPEC-648; P-09 §4.3, Story 1.1, Story 8.1; DEC-87, DEC-3004): the run
read model over HTTP.

Row acceptance: "Seeded #4127 at 9:41 returns 1/0/0/0/0 done of 1/5/1/4/3 with 1 blocked and 1
running, a legacy screener run renders as one succeeded tool card, and a walled viewer gets 404."

#4127 is written by the synthetic-only recorder (the service P-09-T12's scenario calls) on a firm
marked synthetic; a real firm is refused. Expectations come from the row and the epic.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.agents.run_recorder import (
    NotSynthetic,
    RecordedItem,
    RecordedRun,
    RecordedStep,
    record_synthetic_run,
)
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Seeder, World
from .walls_support import Net

pytestmark = pytest.mark.asyncio
AT = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)  # 9:24 AM CT


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


def _run_4127(world: World) -> RecordedRun:
    step = RecordedStep
    return RecordedRun(
        agent_id="audit.planning",
        engagement_id=world.engagement_id,
        initiator_user_id=world.requester.user_id,
        run_number=4127,
        state="blocked_on_decision",
        blocked_on={"kind": "decision", "role": "engagement_partner", "needs": []},
        plan_decided_at=AT,
        steps=[
            step("trial_balance", 1, "Trial balance", "succeeded", tool_name="workpapers.tb"),
            # Materiality v1 is proposed and waits on the partner's decision: an approval step.
            step("materiality", 2, "Materiality", "blocked", kind="approval"),
            step("risk_assessment", 2, "Risk assessment", "running"),
            step(
                "general_planning",
                2,
                "General audit planning",
                "waiting_on_inputs",
                needs=("trust_agreement", "irs_opinion_letter"),
            ),
            step("service_organizations", 2, "Service organizations", "queued", reached=False),
            step("planning_analytics", 2, "Planning analytics", "queued", reached=False),
            step("sampling", 3, "Sampling", "queued", reached=False),
            *(step(f"testing_{n}", 4, f"Testing {n}", "queued", reached=False) for n in range(4)),
            *(
                step(f"completion_{n}", 5, f"Completion {n}", "queued", reached=False)
                for n in range(3)
            ),
        ],
        items=[
            RecordedItem("plan", "plan.approved", AT),
            RecordedItem("tool", "workpapers.tb", AT.replace(minute=26), outcome="succeeded"),
            RecordedItem("line", "tb.agreed", AT.replace(minute=26, second=30)),
        ],
        counters={"records_read": 0, "citations_count": 3},
    )


async def _synthetic(seed: Seeder, world: World) -> None:
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", world.tenant_id)


def _initiator(world: World) -> TenantContext:
    return TenantContext(world.tenant_id, "human", str(world.requester.user_id))


async def test_ac_4127_projects_by_level(net: Net, seed: Seeder, world: World) -> None:
    await _synthetic(seed, world)
    run_id = await record_synthetic_run(_initiator(world), _run_4127(world))
    response = await net.call("GET", f"/v1/agent-runs/{run_id}", world.requester)
    assert response.status_code == 200, response.text
    body = cast(dict[str, object], response.json())
    levels = cast(list[dict[str, int]], body["levels"])
    assert [lv["total"] for lv in levels] == [1, 5, 1, 4, 3]
    assert [lv["done"] for lv in levels] == [1, 0, 0, 0, 0]
    assert (levels[1]["blocked"], levels[1]["running"]) == (1, 1)
    header = cast(dict[str, object], body["header"])
    assert header["run_number"] == 4127
    assert cast(dict[str, object], header["blocked_on"])["role"] == "engagement_partner"
    assert "agent_run.read" in cast(list[str], body["allowed_actions"])


async def test_ac_a_v2_run_s_items_poll_in_run_seq_order(
    net: Net, seed: Seeder, world: World
) -> None:
    await _synthetic(seed, world)
    run_id = await record_synthetic_run(_initiator(world), _run_4127(world))
    first = await net.call("GET", f"/v1/agent-runs/{run_id}/items?after_seq=0", world.requester)
    assert first.status_code == 200, first.text
    items = cast(list[dict[str, object]], first.json()["items"])
    assert [i["session_kind"] for i in items] == ["plan", "tool", "line"]
    assert first.json()["next_seq"] == 3
    later = await net.call("GET", f"/v1/agent-runs/{run_id}/items?after_seq=2", world.requester)
    assert [i["seq"] for i in later.json()["items"]] == [3]
    ahead = await net.call("GET", f"/v1/agent-runs/{run_id}/items?after_seq=9", world.requester)
    assert ahead.json()["resync"] is True


async def test_ac_a_legacy_screener_run_is_one_succeeded_tool_card(
    net: Net, seed: Seeder, world: World
) -> None:
    run_id = uuid.uuid4()
    await seed.run(
        "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope, status, finished_at) VALUES ($1, $2, "
        "'evidence.screener', 1, $3, $4, ARRAY['evidence.read'], 'completed', now())",
        run_id,
        world.tenant_id,
        world.engagement_id,
        world.requester.user_id,
    )
    response = await net.call("GET", f"/v1/agent-runs/{run_id}/items", world.requester)
    assert response.status_code == 200, response.text
    cards = [i for i in response.json()["items"] if i["kind"] == "tool_card"]
    assert len(cards) == 1
    assert (cards[0]["outcome"], cards[0]["session_kind"]) == ("succeeded", "tool")
    view = await net.call("GET", f"/v1/agent-runs/{run_id}", world.requester)
    assert view.json()["levels"] == []  # a legacy run has no plan to project


async def test_ac_a_walled_viewer_gets_404(net: Net, seed: Seeder, world: World) -> None:
    await _synthetic(seed, world)
    run_id = await record_synthetic_run(_initiator(world), _run_4127(world))
    admin = await net.person(world.tenant_id, "firm_admin")
    viewer = await net.person(world.tenant_id)
    await seed.member(world.engagement_id, viewer, "manager")
    client_id = cast(
        uuid.UUID,
        await seed.value("SELECT client_id FROM client_entities WHERE id = $1", world.entity_id),
    )
    before = await net.call("GET", f"/v1/agent-runs/{run_id}", viewer)
    assert before.status_code == 200, before.text
    await net.wall(admin, viewer.user_id, client_id)
    for tail in ("", "/items", "/trace"):
        after = await net.call("GET", f"/v1/agent-runs/{run_id}{tail}", viewer)
        assert after.status_code == 404, (tail, after.text)
    listed = await net.call("GET", f"/v1/engagements/{world.engagement_id}/agent-runs", viewer)
    assert listed.status_code == 404


async def test_the_engagement_list_s_active_runs_include_a_blocked_v2_run(
    net: Net, seed: Seeder, world: World
) -> None:
    await _synthetic(seed, world)
    run_id = await record_synthetic_run(_initiator(world), _run_4127(world))
    response = await net.call(
        "GET", f"/v1/engagements/{world.engagement_id}/agent-runs?state=active", world.requester
    )
    assert response.status_code == 200, response.text
    assert str(run_id) in [r["id"] for r in response.json()]


async def test_the_recorder_refuses_a_real_firm(world: World) -> None:
    with pytest.raises(NotSynthetic):
        await record_synthetic_run(_initiator(world), _run_4127(world))
