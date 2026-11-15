"""A-09-T05 (TASK-8055; SPEC-658 AC-0.4, AC-1.1, AC-1.3; DEC-5040): migration 0889.

The database itself refuses a fourth tier, ownership other than 100%, a currency other than USD,
an entity outside the engagement, a parent on the wrong level, a non-human finalize, and any
change to the structure once the consolidation is finalized; events are insert-only and a reopen
carries its reason. Seeded as the superuser (RLS is covered by the generated isolation suite).
"""

from __future__ import annotations

import uuid
from typing import cast

import asyncpg
import pytest
from tests.integration.conftest import MigratedDatabase
from tests.security.support import Seeder


async def _setup(
    seed: Seeder,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, list[uuid.UUID], uuid.UUID]:
    tenant = await seed.firm()
    who = await seed.person(tenant)
    site = await seed.site(tenant, who.user_id, "harlow-pike")
    # One assurance work item per engagement (0068): the site's own, else a new one.
    found = await seed.value(
        "SELECT id FROM work_items WHERE tenant_id = $1 AND engagement_id = $2 "
        "AND kind = 'assurance'",
        tenant,
        site.engagement_id,
    )
    work_item = cast(
        uuid.UUID,
        found
        or await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
            "VALUES ($1, $2, $3, 'assurance', 'FY2026 group audit', $4) RETURNING id",
            tenant,
            site.engagement_id,
            site.client_id,
            who.user_id,
        ),
    )
    entities = [site.entity_id]
    for n in range(4):
        entity = cast(
            uuid.UUID,
            await seed.value(
                "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
                "RETURNING id",
                tenant,
                site.client_id,
                f"Component {n}",
            ),
        )
        await seed.run(
            "INSERT INTO engagement_entities (tenant_id, engagement_id, client_entity_id, role) "
            "VALUES ($1, $2, $3, 'component')",
            tenant,
            site.engagement_id,
            entity,
        )
        entities.append(entity)
    consolidation = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO consolidations (tenant_id, engagement_id, work_item_id, name, year_end, "
            "reporting_currency, created_by) VALUES ($1, $2, $3, 'FY2026 group consolidation', "
            "'2026-12-31', 'USD', $4) RETURNING id",
            tenant,
            site.engagement_id,
            work_item,
            who.user_id,
        ),
    )
    return tenant, consolidation, site.engagement_id, entities, who.user_id


async def _entity(
    seed: Seeder,
    tenant: uuid.UUID,
    consolidation: uuid.UUID,
    entity: uuid.UUID,
    level: int,
    parent: uuid.UUID | None,
    ownership: int = 100,
) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO consolidation_entities (tenant_id, consolidation_id, client_entity_id, "
            "parent_id, level, ownership_pct) VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
            tenant,
            consolidation,
            entity,
            parent,
            level,
            ownership,
        ),
    )


async def test_ac0_4_three_tiers_at_full_ownership_and_never_a_fourth(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant, cid, _eng, entities, _who = await _setup(seed)
    root = await _entity(seed, tenant, cid, entities[0], 1, None)
    mid = await _entity(seed, tenant, cid, entities[1], 2, root)
    leaf = await _entity(seed, tenant, cid, entities[2], 3, mid)
    with pytest.raises(asyncpg.CheckViolationError):
        await _entity(seed, tenant, cid, entities[3], 4, leaf)  # a fourth tier
    with pytest.raises(asyncpg.CheckViolationError):
        await _entity(seed, tenant, cid, entities[3], 2, root, ownership=80)  # NCI (X-06)
    with pytest.raises(asyncpg.CheckViolationError):
        await _entity(seed, tenant, cid, entities[3], 3, root)  # the parent is not one level up


async def test_ac1_1_usd_only_and_the_engagements_entities_only(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant, cid, _eng, _entities, _who = await _setup(seed)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run("UPDATE consolidations SET reporting_currency = 'CAD' WHERE id = $1", cid)
    stranger = await seed.value(
        "INSERT INTO client_entities (tenant_id, client_id, name) SELECT tenant_id, client_id, "
        "'Stranger' FROM client_entities WHERE tenant_id = $1 LIMIT 1 RETURNING id",
        tenant,
    )
    with pytest.raises(asyncpg.CheckViolationError):
        await _entity(seed, tenant, cid, cast(uuid.UUID, stranger), 1, None)


async def test_ac1_3_a_finalized_structure_is_frozen_and_finalize_is_a_persons(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant, cid, _eng, entities, who = await _setup(seed)
    root = await _entity(seed, tenant, cid, entities[0], 1, None)
    await _entity(seed, tenant, cid, entities[1], 2, root)
    with pytest.raises(asyncpg.CheckViolationError):  # finalized without a person
        await seed.run("UPDATE consolidations SET status = 'finalized' WHERE id = $1", cid)
    await seed.run(
        "UPDATE consolidations SET status = 'finalized', finalized_by = $2, "
        "finalized_at = now(), finalized_actor_kind = 'human' WHERE id = $1",
        cid,
        who,
    )
    with pytest.raises(asyncpg.CheckViolationError):
        await _entity(seed, tenant, cid, entities[2], 2, root)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run("UPDATE consolidation_entities SET city = 'Denver' WHERE id = $1", root)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run("DELETE FROM consolidation_entities WHERE id = $1", root)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run("UPDATE consolidations SET status = 'draft' WHERE id = $1", cid)


async def test_events_are_a_persons_and_a_reopen_has_its_reason(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant, cid, _eng, _entities, who = await _setup(seed)
    insert = (
        "INSERT INTO consolidation_events (tenant_id, consolidation_id, kind, reason, "
        "actor_kind, actor_id) VALUES ($1, $2, $3, $4, $5, $6)"
    )
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(insert, tenant, cid, "finalized", None, "agent", who)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(insert, tenant, cid, "reopened", None, "human", who)
    await seed.run(insert, tenant, cid, "reopened", "Distribution re-pulled", "human", who)


async def test_the_app_role_may_not_update_or_delete_events(migrated_db: MigratedDatabase) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    grants = await seed.rows(
        "SELECT privilege_type FROM information_schema.role_table_grants "
        "WHERE grantee = 'abacus_app' AND table_name = 'consolidation_events'"
    )
    assert {g["privilege_type"] for g in grants} >= {"SELECT"}
    assert not {g["privilege_type"] for g in grants} & {"UPDATE", "DELETE", "TRUNCATE"}
    # INSERT is granted column by column (`insert_columns`), never UPDATE on any column.
    columns = await seed.rows(
        "SELECT DISTINCT privilege_type FROM information_schema.column_privileges "
        "WHERE grantee = 'abacus_app' AND table_name = 'consolidation_events'"
    )
    kinds = {c["privilege_type"] for c in columns}
    assert "INSERT" in kinds and "UPDATE" not in kinds
