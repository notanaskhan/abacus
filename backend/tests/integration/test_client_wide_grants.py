"""DEC-211 (DEC-129) against Postgres: a full-client grant on a client or client entity holds the
matrix's client role on that client's (or entity's) engagements, in `authorise` and in `visible()`
alike; limited roles, `delegate`, other clients and revoked or expired grants hold none."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.modules.identity.api import engagement_role_of
from abacus.modules.portal.home import read_home

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _client_person(seed: Seeder, tenant: uuid.UUID) -> Person:
    who = await seed.person(tenant)
    await seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        who.user_id,
    )
    return who


async def _grant(
    seed: Seeder, who: Person, role: str, kind: str, scope: uuid.UUID, *, status: str = "active"
) -> None:
    await seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id, "
        "status) VALUES ($1, $2, $3, $4, $5, $6)",
        who.tenant_id,
        who.user_id,
        role,
        kind,
        scope,
        status,
    )


async def _client_of(seed: Seeder, entity: uuid.UUID) -> uuid.UUID:
    return cast(
        uuid.UUID, await seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity)
    )


async def test_a_household_taxpayer_is_client_admin_on_its_clients_engagements(
    seed: Seeder,
) -> None:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    feld = await seed.entity(tenant, "Jonah & Claire Feld")
    ours = await seed.engagement(tenant, feld, partner.user_id)
    other = await seed.engagement(tenant, await seed.entity(tenant, "Ridgeline"), partner.user_id)
    claire = await _client_person(seed, tenant)
    await _grant(seed, claire, "taxpayer", "client", await _client_of(seed, feld))

    assert await engagement_role_of(claire.context().tenant, ours, claire.user_id) == (
        "client_admin"
    )
    assert await engagement_role_of(claire.context().tenant, other, claire.user_id) is None
    home = await read_home(claire.context(), None)
    assert home.scope.kind == "client" and home.scope.label == "Seeded client"
    assert {c.work_item_id for c in home.work_cards} == {
        await seed.value("SELECT id FROM work_items WHERE engagement_id = $1", ours)
    }


async def test_a_client_entity_grant_covers_that_entitys_engagements_only(seed: Seeder) -> None:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    roasters = await seed.entity(tenant, "Copperleaf Coffee Roasters, Inc.")
    client = await _client_of(seed, roasters)
    sister = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) "
            "VALUES ($1, $2, 'Copperleaf Holdings LLC') RETURNING id",
            tenant,
            client,
        ),
    )
    covered = await seed.engagement(tenant, roasters, partner.user_id)
    not_covered = await seed.engagement(tenant, sister, partner.user_id)
    tess = await _client_person(seed, tenant)
    await _grant(seed, tess, "owner", "client_entity", roasters)

    assert await engagement_role_of(tess.context().tenant, covered, tess.user_id) == "client_admin"
    assert await engagement_role_of(tess.context().tenant, not_covered, tess.user_id) is None


@pytest.mark.parametrize(
    ("role", "status", "expected"),
    [
        ("contributor", "active", "client_contributor"),
        ("spouse", "active", "client_admin"),
        ("delegate", "active", None),  # P-09's cells (DEC-158)
        ("third_party", "active", None),
        ("k1_recipient", "active", None),
        ("taxpayer", "revoked", None),
        ("taxpayer", "pending", None),
    ],
)
async def test_only_active_full_client_roles_hold_a_role(
    seed: Seeder, role: str, status: str, expected: str | None
) -> None:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, partner.user_id)
    who = await _client_person(seed, tenant)
    await _grant(seed, who, role, "client", await _client_of(seed, entity), status=status)

    assert await engagement_role_of(who.context().tenant, engagement, who.user_id) == expected


async def test_an_expired_client_wide_grant_holds_nothing(seed: Seeder) -> None:
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, partner.user_id)
    who = await _client_person(seed, tenant)
    await seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id, "
        "status, expires_at) VALUES ($1, $2, 'taxpayer', 'client', $3, 'active', "
        "now() - interval '1 day')",
        tenant,
        who.user_id,
        await _client_of(seed, entity),
    )
    assert await engagement_role_of(who.context().tenant, engagement, who.user_id) is None
