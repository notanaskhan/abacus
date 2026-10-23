"""P-07-T08 and T09 against Postgres (SPEC-321 AC-6 to AC-8; clients contract §2-§7): the clients
index, record, overview, relationships and PATCH, as the app role. A walled client is absent from
rows, counts and the total and answers 404; a person sees the clients of their engagements, and a
partner-level member or a firm role every client; masked TINs only; a stale or illegal PATCH is a
409 and a good one writes one `client.updated` event."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta

import pytest

import abacus.modules.engagements.api  # registers the client facts and authz lookups
import abacus.modules.requests.api  # registers the open-request count
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.kernel.listing import CursorInvalid
from abacus.modules.identity.api import AuthContext
from abacus.modules.organisations import live
from abacus.modules.organisations.live import (
    ClientFilters,
    ClientPatch,
    IllegalTransition,
    NewRelationship,
    StaleVersion,
)

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

assert abacus.modules.engagements.api and abacus.modules.requests.api


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


class _Firm:
    def __init__(self, seed: Seeder) -> None:
        self.seed = seed
        self.tenant = uuid.uuid4()

    async def make(self) -> _Firm:
        await self.seed.run(
            "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Brightwater Hale')", self.tenant
        )
        return self

    async def person(
        self, *, firm_role: str | None = None, level: str | None = None
    ) -> AuthContext:
        user = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                    "VALUES ('https://probe.test', $1, $2, 'Dana Reyes') RETURNING id",
                    uuid.uuid4().hex,
                    f"{uuid.uuid4().hex}@example.test",
                )
            )
        )
        await self.seed.run(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status, level) "
            "VALUES ($1, $2, $3, 'active', $4)",
            self.tenant,
            user,
            firm_role,
            level,
        )
        return AuthContext(
            tenant=TenantContext(self.tenant, "human", str(user)),
            user_id=user,
            membership_id=uuid.uuid4(),
            firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
            mfa_at=datetime.now(UTC) - timedelta(minutes=1),
        )

    async def client(
        self, name: str, *, kind: str = "business", status: str = "active"
    ) -> tuple[uuid.UUID, uuid.UUID]:
        client = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO clients (tenant_id, name, kind, status) "
                    "VALUES ($1, $2, $3, $4) RETURNING id",
                    self.tenant,
                    name,
                    kind,
                    status,
                )
            )
        )
        entity = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO client_entities (tenant_id, client_id, name, entity_type) "
                    "VALUES ($1, $2, $3, 'llc') RETURNING id",
                    self.tenant,
                    client,
                    name,
                )
            )
        )
        return client, entity

    async def engagement(self, client: uuid.UUID, entity: uuid.UUID, by: uuid.UUID) -> uuid.UUID:
        return uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                    "fiscal_period_start, fiscal_period_end, created_by, type) "
                    "VALUES ($1, $2, $3, 'FY2025 return', '2025-01-01', '2025-12-31', $4, "
                    "'tax_compliance') RETURNING id",
                    self.tenant,
                    client,
                    entity,
                    by,
                )
            )
        )

    async def member(self, engagement: uuid.UUID, who: AuthContext, role: str) -> None:
        await self.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            self.tenant,
            engagement,
            who.user_id,
            role,
        )

    async def wall(self, who: AuthContext, client: uuid.UUID, by: AuthContext) -> None:
        await self.seed.run(
            "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
            "VALUES ($1, $2, $3, $4)",
            self.tenant,
            who.user_id,
            client,
            by.user_id,
        )


async def _firm(migrated_db: MigratedDatabase) -> _Firm:
    return await _Firm(Seeder(migrated_db.superuser_dsn)).make()


async def _list(ctx: AuthContext, filters: ClientFilters | None = None) -> list[str]:
    page = await live.list_clients(
        ctx, filters or ClientFilters(), sort="name", facets=False, cursor=None, limit=50
    )
    return [r.name for r in page.items]


async def test_ac6_the_index_is_exact_and_a_walled_client_is_simply_absent(
    migrated_db: MigratedDatabase,
) -> None:
    firm = await _firm(migrated_db)
    admin = await firm.person(firm_role="firm_admin")
    lena = await firm.person(firm_role="firm_admin")
    for name in ("Ashford Holdings", "Ridgeline Property Partners", "Copperleaf Studio"):
        await firm.client(name)
    await firm.client("Harbor Trust", kind="household", status="prospect")
    ashford = (
        (
            await live.list_clients(
                admin, ClientFilters(q="ashford"), sort="name", facets=False, cursor=None, limit=50
            )
        )
        .items[0]
        .id
    )
    await firm.wall(lena, ashford, admin)

    everyone = await live.list_clients(
        admin, ClientFilters(status="active"), sort="name", facets=True, cursor=None, limit=2
    )
    assert everyone.total == 3 and everyone.counts == {"active": 3, "prospect": 1}
    assert [r.name for r in everyone.items] == ["Ashford Holdings", "Copperleaf Studio"]
    assert everyone.next_cursor is not None
    rest = await live.list_clients(
        admin,
        ClientFilters(status="active"),
        sort="name",
        facets=False,
        cursor=everyone.next_cursor,
        limit=2,
    )
    assert [r.name for r in rest.items] == ["Ridgeline Property Partners"]
    assert {f.value for f in everyone.facets["kind"]} == {"business"}

    walled = await live.list_clients(
        lena, ClientFilters(status="active"), sort="name", facets=True, cursor=None, limit=50
    )
    # Same keys, one row fewer, nothing saying why (DEC-43).
    assert walled.total == 2 and walled.counts == {"active": 2, "prospect": 1}
    assert "Ashford Holdings" not in [r.name for r in walled.items]
    assert set(walled.model_dump()) == set(everyone.model_dump())
    with pytest.raises(NotFound):
        await live.client_record(lena, ashford)
    with pytest.raises(CursorInvalid):
        await live.list_clients(
            admin, ClientFilters(), sort="name", facets=False, cursor=everyone.next_cursor, limit=2
        )


async def test_ac6_a_person_sees_their_engagements_clients_and_a_partner_every_client(
    migrated_db: MigratedDatabase,
) -> None:
    firm = await _firm(migrated_db)
    admin = await firm.person(firm_role="firm_admin")
    senior = await firm.person()
    partner = await firm.person(level="partner")
    ridgeline, entity = await firm.client("Ridgeline Property Partners")
    await firm.client("Copperleaf Studio")
    engagement = await firm.engagement(ridgeline, entity, admin.user_id)
    await firm.member(engagement, senior, "senior")

    assert await _list(senior) == ["Ridgeline Property Partners"]
    assert await _list(partner) == ["Copperleaf Studio", "Ridgeline Property Partners"]
    assert await _list(senior, ClientFilters(q="ridge")) == ["Ridgeline Property Partners"]
    assert await _list(admin, ClientFilters(service_line="tax")) == ["Ridgeline Property Partners"]
    rows = (
        await live.list_clients(
            admin, ClientFilters(), sort="last_activity", facets=False, cursor=None, limit=50
        )
    ).items
    ridge = next(r for r in rows if r.name.startswith("Ridgeline"))
    assert ridge.service_lines == ["tax"] and ridge.open_request_count == 0
    assert ridge.entity_count == 1


async def test_ac7_the_record_masks_tins_and_derives_the_team(
    migrated_db: MigratedDatabase,
) -> None:
    firm = await _firm(migrated_db)
    admin = await firm.person(firm_role="firm_admin")
    manager = await firm.person()
    client, entity = await firm.client("Ridgeline Property Partners")
    await firm.seed.run(
        "UPDATE client_entities SET tin_status = 'applied_for' WHERE id = $1", entity
    )
    engagement = await firm.engagement(client, entity, admin.user_id)
    await firm.member(engagement, manager, "manager")

    record = await live.client_record(manager, client)
    assert record.manager_user_ids == [manager.user_id]
    assert record.entities[0].tin_kind == "ein"
    assert record.entities[0].tin_presence == "applied_for"
    assert record.entities[0].tin_last4 is None
    assert [e.id for e in record.active_engagements] == [engagement]
    assert record.tab_counts["engagements"] == 1 and record.tab_counts["messages"] is None
    assert record.client.version == 1
    assert "client.update" not in record.allowed_actions  # a manager edits from P-07-T09's grant
    assert "client.update" in (await live.client_record(admin, client)).allowed_actions

    profile, sections = await live.client_overview(manager, client)
    assert profile == "business"
    assert [s.code for s in sections][:1] == ["entities"]
    with pytest.raises(NotFound):
        await live.client_record(manager, uuid.uuid4())


async def test_ac8_patch_is_versioned_legal_and_audited(migrated_db: MigratedDatabase) -> None:
    firm = await _firm(migrated_db)
    admin = await firm.person(firm_role="firm_admin")
    staff = await firm.person()
    client, _ = await firm.client("Copperleaf Studio", status="prospect")

    with pytest.raises(IllegalTransition):
        await live.update_client(admin, client, ClientPatch(seen_version=1, status="active"))
    with pytest.raises(NotFound):  # a person off the client's engagements can't see it at all
        await live.update_client(staff, client, ClientPatch(seen_version=1, descriptor="Design"))
    await live.update_client(
        admin, client, ClientPatch(seen_version=1, descriptor="Design studio", status="former")
    )
    record = await live.client_record(admin, client)
    assert record.client.version == 2 and record.client.descriptor == "Design studio"
    with pytest.raises(StaleVersion):
        await live.update_client(admin, client, ClientPatch(seen_version=1, descriptor="Again"))
    events = await firm.seed.rows(
        "SELECT action, after_ref FROM audit_events WHERE tenant_id = $1 AND target_id = $2",
        firm.tenant,
        str(client),
    )
    assert [e["action"] for e in events] == ["client.updated"]
    assert "descriptor" in str(events[0]["after_ref"]) and "Design" not in str(
        events[0]["after_ref"]
    )


async def test_ac7_an_edge_into_a_walled_client_is_omitted(migrated_db: MigratedDatabase) -> None:
    firm = await _firm(migrated_db)
    admin = await firm.person(firm_role="firm_admin")
    lena = await firm.person(firm_role="firm_admin")
    trust, trust_entity = await firm.client("Harbor Trust", kind="household")
    ashford, ashford_entity = await firm.client("Ashford Holdings")
    copper, copper_entity = await firm.client("Copperleaf Studio")
    for to in (ashford_entity, copper_entity):
        await live.add_relationship(
            admin,
            NewRelationship(
                from_entity_id=trust_entity,
                to_entity_id=to,
                kind="owner_of",
                effective_from=date(2024, 1, 1),
                percent="50",
            ),
        )
    await firm.wall(lena, ashford, admin)

    seen = await live.client_relationships(admin, trust, None)
    assert seen.total == 2 and {r.to_client_id for r in seen.items} == {ashford, copper}
    assert {r.percent for r in seen.items} == {"50"}
    walled = await live.client_relationships(lena, trust, None)
    assert walled.total == 1 and [r.to_client_id for r in walled.items] == [copper]
    assert (await live.client_record(lena, trust)).tab_counts["relationships"] == 1
