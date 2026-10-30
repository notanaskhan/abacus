"""A-03-T05 (TASK-2504; SPEC-580 AC-13 to AC-15; ADR-340) against Postgres: migration 0520.

The row's acceptance: schema_check passes up/down/up with forced RLS, a frozen version refuses
any change but its permitted status moves, and a non-human approval write is refused by the
database. Also: versions are numbered 1, 2, 3 per set and inserted drawing; one approved version
per set; an override needs a rationale and must be below the computed size; strata and items
only while their version is drawing; population records only with their population;
`threshold_policies.kind` accepts `attribute_sample_sizes`. Synthetic values only.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import asyncpg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate

from .support import Migrated, Person, Seeder, Site
from .tb_support import work_item

REVISION = "0520"
_SCRIPTS = ScriptDirectory.from_config(
    Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
)
BEFORE = cast(str, _SCRIPTS.get_revision(REVISION).down_revision)
H = hashlib.sha256(b"probe").hexdigest()

POPULATION = (
    "INSERT INTO sample_populations (tenant_id, engagement_id, work_item_id, source_kind, "
    "evidence_version_id, record_count, record_unit, amount_total, sha256, sampling_unit, "
    "created_by) VALUES ($1, $2, $3, 'upload', $4, 2, 'participants', 300.00, $5, "
    "'participant', $6) RETURNING id"
)
RECORD = (
    "INSERT INTO sample_population_records (tenant_id, population_id, ordinal, record_key, "
    "amount, display) VALUES ($1, $2, $3, $4, 150.00, '{}'::jsonb)"
)
SAMPLE_SET = (
    "INSERT INTO sample_sets (tenant_id, engagement_id, work_item_id, title, created_by) "
    "VALUES ($1, $2, $3, 'Participants', $4) RETURNING id"
)
VERSION = (
    "INSERT INTO sample_set_versions (tenant_id, sample_set_id, version_no, population_id, "
    "method, parameters, computed_size, final_size, seed, seed_source, sampler_version, "
    "inputs_hash, created_by, override_size, override_rationale) VALUES ($1, $2, $3, $4, "
    "'attribute_nonstatistical', '{}'::jsonb, 2, $5, 6171281, 'scenario', '2.3', $6, $7, $8, "
    "$9) RETURNING id"
)
ITEM = (
    "INSERT INTO sample_items (tenant_id, sample_set_version_id, position, "
    "population_record_ordinal, record_key, selection_reason) VALUES ($1, $2, $3, $3, $4, "
    "'random')"
)
STRATUM = (
    "INSERT INTO sample_strata (tenant_id, sample_set_version_id, position, population_count, "
    "population_amount, test_rule, random_count, selected_count) VALUES ($1, $2, 1, 2, 300.00, "
    "'random', 1, 1)"
)
TO_DRAFT = (
    "UPDATE sample_set_versions SET status = 'draft', items_hash = $2, content_hash = $2 "
    "WHERE id = $1"
)
APPROVE = (
    "UPDATE sample_set_versions SET status = 'approved', approved_by = $2, approved_at = now(), "
    "approved_actor_kind = $3 WHERE id = $1"
)
SUPERSEDE = "UPDATE sample_set_versions SET status = 'superseded' WHERE id = $1"
FROZEN = {
    "seed": "UPDATE sample_set_versions SET seed = 1 WHERE id = $1",
    "parameters": "UPDATE sample_set_versions SET parameters = '{\"x\": 1}'::jsonb WHERE id = $1",
    "items_hash": (
        "UPDATE sample_set_versions SET items_hash = "
        "'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' WHERE id = $1"
    ),
    "back_to_draft": "UPDATE sample_set_versions SET status = 'draft' WHERE id = $1",
}


@pytest.fixture
async def app(migrated_db: Migrated) -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(
        migrated_db.app_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        yield conn
    finally:
        await conn.close()


class World:
    def __init__(self, site: Site, marcus: Person, hannah: Person, wid: uuid.UUID) -> None:
        self.site, self.marcus, self.hannah, self.wid = site, marcus, hannah, wid


@pytest.fixture
async def world(seed: Seeder) -> World:
    tenant = await seed.firm()
    marcus = await seed.person(tenant)
    hannah = await seed.person(tenant)
    site = await seed.site(tenant, marcus.user_id, "a03t05")
    return World(site, marcus, hannah, await work_item(seed, site, marcus.user_id))


async def _as(conn: asyncpg.Connection, w: World, who: Person, kind: str = "human") -> None:
    await conn.execute("SELECT set_config('app.tenant_id', $1, false)", str(w.site.tenant_id))
    await conn.execute("SELECT set_config('app.actor_kind', $1, false)", kind)
    await conn.execute("SELECT set_config('app.actor_id', $1, false)", str(who.user_id))


async def _population(app: asyncpg.Connection, w: World) -> uuid.UUID:
    async with app.transaction():
        pid = cast(
            uuid.UUID,
            await app.fetchval(
                POPULATION,
                w.site.tenant_id,
                w.site.engagement_id,
                w.wid,
                w.site.version_id,
                H,
                w.marcus.user_id,
            ),
        )
        for ordinal, key in enumerate(("NW-1", "NW-2")):
            await app.execute(RECORD, w.site.tenant_id, pid, ordinal, key)
    return pid


async def _version(
    app: asyncpg.Connection,
    w: World,
    set_id: uuid.UUID,
    pid: uuid.UUID,
    no: int,
    *,
    override: tuple[int, str] | None = None,
) -> uuid.UUID:
    size = override[0] if override else 2
    return cast(
        uuid.UUID,
        await app.fetchval(
            VERSION,
            w.site.tenant_id,
            set_id,
            no,
            pid,
            size,
            H,
            w.marcus.user_id,
            override[0] if override else None,
            override[1] if override else None,
        ),
    )


async def _drawn(app: asyncpg.Connection, w: World) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """A set with Version 1 drawn to Draft: items written in the draw's transaction."""
    await _as(app, w, w.marcus)
    pid = await _population(app, w)
    set_id = cast(
        uuid.UUID,
        await app.fetchval(
            SAMPLE_SET, w.site.tenant_id, w.site.engagement_id, w.wid, w.marcus.user_id
        ),
    )
    vid = await _version(app, w, set_id, pid, 1)
    async with app.transaction():
        await app.execute(ITEM, w.site.tenant_id, vid, 1, "NW-1")
        await app.execute(ITEM, w.site.tenant_id, vid, 2, "NW-2")
        await app.execute(TO_DRAFT, vid, H)
    return pid, set_id, vid


