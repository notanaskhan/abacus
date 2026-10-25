# ac-test-author: notanaskhan (G-01-T09; ADR-078's independent suite is G-01-T15)
"""G-01-T09 offshore over HTTP against Postgres (G-01 AC9.1 to AC9.3 as amended by TASK-1207;
DEC-52, DEC-319 narrowed, ADR P-12, §7216, F-03 section 4.4): Remy Vidal, marked offshore, keeps
ordinary work: he lists and opens his clients and engagements like anyone with his role, and so
does an agent acting for him; a consent provider changes no list and lifts no reveal; a real wall
still binds him (and his agent) at the wall layer; an offshore member can't be assigned to a
non-consented client (409 `offshore_consent_required`); ADM-03d lists him with 0 consented clients
and the two locked toggles.

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
    AgentContext,
    Forbidden,
    OffshoreConsentRequired,
    Resource,
    agent_context_for_run,
    allowed_actions,
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


# --- AC9.1, AC9.2 (amended, TASK-1207): offshore keeps ordinary work; walls still bind -----------

REVEALS = frozenset({"tin.reveal", "pii.reveal"})


async def test_ac9_1_remy_vidal_lists_and_opens_his_clients_like_anyone_with_his_role(
    firm: Firm,
) -> None:
    clients = await firm.get(firm.remy, "/v1/clients")
    assert clients.status_code == 200, clients.text
    assert {c["id"] for c in _items(clients)} == {
        str(firm.ashford.client_id),
        str(firm.granite.client_id),
    }
    assert cast(Json, clients.json())["total"] == 2
    for site in (firm.ashford, firm.granite):
        for path in (
            f"/v1/clients/{site.client_id}",
            f"/v1/engagements/{site.engagement_id}",
            f"/v1/engagements/{site.engagement_id}/team",
        ):
            seen = await firm.get(firm.remy, path)
            assert seen.status_code == 200, (path, seen.text)
            never = await firm.get(firm.remy, path.replace(str(site.client_id), str(uuid.uuid4())))
            if str(site.client_id) in path:
                assert (never.status_code, never.json()) == (404, NOT_FOUND), path
    engagements = await firm.get(firm.remy, "/v1/engagements")
    assert str(firm.ashford.engagement_id) in engagements.text
    assert str(firm.granite.engagement_id) in engagements.text
    # The control: an onshore member on the same engagements sees the same.
    control = await firm.get(firm.partner, "/v1/engagements")
    assert str(firm.granite.engagement_id) in control.text


async def test_ac9_1_a_wall_still_binds_remy_vidal(firm: Firm) -> None:
    """Walls are unaffected (TASK-1207): walled from Ashford, offshore Remy reads it as unknown."""
    await firm.net.wall(firm.grace, firm.remy.user_id, firm.ashford.client_id)
    clients = await firm.get(firm.remy, "/v1/clients")
    assert [c["id"] for c in _items(clients)] == [str(firm.granite.client_id)]
    for path in (
        f"/v1/clients/{firm.ashford.client_id}",
        f"/v1/engagements/{firm.ashford.engagement_id}",
    ):
        walled = await firm.get(firm.remy, path)
        assert (walled.status_code, walled.json()) == (404, NOT_FOUND), path
    granite = await firm.get(firm.remy, f"/v1/engagements/{firm.granite.engagement_id}")
    assert granite.status_code == 200, granite.text


async def _agent_for_remy(firm: Firm) -> AgentContext:
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
    return await agent_context_for_run(
        tenant_id=firm.tenant_id,
        run_id=run,
        agent_id="evidence.screener",
        engagement_id=firm.granite.engagement_id,
        task_scope=frozenset({"evidence.read"}),
        initiator_user_id=firm.remy.user_id,
    )


async def test_ac9_2_an_agent_acting_for_remy_reads_like_him_and_a_wall_binds_it(
    firm: Firm,
) -> None:
    agent = await _agent_for_remy(firm)
    resource = Resource.engagement(firm.tenant_id, firm.granite.engagement_id, archived=False)
    await authorise(agent, "evidence.read", resource)
    await firm.net.wall(firm.grace, firm.remy.user_id, firm.granite.client_id)
    with pytest.raises(Forbidden) as denied:
        await authorise(agent, "evidence.read", resource)
    assert denied.value.layer == "wall"


async def test_ac9_2_a_registered_provider_changes_no_list_and_lifts_no_reveal(
    firm: Firm, granite_consented: None
) -> None:
    clients = await firm.get(firm.remy, "/v1/clients")
    assert {c["id"] for c in _items(clients)} == {
        str(firm.ashford.client_id),
        str(firm.granite.client_id),
    }
    for site in (firm.ashford, firm.granite):
        assert (await firm.get(firm.remy, f"/v1/clients/{site.client_id}")).status_code == 200
        resource = Resource.engagement(firm.tenant_id, site.engagement_id, archived=False)
        allowed = await allowed_actions(context(firm.remy), resource)
        assert "engagement.read" in allowed
        assert not REVEALS & allowed  # DEC-52: consent or not, an offshore member never reveals
    engagements = await firm.get(firm.remy, "/v1/engagements")
    assert str(firm.granite.engagement_id) in engagements.text
    assert str(firm.ashford.engagement_id) in engagements.text


async def test_ac9_2_offshore_on_or_off_access_follows_roles(firm: Firm) -> None:
    path = f"/v1/engagements/{firm.granite.engagement_id}"
    assert (await firm.get(firm.remy, path)).status_code == 200
    await firm.net.seed.run(
        "UPDATE memberships SET offshore = false WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant_id,
        firm.remy.user_id,
    )
    response = await firm.get(firm.remy, path)
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


# --- TASK-1207 security review, items 3 and 4: every way onto a team checks the consent --------

PERIOD = {"fiscal_period_start": "2026-01-01", "fiscal_period_end": "2026-12-31"}


async def _engagements_of(firm: Firm) -> int:
    return cast(
        int,
        await firm.net.seed.value(
            "SELECT count(*) FROM engagements WHERE tenant_id = $1", firm.tenant_id
        ),
    )


async def _offshore_on(firm: Firm, who: Person) -> None:
    await firm.net.seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant_id,
        who.user_id,
    )


async def test_review3_an_offshore_partner_creating_an_engagement_needs_the_consent(
    firm: Firm,
) -> None:
    """The creator becomes engagement partner: offshore without consent is 409 and nothing is
    kept, for an offshore partner's new client (none can have a consent yet) and an offshore
    firm admin's existing client."""
    await _offshore_on(firm, firm.partner)
    await _offshore_on(firm, firm.grace)
    before = await _engagements_of(firm)
    new = await firm.net.call(
        "POST",
        "/v1/engagements",
        firm.partner,
        body={
            "name": "Fresh 2026",
            "client_name": "Fresh client",
            "client_entity_name": "Fresh client LLC",
            "confirm_new": True,
            **PERIOD,
        },
    )
    assert new.status_code == 409, new.text
    assert new.json()["detail"] == "offshore_consent_required"
    existing = await firm.net.call(
        "POST",
        "/v1/engagements",
        firm.grace,
        body={
            "name": "Granite 2026",
            "client_name": "Granite",
            "client_entity_name": "Granite LLC",
            "client_id": str(firm.granite.client_id),
            "client_entity_id": str(firm.granite.entity_id),
            **PERIOD,
        },
    )
    assert existing.status_code == 409, existing.text
    assert existing.json()["detail"] == "offshore_consent_required"
    assert await _engagements_of(firm) == before


