"""F-03-T27 against Postgres (ADR-145, P-06): "Lena Park gets 404 for Ashford through every scope
kind, and the property test passes for all five kinds." For each kind, the rows a list filtered
by `visible_scope` returns are exactly the rows `authorise` (or, for a portal scope, the grant)
allows, person by person."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

import pytest
from sqlalchemy import Uuid, column, select, table

import abacus.modules.engagements.api  # registers the client lookups `visible_scope` reads
from abacus.kernel.db import TenantContext, configure_engine, tenant_session
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    visible_scope,
)
from abacus.modules.identity.client_access import scope_covers

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
assert abacus.modules.engagements.api
ACTION = "engagement.read_metadata"
Kind = Literal["engagement", "work_item", "client", "client_entity", "portal_scope"]


class _Firm:
    def __init__(self, seed: Seeder) -> None:
        self.seed = seed
        self.tenant = uuid.uuid4()
        self.engagements: dict[str, uuid.UUID] = {}
        self.clients: dict[str, uuid.UUID] = {}
        self.work_items: dict[str, uuid.UUID] = {}

    async def person(self, kind: str = "staff") -> uuid.UUID:
        user = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                    "VALUES ('https://probe.test', $1, $2, 'Probe') RETURNING id",
                    uuid.uuid4().hex,
                    f"{uuid.uuid4().hex}@example.test",
                )
            )
        )
        await self.seed.run(
            "INSERT INTO memberships (tenant_id, user_id, status, kind) "
            "VALUES ($1, $2, 'active', $3)",
            self.tenant,
            user,
            kind,
        )
        return user

    async def make(self) -> _Firm:
        await self.seed.run(
            "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", self.tenant
        )
        partner = await self.person()
        for name in ("Ashford", "Granite", "Northwind"):
            client = await self.seed.value(
                "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
                self.tenant,
                name,
            )
            entity = await self.seed.value(
                "INSERT INTO client_entities (tenant_id, client_id, name) "
                "VALUES ($1, $2, $3) RETURNING id",
                self.tenant,
                client,
                name,
            )
            engagement = await self.seed.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                "fiscal_period_start, fiscal_period_end, created_by, type, status) "
                "VALUES ($1, $2, $3, $4, '2025-01-01', '2025-12-31', $5, 'tax_compliance', "
                "'active') RETURNING id",
                self.tenant,
                client,
                entity,
                name,
                partner,
            )
            work_item = await self.seed.value(
                "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, "
                "kind, name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', $5, $6) "
                "RETURNING id",
                self.tenant,
                engagement,
                client,
                entity,
                f"{name} return",
                partner,
            )
            self.clients[name] = uuid.UUID(str(client))
            self.engagements[name] = uuid.UUID(str(engagement))
            self.work_items[name] = uuid.UUID(str(work_item))
        return self

    async def member(self, user: uuid.UUID, name: str, role: str) -> None:
        await self.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            self.tenant,
            self.engagements[name],
            user,
            role,
        )

    def ctx(self, user: uuid.UUID, firm_role: str | None = None) -> AuthContext:
        tenant = TenantContext(self.tenant, "human", str(user))
        return AuthContext(tenant, user, uuid.uuid4(), firm_role, datetime.now(UTC))  # type: ignore[arg-type]  # a literal firm role or None

    async def allowed(self, ctx: AuthContext, name: str) -> bool:
        resource = Resource.engagement(
            self.tenant, self.engagements[name], archived=False, client_id=self.clients[name]
        )
        try:
            await authorise(ctx, ACTION, resource)
        except Forbidden:
            return False
        return True


_TABLES = {
    "engagement": ("engagements", "id", "id"),
    "work_item": ("work_items", "id", "engagement_id"),
    "client": ("clients", "id", "id"),
    "client_entity": ("client_entities", "client_id", "client_id"),
    "portal_scope": ("work_items", "id", "id"),
}


async def _listed(firm: _Firm, ctx: AuthContext, kind: Kind) -> set[uuid.UUID]:
    """What a list of `kind` returns: for each row, the client or engagement it belongs to."""
    name, key, scoped = _TABLES[kind]
    key_column = column(key, Uuid())
    rows = table(name, key_column, column(scoped, Uuid()))
    query = (
        select(key_column)
        .select_from(rows)
        .where(
            visible_scope(
                ctx,
                ACTION,
                kind,
                column(scoped, Uuid()),
                grant_kind="work_item" if kind == "portal_scope" else None,
            )
        )
    )
    async with tenant_session(ctx.tenant) as session:
        found = (await session.execute(query)).scalars().all()
    return {uuid.UUID(str(v)) for v in found}


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> _Firm:
    configure_engine(migrated_db.app_url)  # a fresh pool on this test's event loop
    return await _Firm(Seeder(migrated_db.superuser_dsn)).make()


@pytest.mark.parametrize("kind", ["engagement", "work_item", "client", "client_entity"])
async def test_lena_park_never_sees_ashford_and_visible_agrees_with_authorise(
    firm: _Firm, kind: Kind
) -> None:
    lena = await firm.person()
    for name in ("Ashford", "Granite"):
        await firm.member(lena, name, "staff")
    await firm.seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $2)",
        firm.tenant,
        lena,
        firm.clients["Ashford"],
    )
    ctx = firm.ctx(lena)
    expected = {name for name in firm.engagements if await firm.allowed(ctx, name)}
    assert "Ashford" not in expected  # walled: authorise answers as if it doesn't exist
    by_kind = {
        "engagement": {firm.engagements[n] for n in expected},
        "work_item": {firm.work_items[n] for n in expected},
        "client": {firm.clients[n] for n in expected},
        "client_entity": {firm.clients[n] for n in expected},
    }
    assert await _listed(firm, ctx, kind) == by_kind[kind]


@pytest.mark.parametrize("kind", ["engagement", "work_item", "client", "client_entity"])
async def test_a_firm_role_that_reads_everything_still_misses_its_walled_client(
    firm: _Firm, kind: Kind
) -> None:
    admin = await firm.person()
    await firm.seed.run(
        "UPDATE memberships SET firm_role = 'firm_admin' WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant,
        admin,
    )
    await firm.seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $2)",
        firm.tenant,
        admin,
        firm.clients["Ashford"],
    )
    ctx = firm.ctx(admin, "firm_admin")
    expected = {name for name in firm.engagements if await firm.allowed(ctx, name)}
    assert expected == {"Granite", "Northwind"}
    by_kind = {
        "engagement": {firm.engagements[n] for n in expected},
        "work_item": {firm.work_items[n] for n in expected},
        "client": {firm.clients[n] for n in expected},
        "client_entity": {firm.clients[n] for n in expected},
    }
    assert await _listed(firm, ctx, kind) == by_kind[kind]


async def test_a_portal_scope_lists_exactly_what_the_grants_cover(firm: _Firm) -> None:
    meera = await firm.person("client")
    await firm.seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, 'taxpayer', 'work_item', $3)",
        firm.tenant,
        meera,
        firm.work_items["Granite"],
    )
    ctx = firm.ctx(meera)
    covered = {
        firm.work_items[name]
        for name in firm.engagements
        if await scope_covers(ctx.tenant, meera, firm.engagements[name], firm.work_items[name])
    }
    assert covered == {firm.work_items["Granite"]}
    assert await _listed(firm, ctx, "portal_scope") == covered
