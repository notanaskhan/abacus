"""A-09-T13 rest (TASK-8365; DEC-5340; SPEC-658 AC-1.1, AC-1.4; AUD-32 c) against Postgres.

"Agent-proposed 3 tiers from the 5 OneWorld subsidiaries (suggestion; Use structure · Edit);
ownership 100%." The proposal is code recorded as the `audit.group_structure` run and offered as
one suggestion; nothing saves until Use structure (adopt) or Edit (the PUT). Adopting saves the
five entities at levels 1, 2 and 3 and the OneWorld connection covers them after commit; an edited
value or a changed run output is refused; without a OneWorld source there is nothing to propose.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime

import asyncpg
import pytest

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.agents.proposals import adopt_suggestion
from abacus.modules.assurance import api as _assurance  # registers the applier and the target
from abacus.modules.assurance import group_consolidation as svc
from abacus.modules.assurance import group_structure as proposal
from abacus.modules.assurance.group_contract import (
    ConsolidationIn,
    StructureInvalid,
    StructureSourceMissing,
)
from abacus.modules.connections.fake_oneworld import SUBSIDIARIES
from abacus.modules.identity.api import AuthContext
from abacus.modules.ledger import api as ledger

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
assert _assurance.SUBSCRIPTIONS["consolidation.structure_adopted"] is proposal.on_structure_adopted


@dataclass(frozen=True)
class World:
    ctx: AuthContext
    seed: Seeder
    engagement: uuid.UUID
    work_item: uuid.UUID
    entities: dict[str, uuid.UUID]
    connection: uuid.UUID


@pytest.fixture
async def world(migrated_db: MigratedDatabase) -> AsyncIterator[World]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = uuid.uuid4()
    await seed.run(
        "INSERT INTO firms (tenant_id, name, synthetic) VALUES ($1, 'Probe', true)", tenant
    )
    user = uuid.UUID(
        str(
            await seed.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) VALUES "
                "('https://probe.test', $1, $2, 'Omar Haddad') RETURNING id",
                uuid.uuid4().hex,
                f"{uuid.uuid4().hex}@x.test",
            )
        )
    )
    await seed.run(
        "INSERT INTO memberships (tenant_id, user_id, status) VALUES ($1, $2, 'active')",
        tenant,
        user,
    )
    client = await seed.value(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Harlow & Pike') RETURNING id", tenant
    )
    entities: dict[str, uuid.UUID] = {}
    for name in SUBSIDIARIES:
        entities[name] = uuid.UUID(
            str(
                await seed.value(
                    "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, "
                    "$3) RETURNING id",
                    tenant,
                    client,
                    name,
                )
            )
        )
    top = entities["HP Holdings"]
    engagement = uuid.UUID(
        str(
            await seed.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                "fiscal_period_start, fiscal_period_end, created_by, status) "
                "VALUES ($1, $2, $3, 'FY2026 Group Audit', '2026-01-01', '2026-12-31', $4, "
                "'active') RETURNING id",
                tenant,
                client,
                top,
                user,
            )
        )
    )
    for entity in entities.values():
        if entity != top:
            await seed.run(
                "INSERT INTO engagement_entities (tenant_id, engagement_id, client_entity_id, "
                "role) VALUES ($1, $2, $3, 'component')",
                tenant,
                engagement,
                entity,
            )
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) VALUES ($1, "
        "$2, $3, 'engagement_partner')",
        tenant,
        engagement,
        user,
    )
    work_item = uuid.UUID(
        str(
            await seed.value(
                "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
                engagement,
            )
        )
    )
    connection = uuid.UUID(
        str(
            await seed.value(
                "INSERT INTO connections (tenant_id, client_entity_id, provider, created_by, "
                "category, external_account_ref, display_label) VALUES ($1, $2, 'fake', 'seed', "
                "'ledger', 'oneworld-1', 'NetSuite OneWorld') RETURNING id",
                tenant,
                top,
            )
        )
    )
    ctx = AuthContext(
        TenantContext(tenant, "human", str(user)), user, uuid.uuid4(), None, datetime.now(UTC)
    )
    yield World(ctx, seed, engagement, work_item, entities, connection)
    await dispose_engine()


async def _consolidation(w: World, *, source: bool = True) -> uuid.UUID:
    made = await svc.create(
        w.ctx,
        w.work_item,
        w.engagement,
        ConsolidationIn(
            name="Harlow & Pike FY2026",
            year_end=date(2026, 12, 31),
            reporting_currency="USD",
            interim_period_end=date(2026, 8, 31),
            prior_period_end=date(2025, 12, 31),
            source_connection_id=w.connection if source else None,
        ),
        uuid.uuid4().hex,
    )
    return made.id


async def _version(w: World, suggestion: uuid.UUID) -> int:
    return int(
        str(await w.seed.value("SELECT version FROM suggestions WHERE id = $1", suggestion))
    )


async def test_aud32_c_the_proposal_is_a_suggestion_and_nothing_saves(world: World) -> None:
    w = world
    consolidation = await _consolidation(w)
    suggestion = await proposal.propose(w.ctx, w.work_item, consolidation)

    row = (
        await w.seed.rows(
            "SELECT s.target_type, s.target_id, s.field_key, s.status, s.citation_ids, "
            "r.agent_id, r.initiator_user_id, r.status AS run_status, r.output "
            "FROM suggestions s JOIN agent_runs r ON r.id = s.agent_run_id WHERE s.id = $1",
            suggestion,
        )
    )[0]
    assert (row["target_type"], row["target_id"], row["field_key"], row["status"]) == (
        "consolidation",
        consolidation,
        "structure",
        "pending",
    )
    assert row["citation_ids"] == []
    assert (row["agent_id"], row["initiator_user_id"], row["run_status"]) == (
        "audit.group_structure",
        w.ctx.user_id,
        "completed",
    )
    facts = await ledger.consolidation_facts(w.ctx.tenant, consolidation)
    assert facts.entities == ()  # AC-1.4: nothing saves until Use structure or Edit


async def test_aud32_c_use_structure_saves_three_tiers_at_100(world: World) -> None:
    w = world
    consolidation = await _consolidation(w)
    suggestion = await proposal.propose(w.ctx, w.work_item, consolidation)

    await adopt_suggestion(
        w.ctx,
        suggestion,
        seen_version=await _version(w, suggestion),
        edited_value=None,
        citation_note=None,
    )

    view = await svc.get(w.ctx, w.work_item, consolidation)
    e = w.entities
    own = {x.id: x.client_entity_id for x in view.entities}
    tree = {
        x.client_entity_id: (None if x.parent_id is None else own[x.parent_id], x.level)
        for x in view.entities
    }
    assert {x.ownership_pct for x in view.entities} == {100}
    assert tree == {
        e["HP Holdings"]: (None, 1),
        e["HP Operating"]: (e["HP Holdings"], 2),
        e["HP Real Estate"]: (e["HP Holdings"], 2),
        e["HP Manufacturing"]: (e["HP Operating"], 3),
        e["HP Distribution"]: (e["HP Operating"], 3),
    }
    assert view.tiers == 3
    events = await w.seed.rows(
        "SELECT id, payload::text AS payload FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'consolidation.structure_adopted'",
        w.ctx.tenant_id,
    )
    assert len(events) == 1
    # After commit the OneWorld connection covers the five (the relay delivers the event).
    await proposal.on_structure_adopted(
        OutboxEvent(
            events[0]["id"],
            w.ctx.tenant_id,
            "consolidation.structure_adopted",
            json.loads(events[0]["payload"]),
        )
    )
    covered = await w.seed.rows(
        "SELECT client_entity_id FROM connection_entity_coverage WHERE connection_id = $1 "
        "AND live",
        w.connection,
    )
    assert {r["client_entity_id"] for r in covered} == set(e.values())


async def test_an_edited_value_is_refused_edit_is_the_put(world: World) -> None:
    w = world
    consolidation = await _consolidation(w)
    suggestion = await proposal.propose(w.ctx, w.work_item, consolidation)
    with pytest.raises(StructureInvalid):
        await adopt_suggestion(
            w.ctx,
            suggestion,
            seen_version=await _version(w, suggestion),
            edited_value="0" * 64,
            citation_note="moved Real Estate",
        )
    assert (await ledger.consolidation_facts(w.ctx.tenant, consolidation)).entities == ()


async def test_the_proposal_cannot_change_under_its_suggestion(world: World) -> None:
    """The finished run's output is immutable (the database refuses), and a suggestion whose
    digest no longer names that output is refused at Use structure."""
    w = world
    consolidation = await _consolidation(w)
    suggestion = await proposal.propose(w.ctx, w.work_item, consolidation)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await w.seed.run(
            "UPDATE agent_runs SET output = jsonb_set(output, '{entities,0,2}', '2') "
            "WHERE id = (SELECT agent_run_id FROM suggestions WHERE id = $1)",
            suggestion,
        )
    await w.seed.run(
        "UPDATE suggestions SET proposed_value = jsonb_build_object('t', 'text', 'v', $2::text) "
        "WHERE id = $1",
        suggestion,
        "0" * 64,
    )
    with pytest.raises(StructureInvalid):
        await adopt_suggestion(
            w.ctx,
            suggestion,
            seen_version=await _version(w, suggestion),
            edited_value=None,
            citation_note=None,
        )
    assert (await ledger.consolidation_facts(w.ctx.tenant, consolidation)).entities == ()


async def test_without_a_oneworld_source_there_is_nothing_to_propose(world: World) -> None:
    w = world
    consolidation = await _consolidation(w, source=False)
    with pytest.raises(StructureSourceMissing):
        await proposal.propose(w.ctx, w.work_item, consolidation)


async def test_no_entity_named_like_a_subsidiary_proposes_nothing(world: World) -> None:
    w = world
    consolidation = await _consolidation(w)
    await w.seed.run(
        "UPDATE client_entities SET name = 'Harlow & Pike ' || name WHERE tenant_id = $1",
        w.ctx.tenant_id,
    )
    with pytest.raises(StructureSourceMissing):
        await proposal.propose(w.ctx, w.work_item, consolidation)