async def test_review3_a_consented_client_lets_an_offshore_creator_create(
    firm: Firm, granite_consented: None
) -> None:
    await _offshore_on(firm, firm.grace)
    created = await firm.net.call(
        "POST",
        "/v1/engagements",
        firm.grace,
        body={
            "name": "Granite 2026",
            "client_name": "Granite",
            "client_entity_name": "Granite LLC",
            "client_id": str(firm.granite.client_id),
            "client_entity_id": str(firm.granite.entity_id),
            **PERIOD,
        },
    )
    assert created.status_code == 201, created.text


async def test_review3_roll_forward_leaves_out_an_offshore_member_and_refuses_one(
    firm: Firm,
) -> None:
    """Last year's team: an offshore member without the client's consent isn't available, and
    adding them anyway is 409, inside the creating unit of work."""
    from abacus.kernel.uow import uow
    from abacus.modules.identity.api import add_rolled_forward_member, available_staff

    nora = await firm.net.person(firm.tenant_id)
    tenant = TenantContext(firm.tenant_id, "human", str(firm.grace.user_id))
    assert nora.user_id in await available_staff(tenant, firm.granite.client_id)
    await firm.net.seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant_id,
        nora.user_id,
    )
    assert nora.user_id not in await available_staff(tenant, firm.granite.client_id)
    grace = context(firm.grace, "firm_admin")
    with pytest.raises(OffshoreConsentRequired):
        async with uow(grace.tenant) as tx:
            await add_rolled_forward_member(
                tx,
                grace,
                firm.granite.engagement_id,
                firm.granite.client_id,
                nora.user_id,
                "staff",
            )
    on_team = await firm.net.seed.value(
        "SELECT count(*) FROM engagement_members WHERE user_id = $1", nora.user_id
    )
    assert on_team == 0


async def test_review3_a_consented_client_keeps_an_offshore_member_available(
    firm: Firm, granite_consented: None
) -> None:
    from abacus.modules.identity.api import available_staff

    nora = await firm.net.person(firm.tenant_id)
    await firm.net.seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant_id,
        nora.user_id,
    )
    tenant = TenantContext(firm.tenant_id, "human", str(firm.grace.user_id))
    assert nora.user_id in await available_staff(tenant, firm.granite.client_id)
    assert nora.user_id not in await available_staff(tenant, firm.ashford.client_id)


async def test_review3_an_offshore_admin_self_joining_needs_the_consent(firm: Firm) -> None:
    await firm.net.seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant_id,
        firm.grace.user_id,
    )
    joined = await firm.net.call(
        "POST", f"/v1/engagements/{firm.granite.engagement_id}/self-join", firm.grace
    )
    assert joined.status_code == 409, joined.text
    assert joined.json()["detail"] == "offshore_consent_required"
    on_team = await firm.net.seed.value(
        "SELECT count(*) FROM engagement_members WHERE engagement_id = $1 AND user_id = $2",
        firm.granite.engagement_id,
        firm.grace.user_id,
    )
    assert on_team == 0


async def test_review4_provisioning_cant_turn_offshore_on_over_assignments(firm: Firm) -> None:
    """`set_member_profile` (directory sync, provisioning, the loader) applies the same guard as
    the person drawer: offshore can't be turned on while the person holds assignments."""
    from abacus.kernel.uow import uow
    from abacus.modules.identity.api import MemberProfile, set_member_profile
    from abacus.modules.identity.people import OffshoreAssignmentConflict

    tenant = TenantContext(firm.tenant_id, "system", "provisioning")
    with pytest.raises(OffshoreAssignmentConflict):
        async with uow(tenant) as tx:
            await set_member_profile(
                tx,
                firm.tenant_id,
                firm.partner.user_id,
                MemberProfile(role_template="partner", level="partner", offshore=True),
            )
    assert not await firm.net.seed.value(
        "SELECT offshore FROM memberships WHERE user_id = $1", firm.partner.user_id
    )
