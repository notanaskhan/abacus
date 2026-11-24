"""K-03-T12 (TASK-8902; SPEC-720 §4; K-03 §4.2): migration 1011, links, rollouts and updates.

"Every engagement with a pinned methodology version has one link in state current, the legacy
column is untouched, a Hold or On rollover action without a reason is refused by CHECK, and the
migration is expand-only" (the row's acceptance).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from pathlib import Path

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Person, Seeder

BEFORE = "1010"
NEW_TABLES = (
    "engagement_template_links",
    "template_link_events",
    "template_rollouts",
    "template_rollout_actions",
    "template_updates",
    "template_update_changes",
    "scoping_evaluations",
)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _pinned(seed: Seeder) -> tuple[uuid.UUID, Person, uuid.UUID, uuid.UUID, uuid.UUID]:
    """A firm, a published methodology version, one engagement pinned to it and one not."""
    tenant = await seed.firm()
    person = await seed.person(tenant)
    template, version = uuid.uuid4(), uuid.uuid4()
    await seed.run(
        "INSERT INTO methodology_templates (id, tenant_id, name, created_by, engagement_types) "
        "VALUES ($1, $2, 'BH Audit Methodology · FS', $3, '{fs_audit}')",
        template,
        tenant,
        person.user_id,
    )
    await seed.run(
        "INSERT INTO methodology_versions (id, tenant_id, template_id, version, "
        "source_fingerprint, imported_by, label) VALUES ($1, $2, $3, 5, $4, $5, 'FS v5')",
        version,
        tenant,
        template,
        "5" * 64,
        person.user_id,
    )
    await seed.run(
        "INSERT INTO methodology_version_states (tenant_id, version_id, template_id, status, "
        "effective_from, approval_basis) VALUES ($1, $2, $3, 'published', DATE '2026-07-01', "
        "'legacy_import')",
        tenant,
        version,
        template,
    )
    entity = await seed.entity(tenant)
    pinned = await seed.engagement(tenant, entity, person.user_id)
    unpinned = await seed.engagement(tenant, entity, person.user_id)
    await seed.run(
        "UPDATE engagements SET methodology_version_id = $2 WHERE id = $1", pinned, version
    )
    await seed.run("UPDATE engagements SET methodology_version_id = NULL WHERE id = $1", unpinned)
    return tenant, person, version, pinned, unpinned


def test_ac_every_pinned_engagement_has_one_current_link_and_up_down_up(
    private_db: sc.Database,
) -> None:
    seed = Seeder(private_db.superuser_dsn)
    migrate(private_db.owner_url, "1003", down=True)
    tenant, _, version, pinned, unpinned = asyncio.run(_pinned(seed))
    migrate(private_db.owner_url, "head")

    async def links() -> None:
        rows = await seed.rows(
            "SELECT l.engagement_id, l.state, tv.methodology_version_id, tv.label "
            "FROM engagement_template_links l JOIN template_versions tv "
            "ON tv.id = l.template_version_id WHERE l.tenant_id = $1",
            tenant,
        )
        assert [(r["engagement_id"], r["state"], r["methodology_version_id"]) for r in rows] == [
            (pinned, "current", version)
        ]
        assert unpinned not in {r["engagement_id"] for r in rows}
        events = await seed.rows(
            "SELECT kind, actor_kind FROM template_link_events WHERE engagement_id = $1", pinned
        )
        assert [(e["kind"], e["actor_kind"]) for e in events] == [("pinned", "system")]
        legacy = await seed.value(
            "SELECT methodology_version_id FROM engagements WHERE id = $1", pinned
        )
        assert legacy == version  # the legacy column is untouched

    asyncio.run(links())
    migrate(private_db.owner_url, BEFORE, down=True)
    for table in NEW_TABLES:
        assert asyncio.run(seed.value("SELECT to_regclass($1) IS NULL", table)), table
    assert asyncio.run(
        seed.value(
            "SELECT count(*) = 0 FROM information_schema.columns WHERE table_name = "
            "'request_items' AND column_name = 'shown_by_rule_id'"
        )
    )
    migrate(private_db.owner_url, "head")
    asyncio.run(links())
    assert sc.check(private_db.owner_url, private_db.app_url) == []


def test_ac_the_migration_is_expand_only() -> None:
    """No existing column is dropped, renamed or retyped: the upgrade only creates tables and
    adds one nullable column."""
    source = (
        Path(__file__).resolve().parents[2] / "migrations/versions/1011_template_links_rollouts.py"
    ).read_text(encoding="utf-8")
    upgrade = source.split("def upgrade() -> None:")[1].split("def downgrade() -> None:")[0]
    for forbidden in ("DROP COLUMN", "RENAME", "ALTER COLUMN", "DROP TABLE", "DROP CONSTRAINT"):
        assert forbidden not in upgrade, forbidden
    assert "ADD COLUMN shown_by_rule_id uuid NULL" in upgrade


def test_ac_a_hold_or_on_rollover_without_a_reason_is_refused(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)
    app = Seeder(_dsn(private_db.app_url))
    migrate(private_db.owner_url, "1003", down=True)
    tenant, person, version, pinned, _ = asyncio.run(_pinned(seed))
    migrate(private_db.owner_url, "head")
    actor = ("human", str(person.user_id))

    async def actions() -> None:
        template = await seed.value(
            "SELECT template_id FROM template_versions WHERE methodology_version_id = $1", version
        )
        from_version = await seed.value(
            "SELECT id FROM template_versions WHERE methodology_version_id = $1", version
        )
        to_version = uuid.uuid4()
        await seed.run(
            "INSERT INTO template_versions (id, tenant_id, template_id, seq, label, status, "
            "effective_from, fingerprint, published_by, published_at, created_by) VALUES "
            "($1, $2, $3, 9, 'FS v6', 'published', DATE '2026-10-01', $4, $5, now(), $5)",
            to_version,
            tenant,
            template,
            "6" * 64,
            person.user_id,
        )
        rollout, action = uuid.uuid4(), uuid.uuid4()
        await app.as_actor(
            tenant,
            actor,
            "INSERT INTO template_rollouts (id, tenant_id, template_id, from_version_id, "
            "to_version_id, created_by) VALUES ($1, $2, $3, $4, $5, $6)",
            rollout,
            tenant,
            template,
            from_version,
            to_version,
            person.user_id,
        )
        await app.as_actor(
            tenant,
            actor,
            "INSERT INTO template_rollout_actions (id, tenant_id, rollout_id, engagement_id, "
            "suggested_action) VALUES ($1, $2, $3, $4, 'update_now')",
            action,
            tenant,
            rollout,
            pinned,
        )
        for choice in ("hold", "on_rollover"):
            with pytest.raises(asyncpg.CheckViolationError):
                await app.as_actor(
                    tenant,
                    actor,
                    "UPDATE template_rollout_actions SET action = $2, set_by = $3, "
                    "set_at = now() WHERE id = $1",
                    action,
                    choice,
                    person.user_id,
                )
        await app.as_actor(
            tenant,
            actor,
            "UPDATE template_rollout_actions SET action = 'hold', reason = 'Fieldwork is "
            "under way; apply at rollover', set_by = $2, set_at = now() WHERE id = $1",
            action,
            person.user_id,
        )
        await app.as_actor(
            tenant,
            actor,
            "UPDATE template_rollout_actions SET action = 'update_now', reason = NULL, "
            "set_by = $2, set_at = now() WHERE id = $1",
            action,
            person.user_id,
        )
        # A held link needs its reason and person; events are insert-only.
        link = await seed.value(
            "SELECT id FROM engagement_template_links WHERE engagement_id = $1", pinned
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await app.as_actor(
                tenant,
                actor,
                "UPDATE engagement_template_links SET state = 'held' WHERE id = $1",
                link,
            )
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app.as_actor(
                tenant, actor, "DELETE FROM template_link_events WHERE link_id = $1", link
            )

    asyncio.run(actions())
