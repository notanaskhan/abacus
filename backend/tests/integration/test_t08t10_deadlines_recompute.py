"""T-08-T10's recompute and read (S51 partials, TASK-8741; DEC-5732; SPEC-710 AC-9, AC-14) on the
migrated database: a return with a due date becomes one deadline row; a second recompute with the
same inputs writes nothing; an extension moves the due date; a walled reader sees no row."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date
from typing import cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, configure_relay_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.practice import deadlines_service as svc

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_t08t09_season_service import admin_of, as_admin, client_with_return

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    configure_relay_engine(migrated_db.relay_url)
    yield
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


async def test_ac_recompute_is_idempotent_and_reads_are_walled(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    office = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO offices (tenant_id, name, time_zone) VALUES ($1, 'Chicago', "
            "'America/Chicago') RETURNING id",
            tenant,
        ),
    )
    partner = await seed.person(tenant)
    feld = await client_with_return(seed, tenant, partner, "Feld", office, "1040")
    await seed.run(
        "UPDATE tax_returns SET original_due_on = '2026-04-15' WHERE tenant_id = $1", tenant
    )
    assert await svc.recompute(tenant) == 1
    assert await svc.recompute(tenant) == 0  # same inputs: nothing written
    admin = await admin_of(seed, tenant)
    found = await svc.rows(as_admin(admin), date(2026, 4, 1), date(2026, 4, 30))
    assert [(r.filing_label, r.due_on, r.signer_user_id) for r in found] == [
        ("Form 1040 · 2025", date(2026, 4, 15), partner.user_id)
    ]

    await seed.run(
        "UPDATE tax_returns SET extended = true, extended_due_on = '2026-10-15' "
        "WHERE tenant_id = $1",
        tenant,
    )
    assert await svc.recompute(tenant) == 1
    moved = await svc.rows(as_admin(admin), date(2026, 10, 1), date(2026, 10, 31))
    assert [(r.due_on, r.extension_form) for r in moved] == [(date(2026, 10, 15), "4868")]

    walled = await admin_of(seed, tenant)
    await seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        tenant,
        walled.user_id,
        feld,
        partner.user_id,
    )
    assert await svc.rows(as_admin(walled), date(2026, 1, 1), date(2026, 12, 31)) == []