def test_ac13_the_migration_passes_up_down_up(migrated_db: Migrated) -> None:
    migrate(migrated_db.owner_url, BEFORE, down=True)
    migrate(migrated_db.owner_url, "head")
    migrate(migrated_db.owner_url, BEFORE, down=True)
    migrate(migrated_db.owner_url, "head")
    assert sc.check(migrated_db.owner_url, migrated_db.app_url) == []


async def test_ac13_every_table_forces_row_level_security(seed: Seeder) -> None:
    rows = await seed.rows(
        "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
        "WHERE relname = ANY($1)",
        [
            "sample_populations",
            "sample_population_records",
            "completeness_ties",
            "sample_sets",
            "sample_set_versions",
            "sample_strata",
            "sample_items",
        ],
    )
    assert len(rows) == 7
    assert all(r["relrowsecurity"] and r["relforcerowsecurity"] for r in rows)


async def test_ac14_a_draft_refuses_any_change_but_its_status_moves(
    app: asyncpg.Connection, world: World
) -> None:
    _, _, vid = await _drawn(app, world)
    for statement in FROZEN.values():
        with pytest.raises(asyncpg.PostgresError, match="version_frozen"):
            await app.execute(statement, vid)
    await _as(app, world, world.hannah)
    await app.execute(APPROVE, vid, world.hannah.user_id, "human")
    for statement in (*FROZEN.values(), TO_DRAFT):
        with pytest.raises(asyncpg.PostgresError, match="version_frozen"):
            await app.execute(statement, vid, *([H] if statement == TO_DRAFT else []))
    await app.execute(SUPERSEDE, vid)
    with pytest.raises(asyncpg.PostgresError, match="version_frozen"):
        await app.execute(APPROVE, vid, world.hannah.user_id, "human")


