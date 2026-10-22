"""TASK-373 (F-03-T26 contract step): a request item's client assignee is checked against
client access grants, as migration 0028's foreign key checked the team table, and losing the
last owner or contributor grant clears the assignment (the key's ON DELETE SET NULL)."""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from .support import Seeder

pytestmark = pytest.mark.asyncio


async def test_only_a_client_with_a_grant_can_be_assigned(seed: Seeder) -> None:
    tenant = uuid.uuid4()
    await seed.run("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", tenant)
    partner = await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, "assignee")
    contributor = await seed.client_contact(site, "client_contributor")
    stranger = await seed.client_contact(await seed.site(tenant, partner.user_id, "other"))

    item = await seed.item(site, "Bank statements", assignee=contributor)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.item(site, "Payroll registers", assignee=stranger)  # another engagement's

    await seed.run(
        "UPDATE client_access_grants SET status = 'revoked' WHERE tenant_id = $1 "
        "AND user_id = $2 AND scope_id = $3",
        tenant,
        contributor.user_id,
        site.engagement_id,
    )
    assignee = await seed.value(
        "SELECT client_assignee_user_id FROM request_items WHERE id = $1", item
    )
    assert assignee is None


async def test_a_second_grant_keeps_the_assignment(seed: Seeder) -> None:
    tenant = uuid.uuid4()
    await seed.run("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", tenant)
    partner = await seed.person(tenant)
    site = await seed.site(tenant, partner.user_id, "assignee-two")
    admin = await seed.client_contact(site, "client_admin")
    await seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, 'contributor', 'engagement', $3)",
        tenant,
        admin.user_id,
        site.engagement_id,
    )
    item = await seed.item(site, "Leases", assignee=admin)
    await seed.run(
        "UPDATE client_access_grants SET status = 'revoked' WHERE tenant_id = $1 "
        "AND user_id = $2 AND role = 'owner'",
        tenant,
        admin.user_id,
    )
    assignee = await seed.value(
        "SELECT client_assignee_user_id FROM request_items WHERE id = $1", item
    )
    assert assignee == admin.user_id
