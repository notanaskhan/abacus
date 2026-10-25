# ac-test-author: notanaskhan (G-01-T09; ADR-078's independent suite is G-01-T15)
"""G-01-T09 offshore fail-closed over HTTP against Postgres (G-01 AC9.1 to AC9.3; DEC-52,
ADR P-12, §7216): Remy Vidal, marked offshore, sees 0 clients until a consent provider is
registered: every client and engagement reads as never-existed (404, no count, metadata
included), and so for an agent acting for him; once a provider is registered only consented
clients appear, with no other change; an offshore member can't be assigned to a non-consented
client (409 `offshore_consent_required`); ADM-03d lists him with 0 consented clients and the
two locked toggles.

Expectations come from G-01 section 3.9, not from the implementation."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import cast

import httpx
import pytest
from sqlalchemy import ColumnElement, literal

from abacus.kernel.db import TenantContext
from abacus.modules.engagements.api import assign_work_item
from abacus.modules.identity import slots
from abacus.modules.identity.api import (
    Forbidden,
    OffshoreConsentRequired,
    Resource,
    agent_context_for_run,
    assert_assignable,
    authorise,
)
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Person, Seeder
from .walls_support import NOT_FOUND, Json, Net, Site, context

FLAGS = ("firm_settings.v2", "clients.v2", "engagements.v2")


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    grace: Person
    partner: Person
    remy: Person
    ashford: Site
    granite: Site

    async def get(self, who: Person, path: str) -> httpx.Response:
        return await self.net.call("GET", path, who)


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant = await seed.firm()
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'G-01-T09')",
            tenant,
            flag,
        )
    grace = await net.person(tenant, "firm_admin")
    partner = await net.partner(tenant)
    remy = await net.person(tenant)
    ashford = await net.site(tenant, grace.user_id)
    granite = await net.site(tenant, grace.user_id)
    for site in (ashford, granite):
        await seed.member(site.engagement_id, remy, "staff")
        await seed.member(site.engagement_id, partner, "engagement_partner")
    await seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        remy.user_id,
    )
    return Firm(net, tenant, grace, partner, remy, ashford, granite)


@pytest.fixture
def granite_consented(firm: Firm) -> Iterator[None]:
    """T-01's provider stand-in: a valid offshore-disclosure consent covers Granite only."""
    granite = firm.granite.client_id

    async def check(_tenant: TenantContext, client: uuid.UUID, _p: str, _at: datetime) -> bool:
        return client == granite

    def column(client_id: object, _purpose: str) -> ColumnElement[bool]:
        return cast(ColumnElement[uuid.UUID], client_id) == literal(granite)

    async def count(_tenant: TenantContext, _purpose: str) -> int:
        return 1

    slots.register_consent_check(slots.OFFSHORE_DISCLOSURE, check, column, count)
    yield
    slots._CONSENTS.pop(slots.OFFSHORE_DISCLOSURE, None)  # pyright: ignore[reportPrivateUsage] -- drops the stand-in
    slots._CONSENT_COLUMNS.pop(slots.OFFSHORE_DISCLOSURE, None)  # pyright: ignore[reportPrivateUsage] -- drops the stand-in
    slots._CONSENT_COUNTS.pop(slots.OFFSHORE_DISCLOSURE, None)  # pyright: ignore[reportPrivateUsage] -- drops the stand-in


def _items(response: httpx.Response) -> list[Json]:
    body = response.json()
    if isinstance(body, list):
        return cast(list[Json], body)
    return cast(list[Json], cast(Json, body)["items"])


# --- AC9.1, AC9.2: 0 clients, fail closed --------------------------------------------------------


async def test_ac9_1_remy_vidal_sees_0_clients_and_every_deep_link_answers_404(
    firm: Firm,
) -> None:
    clients = await firm.get(firm.remy, "/v1/clients")
    assert clients.status_code == 200, clients.text
    assert _items(clients) == []
    assert cast(Json, clients.json())["total"] == 0
    for site in (firm.ashford, firm.granite):
        for path in (
            f"/v1/clients/{site.client_id}",
            f"/v1/engagements/{site.engagement_id}",
            f"/v1/engagements/{site.engagement_id}/team",
        ):
            seen = await firm.get(firm.remy, path)
            never = await firm.get(firm.remy, path.replace(str(site.client_id), str(uuid.uuid4())))
            assert (seen.status_code, seen.json()) == (404, NOT_FOUND), path
            if str(site.client_id) in path:
                assert (never.status_code, never.text) == (seen.status_code, seen.text)
    engagements = await firm.get(firm.remy, "/v1/engagements")
    assert str(firm.ashford.engagement_id) not in engagements.text
    assert str(firm.granite.engagement_id) not in engagements.text
    # The control: an onshore member on the same engagements sees both.
    control = await firm.get(firm.partner, "/v1/engagements")
    assert str(firm.granite.engagement_id) in control.text