async def test_ac14_a_non_human_approval_is_refused_by_the_database(
    app: asyncpg.Connection, world: World
) -> None:
    _, _, vid = await _drawn(app, world)
    with pytest.raises(asyncpg.CheckViolationError):
        await app.execute(APPROVE, vid, world.hannah.user_id, "agent")
    await _as(app, world, world.hannah, kind="agent")
    with pytest.raises(asyncpg.PostgresError, match="approver_not_human"):
        await app.execute(APPROVE, vid, world.hannah.user_id, "human")
    await _as(app, world, world.hannah, kind="system")
    with pytest.raises(asyncpg.PostgresError, match="approver_not_human"):
        await app.execute(APPROVE, vid, world.hannah.user_id, "human")
    await _as(app, world, world.hannah)
    with pytest.raises(asyncpg.CheckViolationError):
        await app.execute("UPDATE sample_set_versions SET status = 'approved' WHERE id = $1", vid)


async def test_ac14_versions_number_in_order_one_approved_per_set_and_nothing_is_deleted(
    app: asyncpg.Connection, world: World
) -> None:
    pid, set_id, v1 = await _drawn(app, world)
    with pytest.raises(asyncpg.PostgresError, match="version_not_next"):
        await _version(app, world, set_id, pid, 3)
    v2 = await _version(app, world, set_id, pid, 2)
    await app.execute(TO_DRAFT, v2, H)
    await _as(app, world, world.hannah)
    await app.execute(APPROVE, v1, world.hannah.user_id, "human")
    with pytest.raises(asyncpg.UniqueViolationError):
        await app.execute(APPROVE, v2, world.hannah.user_id, "human")
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await app.execute("DELETE FROM sample_set_versions WHERE id = $1", v1)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await app.execute("DELETE FROM sample_items WHERE sample_set_version_id = $1", v1)


async def test_ac14_an_override_needs_a_rationale_and_a_smaller_size(
    app: asyncpg.Connection, world: World
) -> None:
    pid, set_id, _ = await _drawn(app, world)
    with pytest.raises(asyncpg.CheckViolationError):
        await app.execute(
            VERSION,
            world.site.tenant_id,
            set_id,
            2,
            pid,
            1,
            H,
            world.marcus.user_id,
            1,
            None,
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await _version(app, world, set_id, pid, 2, override=(3, "above the size"))
    await _version(app, world, set_id, pid, 2, override=(1, "Below methodology, agreed"))


async def test_ac14_items_and_strata_only_while_drawing_and_records_only_with_the_population(
    app: asyncpg.Connection, world: World
) -> None:
    pid, _, vid = await _drawn(app, world)
    with pytest.raises(asyncpg.PostgresError, match="version_frozen"):
        await app.execute(ITEM, world.site.tenant_id, vid, 3, "NW-3")
    with pytest.raises(asyncpg.PostgresError, match="version_frozen"):
        await app.execute(STRATUM, world.site.tenant_id, vid)
    with pytest.raises(asyncpg.PostgresError, match="only be added with their population"):
        await app.execute(RECORD, world.site.tenant_id, pid, 9, "NW-9")


async def test_ac15_threshold_policies_accept_attribute_sample_sizes(
    app: asyncpg.Connection, world: World
) -> None:
    await _as(app, world, world.marcus)
    policy = await app.fetchval(
        "INSERT INTO threshold_policies (tenant_id, kind, key, name, owner_id, created_by) "
        "VALUES ($1, 'attribute_sample_sizes', $2, 'Probe sizes', $3, $3) RETURNING id",
        world.site.tenant_id,
        f"probe-{uuid.uuid4().hex[:8]}",
        world.marcus.user_id,
    )
    assert policy is not None
