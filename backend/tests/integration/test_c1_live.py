"""F-03-T31 against Postgres (C1 live): "GET /v1/work-items lists Brightwater Hale work items of
all five kinds with per-status counts". Built through `engagements.api.create_work_item`, read
through `list_work_items` (the route's service), filtered by `visible_scope`."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest

import abacus.modules.closes.api
import abacus.modules.notices.api
import abacus.modules.tax.api  # register their kinds
from abacus.kernel.db import TenantContext, configure_engine
from abacus.modules.engagements.api import create_work_item
from abacus.modules.engagements.work_items import list_work_items
from abacus.modules.identity.api import AuthContext

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
assert abacus.modules.closes.api and abacus.modules.notices.api and abacus.modules.tax.api


@pytest.fixture
async def setup(migrated_db: MigratedDatabase) -> tuple[Seeder, AuthContext, uuid.UUID]:
    configure_engine(migrated_db.app_url)
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = uuid.uuid4()
    await seed.run(
        "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Brightwater Hale LLP')", tenant
    )
    partner = uuid.UUID(
        str(
            await seed.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ('https://probe.test', $1, $2, 'Probe') RETURNING id",
                uuid.uuid4().hex,
                f"{uuid.uuid4().hex}@example.test",
            )
        )
    )
    await seed.run(
        "INSERT INTO memberships (tenant_id, user_id, status) VALUES ($1, $2, 'active')",
        tenant,
        partner,
    )
    client = await seed.value(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Probe client') RETURNING id", tenant
    )
    entity = await seed.value(
        "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, 'Probe') "
        "RETURNING id",
        tenant,
        client,
    )
    engagement = uuid.UUID(
        str(
            await seed.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                "fiscal_period_start, fiscal_period_end, created_by, type, status) "
                "VALUES ($1, $2, $3, 'All kinds', '2026-01-01', '2026-12-31', $4, 'fs_audit', "
                "'active') RETURNING id",
                tenant,
                client,
                entity,
                partner,
            )
        )
    )
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'engagement_partner')",
        tenant,
        engagement,
        partner,
    )
    ctx = AuthContext(
        TenantContext(tenant, "human", str(partner)),
        partner,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )
    return seed, ctx, engagement


async def test_c1_live_lists_all_five_kinds_with_per_status_counts(
    setup: tuple[Seeder, AuthContext, uuid.UUID],
) -> None:
    seed, ctx, engagement = setup
    for kind, details in (
        ("tax_return", {"form": "1120", "tax_year": 2025}),
        ("close", {"period": "2026-08"}),
        ("notice", {"notice_code": "CP2000", "received_on": date(2026, 9, 1)}),
        ("advisory_project", {"name": "Entity review"}),
    ):
        await create_work_item(ctx, engagement, kind, name=f"Probe {kind}", details=details)
    await seed.run(
        "UPDATE work_items SET status = 'archived' WHERE engagement_id = $1 AND kind = 'notice'",
        engagement,
    )
    page = await list_work_items(ctx)
    assert {row.kind for row in page.items} == {
        "assurance",
        "tax_return",
        "close",
        "notice",
        "advisory_project",
    }
    assert page.counts == {"active": 4, "archived": 1}
    assert page.total == 5
    archived = await list_work_items(ctx, status="archived")
    assert [row.kind for row in archived.items] == ["notice"]
    assert archived.counts == {"active": 4, "archived": 1}  # the tile's own filter left out


async def test_c1_live_pages_with_a_cursor(setup: tuple[Seeder, AuthContext, uuid.UUID]) -> None:
    _, ctx, engagement = setup
    for month in range(1, 6):
        await create_work_item(
            ctx,
            engagement,
            "close",
            name=f"2026-{month:02d}",
            details={"period": f"2026-{month:02d}"},
        )
    first = await list_work_items(ctx, kind="close", limit=3)
    assert len(first.items) == 3 and first.next_cursor is not None
    second = await list_work_items(ctx, kind="close", limit=3, cursor=first.next_cursor)
    assert len(second.items) == 2 and second.next_cursor is None
    assert not {r.id for r in first.items} & {r.id for r in second.items}
