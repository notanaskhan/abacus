"""T-04-T39 (TASK-7410; T-04 §3.8 AC-8.3, AC-8.6; DEC-4409): residency confirmed through SHL-10,
against Postgres.

Row acceptance: "Confirming full-year NY State and NYC resolves the review point (Issues 3 to 2) as
Samuel, the allocation foots to 598,030, 615,605 and 307,900 with credit min(11,279, 15,920) =
11,279, and the agent principal cannot confirm or send." The facts come from cited sources; the
agent proposes the option (its `residency` mode, T-04-T38, proposes through C17); Samuel approves
it in SHL-10 and the applier confirms it as his.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import asyncpg
import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import OutboxEvent, uow
from abacus.modules.agents.api import ProposedRow, create_proposal
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.context import agent_context_for_run
from abacus.modules.tax import residency_service as rs
from abacus.modules.tax.worksheet_review import apply_residency_proposal
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Person, Seeder, World
from .walls_support import Net

pytestmark = pytest.mark.asyncio


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


def _ctx(who: Person) -> AuthContext:
    return AuthContext(
        TenantContext(who.tenant_id, "human", str(who.user_id)),
        who.user_id,
        uuid.uuid4(),
        None,
        datetime.now(UTC) - timedelta(minutes=1),
    )


async def _return(seed: Seeder, world: World, who: Person) -> uuid.UUID:
    client = await seed.value(
        "SELECT client_id FROM engagements WHERE id = $1", world.engagement_id
    )
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, "
            "kind, name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', 'Feld 1040', $5) "
            "RETURNING id",
            world.tenant_id,
            world.engagement_id,
            client,
            world.entity_id,
            who.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, "
        "form, tax_year) VALUES ($1, $2, $3, $4, '1040', 2025)",
        world.tenant_id,
        item,
        world.engagement_id,
        world.entity_id,
    )
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.review_workspace', 'true', 't04-t39', 'T-04-T39') "
        "ON CONFLICT DO NOTHING",
        world.tenant_id,
    )
    forget_flags()
    return item


async def _samuel(seed: Seeder, world: World, item: uuid.UUID) -> Person:
    """Samuel Ito, manager reviewer on the return (`residency.confirm`'s function)."""
    samuel = await seed.person(world.tenant_id)
    await seed.run("UPDATE users SET display_name = 'Samuel Ito' WHERE id = $1", samuel.user_id)
    await seed.member(world.engagement_id, samuel, "manager")
    await seed.run(
        "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
        "function, assigned_by) VALUES ($1, $2, $3, $4, 'manager_reviewer', $4)",
        world.tenant_id,
        item,
        world.engagement_id,
        samuel.user_id,
    )
    return samuel


def _sources(days: int, home: str) -> list[rs.Source]:
    return [
        rs.Source("organizer", uuid.uuid4(), {"nyc_days": days, "main_home": home}),
        rs.Source("coop_statement", uuid.uuid4(), {"place": "New York City"}),
        rs.Source("w2_box20", uuid.uuid4(), {"locality": "NYC"}),
    ]


async def _opened(seed: Seeder, world: World, item: uuid.UUID, who: Person) -> uuid.UUID:
    ctx = _ctx(who)
    async with uow(ctx.tenant) as tx:
        return await rs.open_residency(tx, ctx, item, _sources(281, "New York City"), 2025)


async def _agents_proposal(
    seed: Seeder, world: World, determination: uuid.UUID, option: str
) -> uuid.UUID:
    run_id = uuid.uuid4()
    await seed.run(
        "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope, state, mode, trigger_kind, run_number, runs_as_user_id) "
        "VALUES ($1, $2, 'tax.return_analyst', 2, $3, $4, ARRAY['proposal.create'], 'running', "
        "'run', 'manual', 4301, $4)",
        run_id,
        world.tenant_id,
        world.engagement_id,
        world.requester.user_id,
    )
    agent = await agent_context_for_run(
        tenant_id=world.tenant_id,
        run_id=run_id,
        agent_id="tax.return_analyst",
        engagement_id=world.engagement_id,
        task_scope=frozenset({"proposal.create"}),
        initiator_user_id=world.requester.user_id,
    )
    row = ProposedRow(
        target_type="residency_determination",
        target_id=determination,
        field_key="proposed_option",
        label="proposed option",
        before=None,
        after={"t": "text", "v": option},
        cause="agent_proposal",
    )
    return await create_proposal(
        agent, engagement_id=world.engagement_id, kind="residency", title="Proposed residency",
        rows=[row],
    )  # fmt: skip


async def test_residency_reads_cited_facts_and_codes_recommendation(
    net: Net, seed: Seeder, world: World
) -> None:
    item = await _return(seed, world, world.requester)
    samuel = await _samuel(seed, world, item)
    await _opened(seed, world, item, samuel)
    seen = await net.call("GET", f"/v1/tax/returns/{item}/residency", samuel)
    assert seen.status_code == 200, seen.text
    body = cast(dict[str, object], seen.json())
    assert body["status"] == "review_point" and body["conflict"] is False
    options = cast(list[dict[str, object]], body["options"])
    assert [o["key"] for o in options if o["recommended"]] == ["full_year_nys_nyc"]
    assert "281 NYC days" in cast(list[str], body["facts"])
    assert all(
        cast(list[object], f["citation_ids"])
        for f in cast(list[dict[str, object]], body["fact_rows"])
    )


async def test_samuel_confirms_through_shl10_and_it_is_his(
    net: Net, seed: Seeder, world: World
) -> None:
    item = await _return(seed, world, world.requester)
    samuel = await _samuel(seed, world, item)
    determination = await _opened(seed, world, item, samuel)
    proposal = await _agents_proposal(seed, world, determination, "full_year_nys_nyc")
    headers = {**await net.headers(samuel), "Idempotency-Key": str(uuid.uuid4())}
    approved = await net.http.post(
        f"/v1/proposals/{proposal}/approve", json={"seen_version": 1}, headers=headers
    )
    assert approved.status_code == 200, approved.text
    await apply_residency_proposal(TenantContext(world.tenant_id, "system", "test"), proposal)
    row = await seed.rows(
        "SELECT status, confirmed_by, proposal_id FROM residency_determinations WHERE id = $1",
        determination,
    )
    assert (row[0]["status"], row[0]["confirmed_by"], row[0]["proposal_id"]) == (
        "confirmed",
        samuel.user_id,
        proposal,
    )
    seen = cast(
        dict[str, object],
        (await net.call("GET", f"/v1/tax/returns/{item}/residency", samuel)).json(),
    )
    assert seen["status"] == "confirmed" and seen["confirmed_by_name"] == "Samuel Ito"
    # Delivered twice: nothing changes.
    assert await rs.confirm_approved(
        TenantContext(world.tenant_id, "system", "t"), proposal, samuel.user_id, determination,
        "full_year_nys_nyc",
    ) is False  # fmt: skip


async def test_the_agent_or_a_senior_cannot_confirm(seed: Seeder, world: World) -> None:
    item = await _return(seed, world, world.requester)
    samuel = await _samuel(seed, world, item)
    determination = await _opened(seed, world, item, samuel)
    senior = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, senior, "senior")
    tenant = TenantContext(world.tenant_id, "system", "t")
    for approver in (None, senior.user_id):
        with pytest.raises(rs.ConfirmNotPermitted):
            await rs.confirm_approved(
                tenant, uuid.uuid4(), approver, determination, "full_year_nys_nyc"
            )
    with pytest.raises(asyncpg.CheckViolationError):  # a confirmed row names its proposal
        await seed.run(
            "UPDATE residency_determinations SET status = 'confirmed', confirmed_by = $2, "
            "confirmed_at = now() WHERE id = $1",
            determination,
            samuel.user_id,
        )