async def test_ac9_2_an_agent_acting_for_remy_is_refused_at_the_wall(firm: Firm) -> None:
    run = cast(
        uuid.UUID,
        await firm.net.seed.value(
            "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
            "initiator_user_id, task_scope, status) VALUES ($1, 'evidence.screener', 1, $2, "
            "$3, '{}', 'running') RETURNING id",
            firm.tenant_id,
            firm.granite.engagement_id,
            firm.remy.user_id,
        ),
    )
    agent = await agent_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=run,
        agent_id="evidence.screener",
        engagement_id=firm.granite.engagement_id,
        task_scope=frozenset({"evidence.read"}),
        initiator_user_id=firm.remy.user_id,
    )
    resource = Resource.engagement(firm.tenant_id, firm.granite.engagement_id, archived=False)
    with pytest.raises(Forbidden) as denied:
        await authorise(agent, "evidence.read", resource)
    assert denied.value.layer == "wall"


async def test_ac9_2_a_registered_provider_shows_only_consented_clients(
    firm: Firm, granite_consented: None
) -> None:
    clients = await firm.get(firm.remy, "/v1/clients")
    assert [c["id"] for c in _items(clients)] == [str(firm.granite.client_id)]
    assert (await firm.get(firm.remy, f"/v1/clients/{firm.granite.client_id}")).status_code == 200
    walled = await firm.get(firm.remy, f"/v1/clients/{firm.ashford.client_id}")
    assert (walled.status_code, walled.json()) == (404, NOT_FOUND)
    engagements = await firm.get(firm.remy, "/v1/engagements")
    assert str(firm.granite.engagement_id) in engagements.text
    assert str(firm.ashford.engagement_id) not in engagements.text


async def test_ac9_2_turning_offshore_off_restores_access_by_roles(firm: Firm) -> None:
    await firm.net.seed.run(
        "UPDATE memberships SET offshore = false WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant_id,
        firm.remy.user_id,
    )
    response = await firm.get(firm.remy, f"/v1/engagements/{firm.granite.engagement_id}")
    assert response.status_code == 200


# --- AC9.3: assignment is refused; the policy is locked ------------------------------------------


async def test_ac9_3_an_offshore_member_is_not_assignable_to_a_non_consented_client(
    firm: Firm,
) -> None:
    tenant = TenantContext(firm.tenant_id, "human", str(firm.grace.user_id))
    with pytest.raises(OffshoreConsentRequired):
        await assert_assignable(tenant, firm.remy.user_id, firm.granite.client_id)
    work_item = cast(
        uuid.UUID,
        await firm.net.seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 LIMIT 1",
            firm.granite.engagement_id,
        ),
    )
    with pytest.raises(OffshoreConsentRequired):
        await assign_work_item(context(firm.partner), work_item, firm.remy.user_id, "preparer")
    assert (
        await firm.net.seed.value(
            "SELECT count(*) FROM work_item_assignments WHERE user_id = $1", firm.remy.user_id
        )
        == 0
    )


async def test_ac9_3_a_consented_client_is_assignable(firm: Firm, granite_consented: None) -> None:
    tenant = TenantContext(firm.tenant_id, "human", str(firm.grace.user_id))
    await assert_assignable(tenant, firm.remy.user_id, firm.granite.client_id)
    with pytest.raises(OffshoreConsentRequired):
        await assert_assignable(tenant, firm.remy.user_id, firm.ashford.client_id)


async def test_ac9_1_adm03d_lists_remy_with_0_consented_clients_and_locked_toggles(
    firm: Firm,
) -> None:
    response = await firm.get(firm.grace, "/v1/firm/offshore")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "member_ids": [str(firm.remy.user_id)],
        "consented_client_count": 0,
        "block_without_consent": True,
        "mask_tins": True,
    }


async def test_review_an_offshore_admin_cannot_clear_their_own_offshore_flag(firm: Firm) -> None:
    """Offshore is a restriction on the person: they never lift it themself (another admin
    may), like a wall."""
    from abacus.modules.identity import people

    await firm.net.seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant_id,
        firm.grace.user_id,
    )
    grace = context(firm.grace, "firm_admin")
    version = cast(
        int,
        await firm.net.seed.value(
            "SELECT version FROM memberships WHERE user_id = $1", firm.grace.user_id
        ),
    )
    with pytest.raises(people.OwnOffshore):
        await people.update_person(grace, firm.grace.user_id, version, {"offshore": False})
    assert await firm.net.seed.value(
        "SELECT offshore FROM memberships WHERE user_id = $1", firm.grace.user_id
    )
    other = await firm.net.person(firm.tenant_id, "firm_admin")
    await people.update_person(
        context(other, "firm_admin"), firm.grace.user_id, version, {"offshore": False}
    )
    assert not await firm.net.seed.value(
        "SELECT offshore FROM memberships WHERE user_id = $1", firm.grace.user_id
    )
