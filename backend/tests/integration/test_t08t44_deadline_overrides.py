"""T-08-T44 on the migrated database (TASK-8919; T-08 AC2.13; DF-10; DEC-5921): a firm publishes
its `deadline_overrides` (owner-published, versioned) with a 14-day internal target for Form 1065
and an Illinois relief notice; a firm admin applies the notice to one client; the recompute moves
only that client's Form 1065 from Tue Sep 15 to Mon Nov 16, 2026 (the struck original kept), the
other client's stays statutory, both carry the internal target, and the dates pin the overrides
version. The platform's reference sets are untouched."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import AsyncIterator
from datetime import date
from typing import cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, configure_relay_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.practice import deadline_overrides as df10
from abacus.modules.practice import deadlines_service as svc

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_t08t09_season_service import admin_of, as_admin, client_with_return

pytestmark = pytest.mark.asyncio

PAYLOAD: dict[str, object] = {
    "kind": "deadline_overrides",
    "offsets": [{"form": "1065", "internal_offset_days": 14}],
    "closures": [],
    "postponements": [
        {"notice_id": "IL-2026-03", "title": "Illinois storm relief", "areas": [],
         "window_start": "2026-08-01", "window_end": "2026-10-31", "postponed_to": "2026-11-16"}
    ],
}  # fmt: skip


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


async def _publish_overrides(seed: Seeder, tenant: uuid.UUID, owner: uuid.UUID) -> uuid.UUID:
    body = json.dumps(PAYLOAD, sort_keys=True)
    digest = "sha256:" + hashlib.sha256(body.encode()).hexdigest()
    parent = await seed.value(
        "INSERT INTO firm_standards (tenant_id, kind, key, name, owner_id, created_by) VALUES "
        "($1, 'deadline_overrides', 'bh-deadline-overrides', 'Deadline overrides', $2, $2) "
        "RETURNING id",
        tenant, owner,
    )  # fmt: skip
    version = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO firm_standard_versions (tenant_id, parent_id, version, payload, "
            "payload_hash, drafted_by) VALUES ($1, $2, 1, $3::jsonb, $4, $5) RETURNING id",
            tenant, parent, body, digest, owner,
        ),
    )  # fmt: skip
    async with seed.held() as conn:
        await conn.execute("SELECT set_config('app.actor_kind', 'human', false)")
        await conn.execute(
            "UPDATE firm_standard_versions SET status = 'published', effective_from = "
            "'2026-01-01', published_by = $2, published_actor_kind = 'human', "
            "published_at = now() WHERE id = $1",
            version, owner,
        )  # fmt: skip
    return version


async def test_ac213_a_notice_applied_by_id_moves_only_that_clients_dates(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
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
    admin = await admin_of(seed, tenant)
    ridgeline = await client_with_return(seed, tenant, partner, "Ridgeline", office, "1065")
    bramble = await client_with_return(seed, tenant, partner, "Bramble & Finch", office, "1065")
    await seed.run(
        "UPDATE tax_returns SET original_due_on = '2026-09-15', extended = true, "
        "extended_due_on = '2026-09-15' WHERE tenant_id = $1",
        tenant,
    )
    version = await _publish_overrides(seed, tenant, partner.user_id)
    monkeypatch.setattr(svc.calc, "firm_today", _firm_today)

    found = await df10.apply_postponement(as_admin(admin), ridgeline, "IL-2026-03", version)
    assert found.client_id == ridgeline and found.moved >= 1
    again = await df10.apply_postponement(as_admin(admin), ridgeline, "IL-2026-03", version)
    assert again.application_id == found.application_id  # the first answers
    with pytest.raises(df10.PostponementNoticeUnknown):
        await df10.apply_postponement(as_admin(admin), bramble, "IL-2026-99", version)

    await svc.recompute(tenant)
    rows = {
        r.client_id: r
        for r in await svc.rows(as_admin(admin), date(2026, 1, 1), date(2027, 12, 31))
        if r.source_kind == "tax_return"
    }
    assert rows[ridgeline].due_on == date(2026, 11, 16)
    assert rows[ridgeline].postponed_from == date(2026, 9, 15)
    assert rows[ridgeline].internal_target_on == date(2026, 11, 2)
    assert rows[bramble].due_on == date(2026, 9, 15) and rows[bramble].postponed_from is None
    assert rows[bramble].internal_target_on == date(2026, 9, 1)
    assert version in rows[ridgeline].reference_set_version_ids
    events = await seed.rows(
        "SELECT actor_kind FROM postponement_applications WHERE tenant_id = $1", tenant
    )
    assert [e["actor_kind"] for e in events] == ["human"]


def _firm_today(*_args: object) -> date:
    return date(2026, 9, 10)
