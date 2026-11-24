"""T-08-T20's providers on the migrated database (TASK-8915; SPEC-710 AC-12; FD-1; HOME-03;
DEC-5917): the Thornbury estate's Form 706, with no dates stored on the return, is recomputed
from its estate profile to Nov 2, 2026 with Form 4768 to May 3, 2027 and its Form 8971 to Dec 2,
2026; and with `practice.filing_deadlines` on, HOME-01's pane for the partner shows the same rows
HOME-03 reads."""

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
from abacus.modules.practice import home
from abacus.modules.tax import api as tax_api

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
assert tax_api  # registers tax's providers


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


async def test_ac12_thornbury_706_and_home_01_equals_home_03(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    client = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Estate of Margaret Thornbury') "
            "RETURNING id",
            tenant,
        ),
    )
    entity = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name, entity_type) VALUES ($1, "
            "$2, 'Estate of Margaret Thornbury', 'estate') RETURNING id",
            tenant,
            client,
        ),
    )
    await seed.run(
        "INSERT INTO estate_profiles (client_entity_id, tenant_id, date_of_death, created_by) "
        "VALUES ($1, $2, '2026-02-02', $3)",
        entity,
        tenant,
        partner.user_id,
    )
    engagement = await seed.engagement(tenant, entity, partner.user_id)
    await seed.member(engagement, partner, "engagement_partner")
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, period_start, period_end, created_by) VALUES ($1, $2, $3, $4, 'tax_return', "
            "'Form 706', '2026-01-01', '2026-12-31', $5) RETURNING id",
            tenant,
            engagement,
            client,
            entity,
            partner.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, form, "
        "tax_year) VALUES ($1, $2, $3, $4, '706', 2026)",
        tenant,
        item,
        engagement,
        entity,
    )
    # The recompute asks from the season before: pin the firm's today to Oct 30, 2026.
    monkeypatch.setattr(svc.calc, "firm_today", _firm_today)
    assert await svc.recompute(tenant) >= 2
    assert await svc.recompute(tenant) == 0  # same inputs: nothing written

    ctx = partner.context()
    found = await svc.rows(ctx, date(2026, 1, 1), date(2027, 12, 31))
    by_label = {r.filing_label: r for r in found}
    assert by_label["Form 706 · 2026"].due_on == date(2026, 11, 2)
    assert by_label["Form 706 · 2026"].extension_form == "4768"
    assert by_label["Form 706 · 2026"].extended_due_on == date(2027, 5, 3)
    assert by_label["Form 8971 · 2026"].due_on == date(2026, 12, 2)
    assert by_label["Form 706 · 2026"].signer_user_id == partner.user_id

    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'practice.filing_deadlines', 'true', 't08', 'TASK-8915')",
        tenant,
    )
    forget_flags()
    monkeypatch.setattr(home.clock, "today", _today)
    view = await home.home_view(ctx, None)
    pane = [(d.due_on, d.filing_label) for d in view.deadlines]
    assert (date(2026, 11, 2), "Form 706 · 2026") in pane
    assert view.next_deadline is not None
    home_03 = {(r.due_on, r.filing_label) for r in found if not r.done}
    assert set(pane) | {(view.next_deadline.due_on, view.next_deadline.filing_label)} <= home_03


async def _today(*_args: object, **_kwargs: object) -> date:
    return date(2026, 10, 30)


def _firm_today(*_args: object) -> date:
    return date(2026, 10, 30)