async def test_a_part_year_confirmation_activates_it360_and_flags_the_reimport(
    seed: Seeder, world: World
) -> None:
    item = await _return(seed, world, world.requester)
    await seed.run(
        "INSERT INTO return_worksheets (tenant_id, engagement_id, tax_return_id, key, form_code, "
        "title, jurisdiction, default_tsj, origin, active, content_hash) VALUES ($1, $2, $3, "
        "'it360_1', 'it360_1', 'New York IT-360.1', 'NY', 'J', 'human', false, $4)",
        world.tenant_id,
        world.engagement_id,
        item,
        "b" * 64,
    )
    event = OutboxEvent(
        event_id=uuid.uuid4(),
        tenant_id=world.tenant_id,
        event_type="residency_determination.confirmed",
        payload={
            "determination_id": str(uuid.uuid4()),
            "tax_return_id": str(item),
            "engagement_id": str(world.engagement_id),
            "option": "full_year_nys_part_year_nyc",
        },
    )
    await rs.on_residency_confirmed(event)
    assert (
        await seed.value(
            "SELECT active FROM return_worksheets WHERE tax_return_id = $1 AND key = 'it360_1'",
            item,
        )
        is True
    )
    assert "tax_return.engine_reimport_needed" in await seed.actions(world.tenant_id)
