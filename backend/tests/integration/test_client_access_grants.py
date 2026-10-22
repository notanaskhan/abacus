"""F-03-T26 against Postgres (ADR-146): "every former client_admin/client_contributor row is an
owner/contributor grant" (migration 0083's backfill, checked down and up on a private
database), and Meera Shah's grants yield a
role-union shell limited to her own scopes (story 5.2). The contract step (0084) leaves no
client role on the team table, and removal and re-invitation move the grant."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import asyncpg
import pytest

import abacus.modules.engagements.api  # registers the scope resolvers and the client lookup
from abacus.kernel.db import TenantContext, configure_engine
from abacus.kernel.uow import Target, uow
from abacus.modules.identity.api import AuthContext, portal_scopes
from abacus.modules.identity.client_access import scope_covers
from abacus.modules.identity.repository import (
    engagement_role,
    grant_engagement_role,
    remove_client_member,
)
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

assert abacus.modules.engagements.api
BEFORE = "0082"


class _Firm:
    def __init__(self, seed: Seeder) -> None:
        self.seed = seed
        self.tenant = uuid.uuid4()
        self.partner = uuid.uuid4()

    async def make(self) -> _Firm:
        await self.seed.run(
            "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", self.tenant
        )
        self.partner = await self.user("staff")
        return self

    async def user(self, kind: str) -> uuid.UUID:
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

    async def engagement(self, name: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
        client = await self.seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id", self.tenant, name
        )
        entity = await self.seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
            "RETURNING id",
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
            self.partner,
        )
        return uuid.UUID(str(client)), uuid.UUID(str(entity)), uuid.UUID(str(engagement))

    async def member(self, engagement: uuid.UUID, user: uuid.UUID, role: str) -> None:
        await self.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, $4)",
            self.tenant,
            engagement,
            user,
            role,
        )

    async def grants(self, user: uuid.UUID) -> set[tuple[str, str, uuid.UUID, str]]:
        rows = await self.seed.rows(
            "SELECT role, scope_kind, scope_id, status FROM client_access_grants "
            "WHERE tenant_id = $1 AND user_id = $2",
            self.tenant,
            user,
        )
        return {(r["role"], r["scope_kind"], r["scope_id"], r["status"]) for r in rows}


# --- the backfill, down and up ----------------------------------------------------------------


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def test_every_former_client_role_row_is_an_owner_or_contributor_grant(
    private_db: sc.Database,
) -> None:
    seed = Seeder(private_db.superuser_dsn)
    migrate(private_db.owner_url, BEFORE, down=True)

    async def before() -> tuple[_Firm, uuid.UUID, uuid.UUID, uuid.UUID]:
        firm = await _Firm(seed).make()
        _, _, engagement = await firm.engagement("Probe client")
        admin, contributor = await firm.user("client"), await firm.user("client")
        await firm.member(engagement, admin, "client_admin")
        await firm.member(engagement, contributor, "client_contributor")
        await firm.member(engagement, firm.partner, "engagement_partner")
        return firm, engagement, admin, contributor

    firm, engagement, admin, contributor = asyncio.run(before())
    migrate(private_db.owner_url, "head")

    async def after() -> None:
        assert await firm.grants(admin) == {("owner", "engagement", engagement, "active")}
        assert await firm.grants(contributor) == {
            ("contributor", "engagement", engagement, "active")
        }
        assert await firm.grants(firm.partner) == set()  # staff roles aren't client grants
        # The contract step (0084): no client role is left on the team table.
        left = await seed.value(
            "SELECT count(*) FROM engagement_members WHERE tenant_id = $1 "
            "AND role IN ('client_admin', 'client_contributor')",
            firm.tenant,
        )
        assert left == 0
        events = await seed.value(
            "SELECT count(*) FROM client_access_events WHERE tenant_id = $1 AND event = 'granted'",
            firm.tenant,
        )
        assert events == 2

    asyncio.run(after())
    migrate(private_db.owner_url, BEFORE, down=True)
    migrate(private_db.owner_url, "head")
    assert sc.check(private_db.owner_url, private_db.app_url) == []


# --- the shared database: the mirror and story 5.2 ----------------------------------------------


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> _Firm:
    configure_engine(migrated_db.app_url)  # a fresh pool on this test's event loop
    return await _Firm(Seeder(migrated_db.superuser_dsn)).make()


@pytest.mark.asyncio
async def test_removal_revokes_the_grant_and_a_new_invitation_restores_it(firm: _Firm) -> None:
    _, _, engagement = await firm.engagement("Probe")
    user = await firm.user("client")
    tenant = TenantContext(firm.tenant, "human", str(firm.partner))
    async with uow(tenant) as tx:
        await grant_engagement_role(
            tx.session,
            tenant_id=firm.tenant,
            engagement_id=engagement,
            user_id=user,
            role="client_contributor",
            by=firm.partner,
        )
        tx.record("client_access.probed", target=Target("engagement", engagement))
    assert await firm.grants(user) == {("contributor", "engagement", engagement, "active")}
    assert await engagement_role(tenant, user, engagement) == "client_contributor"
    async with uow(tenant) as tx:
        assert await remove_client_member(tx.session, engagement, user) is True
        tx.record("client_access.probed", target=Target("engagement", engagement))
    assert await firm.grants(user) == {("contributor", "engagement", engagement, "revoked")}
    assert await engagement_role(tenant, user, engagement) is None
    async with uow(tenant) as tx:
        await grant_engagement_role(
            tx.session,
            tenant_id=firm.tenant,
            engagement_id=engagement,
            user_id=user,
            role="client_contributor",
            by=firm.partner,
        )
        tx.record("client_access.probed", target=Target("engagement", engagement))
    assert await firm.grants(user) == {("contributor", "engagement", engagement, "active")}
    events = await firm.seed.rows(
        "SELECT event FROM client_access_events WHERE tenant_id = $1 ORDER BY id", firm.tenant
    )
    assert [r["event"] for r in events] == ["granted", "revoked", "activated"]


@pytest.mark.asyncio
async def test_a_client_role_no_longer_fits_the_team_table(firm: _Firm) -> None:
    _, _, engagement = await firm.engagement("Probe")
    user = await firm.user("client")
    with pytest.raises(asyncpg.CheckViolationError):
        await firm.member(engagement, user, "client_admin")


@pytest.mark.asyncio
async def test_a_grant_needs_a_client_membership(firm: _Firm) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await firm.seed.run(
            "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
            "VALUES ($1, $2, 'owner', 'engagement', $3)",
            firm.tenant,
            firm.partner,  # staff
            uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_story_5_2_meera_shahs_role_union_is_her_own_scopes(firm: _Firm) -> None:
    _, shah_entity, shah = await firm.engagement("Shah household")
    _, ridgeline_entity, ridgeline = await firm.engagement("Ridgeline Property Partners, LP")
    meera = await firm.user("client")

    async def work_item(engagement: uuid.UUID, client_entity: uuid.UUID, name: str) -> uuid.UUID:
        client = await firm.seed.value(
            "SELECT client_id FROM engagements WHERE id = $1", engagement
        )
        return uuid.UUID(
            str(
                await firm.seed.value(
                    "INSERT INTO work_items (tenant_id, engagement_id, client_id, "
                    "client_entity_id, kind, name, created_by) "
                    "VALUES ($1, $2, $3, $4, 'tax_return', $5, $6) RETURNING id",
                    firm.tenant,
                    engagement,
                    client,
                    client_entity,
                    name,
                    firm.partner,
                )
            )
        )

    own_return = await work_item(shah, shah_entity, "2025 Form 1040")
    ridgeline_return = await work_item(ridgeline, ridgeline_entity, "2025 Form 1065")
    k1_package = uuid.uuid4()
    for role, kind, scope in (
        ("taxpayer", "work_item", own_return),
        ("k1_recipient", "k1_package", k1_package),
    ):
        await firm.seed.run(
            "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
            "VALUES ($1, $2, $3, $4, $5)",
            firm.tenant,
            meera,
            role,
            kind,
            scope,
        )
    tenant = TenantContext(firm.tenant, "human", str(meera))
    ctx = AuthContext(tenant, meera, uuid.uuid4(), None, datetime.now(UTC))
    scopes = await portal_scopes(ctx)
    assert scopes.shell == "full"
    assert {(s.role, s.scope_kind, s.scope_id) for s in scopes.scopes} == {
        ("taxpayer", "work_item", own_return),
        ("k1_recipient", "k1_package", k1_package),
    }
    assert await scope_covers(tenant, meera, shah, own_return) is True
    assert await scope_covers(tenant, meera, ridgeline, ridgeline_return) is False
    assert await scope_covers(tenant, meera, ridgeline, None) is False
