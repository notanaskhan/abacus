"""A-09-T13 (TASK-8094; SPEC-658 AC-1.1 to AC-1.3; DEC-5070) against Postgres: "Finalize with Real
Estate Prior missing answers 409 trial_balance_missing, a finalized structure cannot change, and
finalize writes one audit event and starts five mapping runs" (one TB of record per entity, whose
adoption starts its mapping run through A-03's subscriber).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.assurance import group_consolidation as svc
from abacus.modules.assurance.group_contract import (
    ConsolidationFinalizeIn,
    ConsolidationIn,
    StructureEntityIn,
    StructureIn,
    TbAttachIn,
    TbNotNeededIn,
    TrialBalanceMissing,
)
from abacus.modules.identity.api import AuthContext
from abacus.modules.ledger import api as ledger

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
NAMES = (
    "Holdings, Inc.",
    "Operating Co.",
    "Manufacturing, Inc.",
    "Distribution, Inc.",
    "Real Estate, LLC",
)


@dataclass(frozen=True)
class World:
    ctx: AuthContext
    seed: Seeder
    engagement: uuid.UUID
    work_item: uuid.UUID
    entities: list[uuid.UUID]


@pytest.fixture
async def world(migrated_db: MigratedDatabase) -> AsyncIterator[World]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = uuid.uuid4()
    await seed.run("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", tenant)
    user = uuid.UUID(str(await seed.value(
        "INSERT INTO users (idp_issuer, idp_subject, email, display_name) VALUES ('https://probe.test', $1, $2, 'Omar Haddad') RETURNING id",
        uuid.uuid4().hex, f"{uuid.uuid4().hex}@x.test",
    )))  # fmt: skip
    await seed.run(
        "INSERT INTO memberships (tenant_id, user_id, status) VALUES ($1, $2, 'active')",
        tenant,
        user,
    )
    client = await seed.value(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Harlow & Pike') RETURNING id", tenant
    )
    entities = [
        uuid.UUID(str(await seed.value(
            "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, $3) RETURNING id",
            tenant, client, f"Harlow & Pike {n}",
        )))
        for n in NAMES
    ]  # fmt: skip
    engagement = uuid.UUID(str(await seed.value(
        "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, fiscal_period_start, fiscal_period_end, created_by, status) "
        "VALUES ($1, $2, $3, 'FY2026 Group Audit', '2026-01-01', '2026-12-31', $4, 'active') RETURNING id",
        tenant, client, entities[0], user,
    )))  # fmt: skip
    for entity in entities[1:]:
        await seed.run(
            "INSERT INTO engagement_entities (tenant_id, engagement_id, client_entity_id, role) VALUES ($1, $2, $3, 'component')",
            tenant, engagement, entity,
        )  # fmt: skip
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) VALUES ($1, $2, $3, 'engagement_partner')",
        tenant, engagement, user,
    )  # fmt: skip
    work_item = uuid.UUID(str(await seed.value(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) VALUES ($1, $2, $3, 'assurance', 'Audit', $4) RETURNING id",
        tenant, engagement, client, user,
    )))  # fmt: skip
    ctx = AuthContext(
        TenantContext(tenant, "human", str(user)), user, uuid.uuid4(), None, datetime.now(UTC)
    )
    yield World(ctx, seed, engagement, work_item, entities)
    await dispose_engine()


async def _snapshot(w: World, entity: uuid.UUID, start: date, end: date, debits: int) -> uuid.UUID:
    return uuid.UUID(str(await w.seed.value(
        "INSERT INTO ledger_snapshots (tenant_id, client_entity_id, period_start, period_end, pulled_at, source, raw_fingerprint, line_count, total_debit, total_credit) "
        "VALUES ($1, $2, $3, $4, now(), 'import', md5(random()::text), 2, $5, $5) RETURNING id",
        w.ctx.tenant_id, entity, start, end, debits,
    )))  # fmt: skip


async def _built(w: World) -> uuid.UUID:
    made = await svc.create(
        w.ctx, w.work_item, w.engagement,
        ConsolidationIn(name="Harlow & Pike FY2026", year_end=date(2026, 12, 31), reporting_currency="USD",
                        interim_period_end=date(2026, 8, 31), prior_period_end=date(2025, 12, 31)),
        uuid.uuid4().hex,
    )  # fmt: skip
    h, o, m, d, r = w.entities
    tree = [(h, None, 1), (o, h, 2), (m, o, 3), (d, o, 3), (r, h, 2)]
    view = await svc.save_structure(
        w.ctx, w.work_item, made.id,
        StructureIn(entities=[StructureEntityIn(client_entity_id=e, parent_client_entity_id=p, level=lv, ownership_pct=100) for e, p, lv in tree]),
        str(made.row_version),
    )  # fmt: skip
    assert view.tiers == 3 and len(view.missing) == 10
    for entity in view.entities:
        current = await _snapshot(
            w, entity.client_entity_id, date(2026, 1, 1), date(2026, 8, 31), 1_000_000
        )
        await svc.attach(
            w.ctx,
            w.work_item,
            made.id,
            entity.id,
            TbAttachIn(source="upload", label="interim", period_kind="current", upload_id=current),
        )
        if entity.client_entity_id != r:
            prior = await _snapshot(
                w, entity.client_entity_id, date(2025, 1, 1), date(2025, 12, 31), 900_000
            )
            await svc.attach(
                w.ctx,
                w.work_item,
                made.id,
                entity.id,
                TbAttachIn(source="upload", label="prior", period_kind="prior", upload_id=prior),
            )
    return made.id


async def test_ac_finalize_with_real_estate_prior_missing_is_refused(world: World) -> None:
    consolidation = await _built(world)
    view = await svc.get(world.ctx, world.work_item, consolidation)
    assert view.missing == ["Harlow & Pike Real Estate, LLC · Prior"]
    assert view.interim_total_debits == 5_000_000 and view.all_balanced
    with pytest.raises(TrialBalanceMissing):
        await svc.finalize(
            world.ctx,
            world.work_item,
            consolidation,
            ConsolidationFinalizeIn(seen_version=view.row_version),
            uuid.uuid4().hex,
        )


async def test_ac_finalize_writes_one_event_and_adopts_five_tbs_then_freezes(world: World) -> None:
    consolidation = await _built(world)
    view = await svc.get(world.ctx, world.work_item, consolidation)
    real_estate = next(e for e in view.entities if e.client_entity_id == world.entities[4])
    prior = next(t for t in real_estate.trial_balances if t.period_kind == "prior")
    await svc.not_needed(
        world.ctx,
        world.work_item,
        consolidation,
        prior.id,
        TbNotNeededIn(reason="Formed in 2026; no prior year"),
    )
    view = await svc.get(world.ctx, world.work_item, consolidation)
    assert view.missing == [] and "consolidation.finalize" in view.allowed_actions
    done = await svc.finalize(
        world.ctx,
        world.work_item,
        consolidation,
        ConsolidationFinalizeIn(seen_version=view.row_version),
        uuid.uuid4().hex,
    )
    assert done.status == "finalized" and done.finalized_by_name == "Omar Haddad"
    events = await world.seed.rows(
        "SELECT count(*) AS n FROM audit_events WHERE tenant_id = $1 AND action = 'consolidation.finalized'", world.ctx.tenant_id
    )  # fmt: skip
    assert events[0]["n"] == 1
    tbs = await world.seed.rows(
        "SELECT count(*) AS n FROM trial_balances WHERE work_item_id = $1", world.work_item
    )
    assert tbs[0]["n"] == 5  # one TB of record per entity: each adoption starts its mapping run
    with pytest.raises(ledger.ConsolidationNotDraft):
        await svc.save_structure(
            world.ctx, world.work_item, consolidation,
            StructureIn(entities=[StructureEntityIn(client_entity_id=world.entities[0], level=1, ownership_pct=100)]),
            str(done.row_version),
        )  # fmt: skip
