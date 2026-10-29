# ac-test-author: ayushkbhatia
"""P-04-T39 (TASK-2024; P-04 §3; INV-1 to INV-5): the review grammar end to end, over HTTP, on a
Northwind-shaped and a Feld-shaped target registered as pytest fixtures.

Acceptance (the task row): "The test runs in make check and fails on any agent-actor decision
row or any Accrued Agent approver attribution."

The walk: the agent proposes the Feld K-1 treatment (cited) and Samuel approves it; Ana opens an
issue on the Northwind target and Samuel resolves it; the agent proposes a checkpoint on the
return and Samuel approves it. Then, over everything the walk wrote:
- INV-1 the agent never decides: no row of any decision table has a non-human actor, and every
  decision audit names a person;
- INV-2 citations verified: an uncited row blocks approval (422 `uncited_change`);
- INV-3 walls hold: Lena, walled from the Feld client, gets 404 for its proposal;
- INV-4 portal scopes isolated: a client principal reaches no review route;
- INV-5 attribution correct: every approver reads as the person ("Samuel Ito"), never
  "Accrued Agent".
"""

from __future__ import annotations

import uuid
from typing import Any, Final

import pytest
from backfill import test_p04t28_proposals_independent as t28
from backfill import test_p04t32_checkpoints as t32
from backfill.p04t28_support import (
    PROBE,
    World,
    agent,
    cite,
    make_world,
    own,
    probe,
    second_site,
)
from backfill.support import Net, Site

from abacus.modules.agents.api import create_proposal

pytestmark = pytest.mark.asyncio
Body = dict[str, Any]  # a response body as the contract shapes it
DECISION_TABLES: Final = (
    "sign_offs",
    "decisions",
    "proposal_decisions",
    "suggestion_decisions",
    "checkpoint_decisions",
    "review_note_events",
    "issue_events",
)
DECISION_AUDITS: Final = (
    "proposal.approved",
    "proposal.rejected",
    "checkpoint.approved",
    "checkpoint.rejected",
    "checkpoint.restored",
    "issue.resolved",
)
row_ = t28._row  # pyright: ignore[reportPrivateUsage]
return_ = t32._return  # pyright: ignore[reportPrivateUsage]
propose_ = t32._propose  # pyright: ignore[reportPrivateUsage]
change_ = t32._change  # pyright: ignore[reportPrivateUsage]
decide_ = t32._decide  # pyright: ignore[reportPrivateUsage]


@pytest.fixture
async def northwind(net: Net) -> World:
    """The Northwind-shaped world: the 401(k) plan's engagement and the whole cast."""
    return await make_world(net, "Northwind Robotics 401(k) Plan")


@pytest.fixture
async def feld(northwind: World) -> Site:
    """The Feld-shaped target's client, in the same firm, Lena walled from it."""
    site = await second_site(northwind, "Jonah & Claire Feld")
    await northwind.net.wall(northwind.admin, northwind["lena"], site)
    return site


async def _feld_k1(world: World, site: Site, *, uncited: bool = False) -> uuid.UUID:
    c1, c2 = await cite(world, site=site), await cite(world, site=site)
    target = own(site)
    rows = [
        row_(target, "activity.ridgeline", "1", (c1, c2)),
        row_(target, "sch_e.p2.28a_h", "307900", (c1,)),
    ]
    if uncited:
        rows.append(row_(target, "sch_a.l5b", "18240", ()))
    return await create_proposal(
        await agent(world, site=site),
        engagement_id=site.engagement_id,
        kind="field_change_set",
        title="K-1 treatment: Ridgeline",
        rows=rows,
        reasoning_ref="reasoning",
    )


async def _decision_actors(world: World) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for table in DECISION_TABLES:
        has = await world.seed.value(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = $1 AND column_name = 'actor_kind'",
            table,
        )
        if not has:
            continue
        rows = await world.seed.rows(
            f"SELECT DISTINCT actor_kind FROM {table} WHERE tenant_id = $1",  # noqa: S608 -- fixed names
            world.tenant_id,
        )
        out[table] = {str(r["actor_kind"]) for r in rows}
    return out


async def test_the_review_grammar_journey_keeps_inv_1_to_inv_5(
    northwind: World, feld: Site
) -> None:
    world = northwind

    # INV-2: an uncited row blocks approval.
    blocked = await _feld_k1(world, feld, uncited=True)
    refused = await world.call(
        "POST", f"/v1/proposals/{blocked}/approve", "samuel", {"seen_version": 1}
    )
    assert refused.status_code == 422 and refused.json()["detail"] == "uncited_change"

    # The agent proposes the Feld K-1; Samuel approves (a person decides).
    proposal = await _feld_k1(world, feld)
    approved = await world.call(
        "POST", f"/v1/proposals/{proposal}/approve", "samuel", {"seen_version": 1, "edits": []}
    )
    assert approved.status_code == 200, approved.text
    decision: Body = approved.json()["decision"]
    assert decision["decided_by_name"] == "Samuel Ito"  # INV-5

    # INV-3: walled Lena cannot see the Feld proposal.
    walled = await world.call("GET", f"/v1/proposals/{proposal}", "lena")
    assert walled.status_code == 404

    # Ana opens an issue on the Northwind target; Samuel resolves it.
    target = probe(world.site, (world["samuel"],))
    made = await world.call(
        "POST",
        "/v1/issues",
        "ana",
        {
            "record_type": PROBE,
            "record_id": str(target),
            "kind": "waiting_on_client",
            "title": "Census hire dates still differ from payroll",
        },
    )
    assert made.status_code == 201, made.text
    issue = made.json()["issue"]
    resolved = await world.call(
        "POST", f"/v1/issues/{issue['id']}/resolve", "samuel", {"seen_version": issue["version"]}
    )
    assert resolved.status_code == 200, resolved.text

    # The agent proposes a checkpoint on the return; Samuel approves it.
    ret = await return_(world)
    checkpoint, seen = await propose_(
        world, ret, change_(t32.INT, "100.00", "125.00", "25.00"), tag="p04t39"
    )
    await decide_(world, checkpoint, seen)

    # INV-4: a client principal reaches no review route.
    client = await world.seed.client_contact(world.site)
    for path in (
        f"/v1/proposals/{proposal}",
        "/v1/checkpoints?target_type=x&target_id=" + str(ret),
    ):
        assert (await world.call("GET", path, client)).status_code in (403, 404)

    # INV-1: no decision row has a non-human actor.
    for table, actors in (await _decision_actors(world)).items():
        assert actors <= {"human"}, f"{table} holds {actors}"
    audits = await world.seed.rows(
        "SELECT action, actor_kind, actor_id FROM audit_events "
        "WHERE tenant_id = $1 AND action = ANY($2)",
        world.tenant_id,
        list(DECISION_AUDITS),
    )
    assert audits, "the walk recorded no decision audit"
    for row in audits:
        assert row["actor_kind"] == "human", row["action"]

    # INV-5: no approver anywhere reads as the agent.
    names = await world.seed.rows(
        "SELECT display_name FROM users WHERE id = ANY($1)",
        [uuid.UUID(str(a["actor_id"])) for a in audits if a["actor_id"]],
    )
    assert names and all(n["display_name"] != "Accrued Agent" for n in names)
