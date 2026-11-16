"""A-09-T10, T11, T12 (TASK-8091 to 8093; SPEC-658) against Postgres: the S46 group-audit
migrations' acceptance, by the database itself.

- 0896: an AJE still cannot reach posted; an elimination posts only to the consolidation layer;
  a line for an entity outside its consolidation fails at commit.
- 0897: a new connection covers its own entity; one OneWorld connection may cover five; a second
  live ledger for a covered subsidiary is refused.
- 0898: a PM on an Analytical-only component is refused; a deliverable review by a non-human
  actor is refused; a group materiality version must name its consolidation.

Up/down/up runs with every migration in the end pass (`migrations` round trip).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import asyncpg
import pytest

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio


@dataclass(frozen=True)
class Group:
    seed: Seeder
    tenant: uuid.UUID
    user: uuid.UUID
    engagement: uuid.UUID
    work_item: uuid.UUID
    entities: list[uuid.UUID]
    consolidation: uuid.UUID
    members: list[uuid.UUID]  # consolidation_entities ids, in entity order


async def _group(migrated_db: MigratedDatabase) -> Group:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = uuid.uuid4()
    await seed.run("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", tenant)
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
    names = ["Holdings", "Operating", "Manufacturing", "Distribution", "Real Estate"]
    entities = [
        uuid.UUID(
            str(
                await seed.value(
                    "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, "
                    "$3) RETURNING id",
                    tenant,
                    client,
                    f"Harlow & Pike {n}",
                )
            )
        )
        for n in names
    ]
    engagement = uuid.UUID(
        str(
            await seed.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                "fiscal_period_start, fiscal_period_end, created_by, status) "
                "VALUES ($1, $2, $3, 'FY2026 Group Audit', '2026-01-01', '2026-12-31', $4, "
                "'active') RETURNING id",
                tenant,
                client,
                entities[0],
                user,
            )
        )
    )
    for entity in entities[1:]:
        await seed.run(
            "INSERT INTO engagement_entities (tenant_id, engagement_id, client_entity_id, role) "
            "VALUES ($1, $2, $3, 'component')",
            tenant,
            engagement,
            entity,
        )
    work_item = uuid.UUID(
        str(
            await seed.value(
                # The engagement opens with its one assurance work item (0069's trigger).
                "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
                engagement,
            )
        )
    )
    consolidation = uuid.UUID(
        str(
            await seed.value(
                "INSERT INTO consolidations (tenant_id, engagement_id, work_item_id, name, "
                "year_end, reporting_currency, created_by) "
                "VALUES ($1, $2, $3, 'Harlow & Pike FY2026', '2026-12-31', 'USD', $4) RETURNING "
                "id",
                tenant,
                engagement,
                work_item,
                user,
            )
        )
    )
    root = uuid.UUID(
        str(
            await seed.value(
                "INSERT INTO consolidation_entities (tenant_id, consolidation_id, "
                "client_entity_id, level) VALUES ($1, $2, $3, 1) RETURNING id",
                tenant,
                consolidation,
                entities[0],
            )
        )
    )
    members = [root]
    for entity in entities[1:4]:  # Real Estate stays outside the consolidation for the line test
        members.append(
            uuid.UUID(
                str(
                    await seed.value(
                        "INSERT INTO consolidation_entities (tenant_id, consolidation_id, "
                        "client_entity_id, parent_id, level) VALUES ($1, $2, $3, $4, 2) "
                        "RETURNING id",
                        tenant,
                        consolidation,
                        entity,
                        root,
                    )
                )
            )
        )
    return Group(seed, tenant, user, engagement, work_item, entities, consolidation, members)


async def _entry(
    g: Group, kind: str, number: int, *, status: str = "proposed", target: str | None = None
) -> uuid.UUID:
    ref = {"aje": "AJE", "elimination": "ELIM"}[kind]
    return uuid.UUID(
        str(
            await g.seed.value(
                "INSERT INTO proposed_entries (tenant_id, engagement_id, work_item_id, kind, "
                "number, ref, threshold_result, "
                "is_attest_client, status, created_by_kind, created_by_id, consolidation_id, "
                "posting_target) "
                "VALUES ($1, $2, $3, $4, $5, $6, 'review_required', false, $7, 'human', $8, $9, "
                "$10) RETURNING id",
                g.tenant,
                g.engagement,
                g.work_item,
                kind,
                number,
                f"{ref}-{number}",
                status,
                str(g.user),
                g.consolidation if kind == "elimination" else None,
                target,
            )
        )
    )


# --- 0896 ----------------------------------------------------------------------------------------


async def test_t10_an_aje_still_cannot_reach_posted(migrated_db: MigratedDatabase) -> None:
    g = await _group(migrated_db)
    with pytest.raises(asyncpg.CheckViolationError):
        await _entry(g, "aje", 1, status="posted")


async def test_t10_an_elimination_posts_only_to_the_consolidation_layer(
    migrated_db: MigratedDatabase,
) -> None:
    g = await _group(migrated_db)
    with pytest.raises(asyncpg.CheckViolationError):
        await _entry(g, "elimination", 1, status="posted")
    posted = await _entry(g, "elimination", 2, status="posted", target="consolidation_layer")
    assert posted is not None
    with pytest.raises(asyncpg.CheckViolationError):
        await _entry(g, "aje", 3, target="consolidation_layer")


async def test_t10_a_line_outside_the_consolidation_fails_at_commit(
    migrated_db: MigratedDatabase,
) -> None:
    g = await _group(migrated_db)
    entry = await _entry(g, "elimination", 1)
    # Both lines in one statement (one transaction): balanced, so only the entity check fires
    # at commit, on the Real Estate line.
    with pytest.raises(asyncpg.CheckViolationError, match="line_entity_outside_consolidation"):
        await g.seed.run(
            "INSERT INTO proposed_entry_lines (tenant_id, engagement_id, work_item_id, entry_id, "
            "line_no, account_code, debit, credit, client_entity_id, consolidation_level) "
            "VALUES ($1, $2, $3, $4, 1, '1610', 240000, 0, $5, 2), "
            "($1, $2, $3, $4, 2, '1610', 0, 240000, $6, 2)",
            g.tenant,
            g.engagement,
            g.work_item,
            entry,
            g.entities[3],
            g.entities[4],
        )


# --- 0897 ----------------------------------------------------------------------------------------

_CONNECT = (
    "INSERT INTO connections (tenant_id, client_entity_id, provider, created_by, category, "
    "external_account_ref, display_label) "
    "VALUES ($1, $2, 'fake', 'seed', 'ledger', $3, 'NetSuite OneWorld') RETURNING id"
)


async def test_t11_one_oneworld_connection_covers_five_and_a_second_ledger_is_refused(
    migrated_db: MigratedDatabase,
) -> None:
    g = await _group(migrated_db)
    connection = uuid.UUID(
        str(await g.seed.value(_CONNECT, g.tenant, g.entities[0], "oneworld-1"))
    )
    own = await g.seed.rows(
        "SELECT client_entity_id, live FROM connection_entity_coverage WHERE connection_id = $1",
        connection,
    )
    assert [(r["client_entity_id"], r["live"]) for r in own] == [(g.entities[0], True)]
    for entity in g.entities[1:]:
        await g.seed.run(
            "INSERT INTO connection_entity_coverage (tenant_id, connection_id, client_entity_id, "
            "category, live) VALUES ($1, $2, $3, 'ledger', true)",
            g.tenant,
            connection,
            entity,
        )
    rows = await g.seed.rows(
        "SELECT count(*) AS n FROM connection_entity_coverage WHERE connection_id = $1 AND live",
        connection,
    )
    assert rows[0]["n"] == 5
    with pytest.raises(asyncpg.UniqueViolationError):
        await g.seed.value(_CONNECT, g.tenant, g.entities[2], "quickbooks-mfg")


async def test_t11_revoking_the_connection_frees_its_entities(
    migrated_db: MigratedDatabase,
) -> None:
    g = await _group(migrated_db)
    connection = uuid.UUID(
        str(await g.seed.value(_CONNECT, g.tenant, g.entities[1], "oneworld-2"))
    )
    await g.seed.run(
        "UPDATE connections SET status = 'revoked', revoked_at = now() WHERE id = $1", connection
    )
    rows = await g.seed.rows(
        "SELECT live FROM connection_entity_coverage WHERE connection_id = $1", connection
    )
    assert [r["live"] for r in rows] == [False]
    assert await g.seed.value(_CONNECT, g.tenant, g.entities[1], "oneworld-3") is not None


# --- 0898 ----------------------------------------------------------------------------------------

_COMPONENT = (
    "INSERT INTO components (tenant_id, engagement_id, work_item_id, consolidation_entity_id, "
    "planned_work, "
    "performed_by, component_pm, created_by) VALUES ($1, $2, $3, $4, $5, 'group_team', $6, $7) "
    "RETURNING id"
)


async def test_t12_a_pm_on_an_analytical_only_component_is_refused(
    migrated_db: MigratedDatabase,
) -> None:
    g = await _group(migrated_db)
    await g.seed.value(
        _COMPONENT, g.tenant, g.engagement, g.work_item, g.members[1], "full_scope", 12000, g.user
    )
    with pytest.raises(asyncpg.CheckViolationError):
        await g.seed.value(
            _COMPONENT,
            g.tenant,
            g.engagement,
            g.work_item,
            g.members[2],
            "analytical_only",
            9000,
            g.user,
        )
    assert await g.seed.value(
        _COMPONENT,
        g.tenant,
        g.engagement,
        g.work_item,
        g.members[2],
        "analytical_only",
        None,
        g.user,
    )


async def test_t12_a_deliverable_review_by_a_non_human_is_refused(
    migrated_db: MigratedDatabase,
) -> None:
    g = await _group(migrated_db)
    auditor = await g.seed.value(
        "INSERT INTO component_auditors (tenant_id, engagement_id, work_item_id, "
        "organisation_name, city, created_by) "
        "VALUES ($1, $2, $3, 'Pruett & Lang LLP', 'Denver', $4) RETURNING id",
        g.tenant,
        g.engagement,
        g.work_item,
        g.user,
    )
    deliverable = await g.seed.value(
        "INSERT INTO component_deliverables (tenant_id, engagement_id, work_item_id, "
        "component_auditor_id, title, due_on) "
        "VALUES ($1, $2, $3, $4, 'Interim memo', '2026-11-30') RETURNING id",
        g.tenant,
        g.engagement,
        g.work_item,
        auditor,
    )
    review = (
        "UPDATE component_deliverables SET status = 'reviewed', received_at = now(), reviewed_by "
        "= $2, "
        "reviewed_at = now(), reviewed_actor_kind = $3 WHERE id = $1"
    )
    with pytest.raises(asyncpg.CheckViolationError):
        await g.seed.run(review, deliverable, g.user, "agent")
    await g.seed.run(review, deliverable, g.user, "human")


async def test_t12_a_group_materiality_names_its_consolidation(
    migrated_db: MigratedDatabase,
) -> None:
    g = await _group(migrated_db)
    rows = await g.seed.rows(
        "SELECT conname FROM pg_constraint WHERE conname = "
        "'materiality_versions_group_names_consolidation'"
    )
    assert len(rows) == 1
    default = await g.seed.rows(
        "SELECT column_default FROM information_schema.columns WHERE table_name = "
        "'materiality_versions' AND column_name = 'scope'"
    )
    assert "entity" in str(default[0]["column_default"])
