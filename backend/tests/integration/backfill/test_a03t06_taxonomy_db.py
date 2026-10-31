"""A-03-T06 (TASK-2506; SPEC-580 AC-17) against Postgres: migration 0521 and the taxonomy service.

Publishing needs a person's session and sets the effective date; a re-import discards the set's
earlier draft and a discarded version never changes or publishes; the picker's Recently used is
the person's own. Synthetic probe content only (AGENTS 16).
"""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from typing import cast

import asyncpg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.ledger.api import (
    VersionNotDraft,
    grouping_set_versions,
    import_grouping_set,
    publish_version,
)
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate

from .support import Migrated, Seeder

REVISION = "0521"
_SCRIPTS = ScriptDirectory.from_config(
    Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
)
BEFORE = cast(str, _SCRIPTS.get_revision(REVISION).down_revision)
CSV = (
    "grouping_key,grouping_label,class,fs_line_key,fs_line_label,normal_balance,"
    "account_from,account_to\n"
    "cash,Cash,assets,cash,Operating cash,debit,1000,1099\n"
)


async def _import(tenant: TenantContext, tenant_id: uuid.UUID, user: uuid.UUID) -> uuid.UUID:
    async with uow(tenant) as tx:
        return await import_grouping_set(
            tx, tenant_id=tenant_id, key="probe-set", name="Probe set", text=CSV, user_id=user
        )


def test_the_migration_passes_up_down_up(migrated_db: Migrated) -> None:
    migrate(migrated_db.owner_url, BEFORE, down=True)
    migrate(migrated_db.owner_url, "head")
    migrate(migrated_db.owner_url, BEFORE, down=True)
    migrate(migrated_db.owner_url, "head")
    assert sc.check(migrated_db.owner_url, migrated_db.app_url) == []


async def test_ac17_a_reimport_discards_the_earlier_draft_and_publish_needs_a_person(
    seed: Seeder,
) -> None:
    tenant_id = await seed.firm()
    margaret = await seed.person(tenant_id, "quality_partner")
    person = TenantContext(tenant_id, "human", str(margaret.user_id))
    first = await _import(person, tenant_id, margaret.user_id)
    second = await _import(person, tenant_id, margaret.user_id)
    statuses = {v.id: v.status for v in await grouping_set_versions(person)}
    assert statuses == {first: "discarded", second: "draft"}

    with pytest.raises(VersionNotDraft):
        async with uow(person) as tx:
            await publish_version(
                tx,
                version_id=first,
                user_id=margaret.user_id,
                actor_kind="human",
                effective_from=date(2026, 10, 1),
            )

    agent = TenantContext(tenant_id, "agent", str(margaret.user_id))
    with pytest.raises(Exception, match="publisher_not_human"):
        async with uow(agent) as tx:
            await publish_version(
                tx,
                version_id=second,
                user_id=margaret.user_id,
                actor_kind="human",
                effective_from=date(2026, 10, 1),
            )

    async with uow(person) as tx:
        await publish_version(
            tx,
            version_id=second,
            user_id=margaret.user_id,
            actor_kind="human",
            effective_from=date(2026, 10, 1),
        )
    published = {v.id: v for v in await grouping_set_versions(person)}[second]
    assert (published.status, published.effective_from) == ("published", date(2026, 10, 1))


async def test_ac17_a_discarded_version_never_changes(seed: Seeder, migrated_db: Migrated) -> None:
    tenant_id = await seed.firm()
    margaret = await seed.person(tenant_id, "quality_partner")
    person = TenantContext(tenant_id, "human", str(margaret.user_id))
    first = await _import(person, tenant_id, margaret.user_id)
    await _import(person, tenant_id, margaret.user_id)
    conn = await asyncpg.connect(
        migrated_db.app_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        await conn.execute("SELECT set_config('app.tenant_id', $1, false)", str(tenant_id))
        await conn.execute("SELECT set_config('app.actor_kind', 'human', false)")
        with pytest.raises(asyncpg.PostgresError, match="version_frozen"):
            await conn.execute(
                "UPDATE grouping_set_versions SET status = 'draft' WHERE id = $1", first
            )
    finally:
        await conn.close()
