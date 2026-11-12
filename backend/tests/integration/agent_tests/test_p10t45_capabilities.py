"""P-10-T45 (TASK-7303; DEC-4303): `GET /v1/agents/capabilities?engagement_id=` over HTTP.

Row acceptance: "For the Stein taxpayer the tax capabilities read unavailable with reason
consent_7216 and no usage row is written." The engagement's taxpayer here holds no §7216 consent.
"""

from __future__ import annotations

from typing import cast

import httpx
import pytest

from abacus.kernel.flags import forget_flags
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Seeder, World
from .walls_support import Net

pytestmark = pytest.mark.asyncio


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


async def test_the_stein_taxpayer_reads_consent_7216_with_no_usage_row(
    net: Net, seed: Seeder, world: World
) -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'agent_runtime.v2', 'true', 'p10-t45', 'P-10-T45') ON CONFLICT DO NOTHING",
        world.tenant_id,
    )
    forget_flags()
    hannah = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, hannah, "manager")
    usage_before = await seed.value("SELECT count(*) FROM usage_records")
    response = await net.call(
        "GET", f"/v1/agents/capabilities?engagement_id={world.engagement_id}", hannah
    )
    assert response.status_code == 200, response.text
    items = {i["capability"]: i for i in cast(list[dict[str, object]], response.json()["items"])}
    for tax in ("tax.return_drafter", "tax.return_analyst"):
        assert items[tax]["available"] is False and items[tax]["reason"] == "consent_7216"
    assert "runtime.conformance" not in items  # never for a real firm
    assert await seed.value("SELECT count(*) FROM usage_records") == usage_before


async def test_a_walled_engagement_answers_404(net: Net, seed: Seeder, world: World) -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'agent_runtime.v2', 'true', 'p10-t45', 'P-10-T45') ON CONFLICT DO NOTHING",
        world.tenant_id,
    )
    forget_flags()
    hannah = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, hannah, "manager")
    client = await seed.value(
        "SELECT client_id FROM engagements WHERE id = $1", world.engagement_id
    )
    admin = await net.person(world.tenant_id, "firm_admin")
    await net.wall(admin, hannah.user_id, client)  # type: ignore[arg-type]  # a client uuid
    walled = await net.call(
        "GET", f"/v1/agents/capabilities?engagement_id={world.engagement_id}", hannah
    )
    assert walled.status_code == 404
