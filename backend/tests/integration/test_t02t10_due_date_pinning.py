"""T-02-T10 (TASK-2216; SPEC-502 AC-18 to AC-20; T-02 §4.2) against Postgres: due dates and
BH-TAX-02 pinned on the return.

The row's acceptance: Ridgeline's extended 1065 resolves to Tue Sep 15, 2026 with its version ids
and a filed return keeps its pinned dates after a correction. The rule rows are synthetic probes
published as the operator CLI will (AGENTS 16); the session database is shared, so the probe
form is unique and the shared forms' answers are read relative to what this test published.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import AsyncIterator
from datetime import date
from typing import cast

import asyncpg
import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import uow
from abacus.modules.tax import due_dates
from abacus.modules.tax.due_dates import FORM_FOR_RULES

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

AY, AN = "ayushkbhatia", "notanaskhan"


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _publish(seed: Seeder, day: int, *, effective: date, tax_year: int = 2025) -> uuid.UUID:
    """A 1065 rule set (calendar year: the 15th of the 3rd month, 7004 + 6 months)."""
    payload = json.dumps(
        {
            "kind": "due_date_rules",
            "rows": [
                {
                    "form": FORM_FOR_RULES["1065"],
                    "fye_rule": "calendar_year",
                    "original": {"months_after_period_end": 3, "day": day},
                    "extension": {"form": "7004", "months": 6},
                    "authority": "Probe authority",
                }
            ],
        }
    )
    version = cast(
        uuid.UUID,
        await seed.value(
            "SELECT reference_set_draft($1, 'due_date_rules', 'Probe rules', 'US', $2, NULL, "
            "$6, $3, $4::jsonb, $5, '[]'::jsonb, $2, 'probe')",
            f"probe.t02t10.{uuid.uuid4().hex[:10]}",
            AY,
            effective,
            payload,
            "sha256:" + hashlib.sha256(payload.encode()).hexdigest(),
            tax_year,
        ),
    )
    await seed.run("SELECT reference_set_publish($1, $2, 'probe')", version, AN)
    return version


async def _return(
    seed: Seeder, tenant: uuid.UUID, status: str, *, extended: bool, tax_year: int = 2025
) -> uuid.UUID:
    partner = (await seed.person(tenant)).user_id
    client = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Probe partnership') RETURNING id",
            tenant,
        ),
    )
    entity = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, 'Probe') "
            "RETURNING id",
            tenant,
            client,
        ),
    )
    engagement = await seed.engagement(tenant, entity, partner)
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
            "name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', '2025 Form 1065', $5) "
            "RETURNING id",
            tenant,
            engagement,
            client,
            entity,
            partner,
        ),
    )
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, form, "
        "tax_year) VALUES ($1, $2, $3, $4, '1065', $5)",
        tenant,
        item,
        engagement,
        entity,
        tax_year,
    )
    await seed.run(
        "UPDATE tax_returns SET status = $2, extended = $3 WHERE work_item_id = $1",
        item,
        status,
        extended,
    )
    return item


async def _dates(seed: Seeder, item: uuid.UUID) -> asyncpg.Record:
    found = await seed.rows(
        "SELECT original_due_on, extended_due_on, due_rule_version_ids FROM tax_returns "
        "WHERE work_item_id = $1",
        item,
    )
    return found[0]


async def test_ac19_ridgelines_extended_1065_is_sep_15_2026_with_its_versions(
    seed: Seeder,
) -> None:
    rules = await _publish(seed, 15, effective=date(2025, 1, 1))
    tenant = await seed.firm()
    item = await _return(seed, tenant, "preparing", extended=True)
    ctx = TenantContext(tenant, "system", "test:t02t10")
    async with uow(ctx) as tx:
        pinned = await due_dates.pin(tx.session, ctx, item)
        assert pinned is not None
        due_dates.record_pinned(tx, item, pinned)
    row = await _dates(seed, item)
    assert row["original_due_on"] == date(2026, 3, 16)  # Mar 15 is a Sunday
    assert row["extended_due_on"] == date(2026, 9, 15)
    assert str(rules) in json.loads(row["due_rule_version_ids"])


async def test_ac20_a_filed_return_keeps_its_dates_after_a_correction(seed: Seeder) -> None:
    # Its own tax year, so no other test's rules answer it (the session database is shared).
    await _publish(seed, 15, effective=date(2031, 1, 1), tax_year=2031)
    tenant = await seed.firm()
    ctx = TenantContext(tenant, "system", "test:t02t10")
    filed = await _return(seed, tenant, "preparing", extended=True, tax_year=2031)
    open_ = await _return(seed, tenant, "preparing", extended=True, tax_year=2031)
    for item in (filed, open_):
        async with uow(ctx) as tx:
            await due_dates.pin(tx.session, ctx, item)
    await seed.run("UPDATE tax_returns SET status = 'filed' WHERE work_item_id = $1", filed)
    before = await _dates(seed, filed)
    # A correction: the 17th, effective later in the year (the latest set effective on or
    # before the period end, Dec 31, 2031, answers).
    await _publish(seed, 17, effective=date(2031, 6, 1), tax_year=2031)
    await due_dates.recompute_unfiled(ctx)
    after_filed, after_open = await _dates(seed, filed), await _dates(seed, open_)
    assert after_filed["original_due_on"] == before["original_due_on"] == date(2032, 3, 15)
    assert after_open["original_due_on"] == date(2032, 3, 17)


async def test_ac18_no_rule_leaves_the_dates_empty(seed: Seeder) -> None:
    tenant = await seed.firm()
    ctx = TenantContext(tenant, "system", "test:t02t10")
    item = await _return(seed, tenant, "preparing", extended=False)
    await seed.run("UPDATE tax_returns SET form = '709' WHERE work_item_id = $1", item)
    async with uow(ctx) as tx:
        pinned = await due_dates.pin(tx.session, ctx, item)
    assert pinned is not None and pinned.original_due_on is None
