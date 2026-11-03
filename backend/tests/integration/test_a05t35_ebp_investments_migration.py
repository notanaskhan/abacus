"""A-05-T35 (TASK-3254; DEC-2234): migration 0665 `ebp_investments_5500`.

Row acceptance: "Upgrade and downgrade pass on the seed, and an agent cannot write a
certification evaluation." Also: every new table has forced RLS and no DELETE grant; an
evaluation is insert-only; a reconciling item needs its note; an inconsistent Part IV answer
needs its issue.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from typing import cast

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

TABLES = (
    "ebp_trust_report_lines",
    "ebp_certification_points",
    "ebp_certification_evaluations",
    "ebp_form5500_drafts",
    "ebp_form5500_lines",
    "ebp_part_iv_answers",
    "ebp_supplemental_schedules",
    "ebp_schedule_h_mappings",
)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def test_ac_0665_goes_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, "0664", down=True)
    for table in TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    migrate(private_db.owner_url, "head")
    for table in TABLES:
        assert _value(
            private_db,
            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
            table,
        ), table
        assert not _value(
            private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'DELETE')"
        ), table


async def _point(seed: Seeder) -> dict[str, uuid.UUID]:
    tenant = await seed.firm()
    person = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, person.user_id)
    item = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'", engagement
        ),
    )
    evidence_item = await seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id) VALUES ($1, $2, 'Harborline trust report.pdf', 'human', 'seed') "
        "RETURNING id",
        tenant,
        engagement,
    )
    version = await seed.value(
        "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, version_no, "
        "fingerprint, storage_key, storage_version_id, size_bytes, media_type, source, method) "
        "VALUES ($1, $2, $3, 1, repeat('c', 64), "
        "'tenants/' || $1::uuid::text || '/sha256/' || repeat('c', 64), 'v1', 10, "
        "'application/pdf', 'client_upload', 'uploaded') RETURNING id",
        tenant,
        engagement,
        evidence_item,
    )
    point = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO ebp_certification_points (tenant_id, engagement_id, work_item_id, "
            "evidence_version_id, point_key) VALUES ($1, $2, $3, $4, 'qualifying_institution') "
            "RETURNING id",
            tenant,
            engagement,
            item,
            version,
        ),
    )
    draft = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO ebp_form5500_drafts (tenant_id, engagement_id, work_item_id, "
            "evidence_version_id, received_at, plan_year) VALUES ($1, $2, $3, $4, now(), 2025) "
            "RETURNING id",
            tenant,
            engagement,
            item,
            version,
        ),
    )
    return {
        "tenant": tenant,
        "engagement": engagement,
        "item": item,
        "point": point,
        "draft": draft,
        "person": person.user_id,
    }


_EVALUATE = (
    "INSERT INTO ebp_certification_evaluations (tenant_id, engagement_id, work_item_id, "
    "point_id, answer) VALUES ($1, $2, $3, $4, 'evaluated')"
)


def test_ac_an_agent_cannot_write_a_certification_evaluation(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _point(seed)
        args = (ids["tenant"], ids["engagement"], ids["item"], ids["point"])
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.as_actor(ids["tenant"], ("agent", str(ids["person"])), _EVALUATE, *args)
        await seed.as_actor(ids["tenant"], ("human", str(ids["person"])), _EVALUATE, *args)
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await seed.run(
                "UPDATE ebp_certification_evaluations SET answer = 'not_evaluated' "
                "WHERE point_id = $1",
                ids["point"],
            )

    asyncio.run(scenario())


def test_ac_tie_out_rows_keep_their_reasons(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _point(seed)
        scope = (ids["tenant"], ids["engagement"], ids["item"], ids["draft"])
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.run(
                "INSERT INTO ebp_form5500_lines (tenant_id, engagement_id, work_item_id, "
                "draft_id, line_code, caption, classification, classified_by_kind) VALUES "
                "($1, $2, $3, $4, '1c(8)', 'Participant loans', 'reconciling_item', 'code')",
                *scope,
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.run(
                "INSERT INTO ebp_part_iv_answers (tenant_id, engagement_id, work_item_id, "
                "draft_id, question, draft_answer, result) VALUES ($1, $2, $3, $4, '4a', 'no', "
                "'inconsistent')",
                *scope,
            )

    asyncio.run(scenario())
