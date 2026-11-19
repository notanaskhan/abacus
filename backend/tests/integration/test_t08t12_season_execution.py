"""T-08-T12's approval and execution (S51 partials, TASK-8739; DEC-5730; SPEC-710 AC-5, AC-6) on
the migrated database: a partner approves the cohort they saw (one insert-only approval and a
single-use grant); the execution consumes the grant and creates the engagement and its team once
(a re-run creates nothing more); steps without an owner's executor fail as `step_unavailable`;
withdrawal after a step ran answers `execution_started`; a firm admin may not approve."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, configure_relay_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.engagements import season_execution_service as ex
from abacus.modules.engagements import season_service as svc
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.tax import api as tax_api

from .agent_tests.support import Person, Seeder
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

    async def no_dispatch(*_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(ex, "dispatch", no_dispatch)  # the workflow is the activity, run below
    yield
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


async def _partner(seed: Seeder, tenant: uuid.UUID) -> AuthContext:
    who: Person = await seed.person(tenant)
    await seed.run(
        "UPDATE memberships SET level = 'partner' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        who.user_id,
    )
    return who.context()


async def test_ac_approve_execute_once_and_withdraw_refused(migrated_db: MigratedDatabase) -> None:
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
    signer = await seed.person(tenant)
    assert tax_api.register_season_candidates is not None
    admin = await admin_of(seed, tenant)
    await client_with_return(seed, tenant, signer, "Abbott", office, "1040")
    manifest = await svc.build_manifest(as_admin(admin), 2026)
    view = await svc.manifest(as_admin(admin), 2026, manifest)
    cohort = view.cohorts[0]

    with pytest.raises(Forbidden):
        await ex.approve_cohort(
            as_admin(admin), cohort.cohort_id, rows_hash=cohort.rows_hash, manifest_version=1
        )
    partner = await _partner(seed, tenant)
    with pytest.raises(svc.StaleRow):
        await ex.approve_cohort(partner, cohort.cohort_id, rows_hash="0" * 64, manifest_version=1)
    made = await ex.approve_cohort(
        partner, cohort.cohort_id, rows_hash=cohort.rows_hash, manifest_version=1
    )
    approvals = await seed.value(
        "SELECT count(*) FROM season_cohort_approvals WHERE cohort_id = $1", cohort.cohort_id
    )
    assert approvals == 1 and made.grant_id is not None

    first = await ex.execute_cohort(tenant, cohort.cohort_id)
    again = await ex.execute_cohort(tenant, cohort.cohort_id)
    assert (first, again) == ("failed", "failed")  # returns onward have no executor yet
    steps = await seed.rows(
        "SELECT step, status, error_code FROM season_row_steps ORDER BY step, attempt"
    )
    ok = {r["step"] for r in steps if r["status"] == "ok"}
    assert ok == {"engagement"}
    assert {r["error_code"] for r in steps if r["status"] == "failed"} == {"step_unavailable"}
    created = await seed.value(
        "SELECT count(*) FROM engagements WHERE tenant_id = $1 AND type = 'tax_compliance' "
        "AND name = '2025 tax returns'",
        tenant,
    )
    assert created == 1  # the re-run created nothing more

    with pytest.raises(ex.ExecutionStarted):
        await ex.withdraw_cohort(replace(partner), cohort.cohort_id, "client left")
