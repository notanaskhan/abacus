"""T-08-T09's persistence (S51 partials, TASK-8737; DEC-5729; SPEC-710 AC-1 to AC-3, AC-7) on the
migrated database: the season is built from the prior year's returns into cohorts by office and
segment with rows that carry the prior team; a walled reader sees no row and no count; a walled
or inactive person is not an eligible assignee; an excluded row leaves the tallies; a rebuild is
refused once a cohort is approved."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, configure_relay_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.engagements import season_service as svc
from abacus.modules.identity.api import AuthContext
from abacus.modules.tax import api as tax_api

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

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


def as_admin(who: Person) -> AuthContext:
    return replace(who.context(), firm_role="firm_admin")


async def admin_of(seed: Seeder, tenant: uuid.UUID) -> Person:
    who = await seed.person(tenant)
    await seed.run(
        "UPDATE memberships SET firm_role = 'firm_admin' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        who.user_id,
    )
    return who


async def client_with_return(
    seed: Seeder, tenant: uuid.UUID, partner: Person, name: str, office: uuid.UUID, form: str
) -> uuid.UUID:
    client = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id", tenant, name
        ),
    )
    entity = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) "
            "RETURNING id",
            tenant,
            client,
            name,
        ),
    )
    engagement = await seed.engagement(tenant, entity, partner.user_id)
    await seed.member(engagement, partner, "engagement_partner")
    await seed.run("UPDATE engagements SET office_id = $2 WHERE id = $1", engagement, office)
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, period_start, period_end, office_id, created_by) VALUES ($1, $2, $3, $4, "
            "'tax_return', '2025 return', '2025-01-01', '2025-12-31', $5, $6) RETURNING id",
            tenant,
            engagement,
            client,
            entity,
            office,
            partner.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, form, "
        "tax_year) VALUES ($1, $2, $3, $4, $5, 2025)",
        tenant,
        item,
        engagement,
        entity,
        form,
    )
    return client


async def test_ac_the_season_builds_reads_and_guards_its_rows(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    offices = {
        n: cast(
            uuid.UUID,
            await seed.value(
                "INSERT INTO offices (tenant_id, name, time_zone) VALUES ($1, $2, "
                "'America/Chicago') RETURNING id",
                tenant,
                n,
            ),
        )
        for n in ("Chicago", "Denver")
    }
    partner = await seed.person(tenant)
    assert tax_api.register_season_candidates is not None  # tax's import registers the source
    admin = await admin_of(seed, tenant)
    abbott = await client_with_return(seed, tenant, partner, "Abbott", offices["Chicago"], "1040")
    baker = await client_with_return(
        seed, tenant, partner, "Baker Logistics", offices["Denver"], "1065"
    )

    made = await svc.build_manifest(as_admin(admin), 2026)
    again = await svc.build_manifest(as_admin(admin), 2026)
    assert again == made  # the ready manifest, not a second version
    view = await svc.manifest(as_admin(admin), 2026, made)
    assert [(c.office_name, c.segment, c.engagements) for c in view.cohorts] == [
        ("Chicago", "individuals_trusts", 1),
        ("Denver", "entities_exempt", 1),
    ]
    rows = {r.client_id: r for c in view.cohorts for r in c.rows}
    assert rows[abbott].signer_user_id == partner.user_id and rows[abbott].display == "ready"

    walled = await admin_of(seed, tenant)
    await seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        tenant,
        walled.user_id,
        baker,
        partner.user_id,
    )
    theirs = await svc.manifest(as_admin(walled), 2026, made)
    assert sum(c.engagements for c in theirs.cohorts) == 1  # no row, no count
    with pytest.raises(svc.AssigneeNotEligible):
        await svc.reassign(
            as_admin(admin), rows[baker].row_id, rows[baker].row_version, preparer=walled.user_id
        )

    excluded = await svc.exclude(as_admin(admin), [rows[abbott].row_id], "not_continuing")
    assert excluded == 1
    after = await svc.manifest(as_admin(admin), 2026, made)
    assert sum(c.engagements for c in after.cohorts) == 1

    await seed.run(
        "UPDATE season_cohorts SET status = 'approved' WHERE manifest_id = $1 AND position = 2",
        made,
    )
    with pytest.raises(svc.CohortApproved):
        await svc.build_manifest(as_admin(admin), 2026, rebuild=True)
    with pytest.raises(svc.CohortApproved):
        await svc.exclude(as_admin(admin), [rows[baker].row_id], "duplicate")
