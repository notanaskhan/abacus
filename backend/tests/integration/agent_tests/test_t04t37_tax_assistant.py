"""T-04-T37 (TASK-7317; T-04 §6; TAX-08; DF-04; DEC-4316): the return's assistant sessions.

An unconsented taxpayer gets the agents-off state (409 `capability_unavailable`, reason
`consent_7216`) with no session and no model call (no usage row)."""

from __future__ import annotations

import uuid
from typing import cast

import httpx
import pytest

from abacus.kernel.flags import forget_flags
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Person, Seeder, World
from .walls_support import Net

pytestmark = pytest.mark.asyncio


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


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
    for flag in ("tax.review_workspace", "agent_runtime.v2"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 't04-t37', 'T-04-T37') ON CONFLICT DO NOTHING",
            world.tenant_id,
            flag,
        )
    forget_flags()
    return item


async def test_an_unconsented_taxpayer_gets_the_agents_off_state_with_no_model_call(
    net: Net, seed: Seeder, world: World
) -> None:
    samuel = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, samuel, "manager")
    item = await _return(seed, world, samuel)
    usage = await seed.value("SELECT count(*) FROM usage_records")
    response = await net.call(
        "POST",
        "/v1/workbench/sessions",
        samuel,
        body={"subject_ref": {"kind": "tax_return", "id": str(item)}, "title": "Assistant"},
    )
    assert response.status_code == 409, response.text
    body = cast(dict[str, object], response.json())
    assert "capability_unavailable" in str(body) and "consent_7216" in str(body)
    assert await seed.value("SELECT count(*) FROM workbench_sessions") == 0
    assert await seed.value("SELECT count(*) FROM usage_records") == usage


async def test_history_lists_only_the_persons_threads_on_the_return(
    net: Net, seed: Seeder, world: World
) -> None:
    samuel = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, samuel, "manager")
    item = await _return(seed, world, samuel)
    refs = (
        f'[{{"kind": "engagement", "id": "{world.engagement_id}"}}, '
        f'{{"kind": "tax_return", "id": "{item}"}}]'
    )
    await seed.run(
        "INSERT INTO workbench_sessions (tenant_id, title, owner_user_id, origin, context_refs) "
        "VALUES ($1, 'Assistant', $2, 'manual', $3::jsonb)",
        world.tenant_id,
        samuel.user_id,
        refs,
    )
    seen = await net.call("GET", f"/v1/workbench/sessions?subject_ref=tax_return:{item}", samuel)
    assert seen.status_code == 200, seen.text
    assert len(cast(list[object], seen.json()["items"])) == 1
