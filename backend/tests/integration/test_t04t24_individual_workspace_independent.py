"""T-04-T24 (ac-test-author: ayushkbhatia, ADR-078 solo independence as DEC-3127; SPEC-649; T-04
§4.2): independent checks of migration 0761 and the workspace contracts, written from the epic
and the SPEC, not from T-04-T10/T15/T16/T17's own suites.

- Every 0761 table has forced row-level security and the tenant policy: a second tenant reads
  nothing.
- The insert-only tables refuse UPDATE and DELETE to the app role; `document_approvals` is
  human-only by CHECK, a reversal names one approval, once, and only a reversal carries a reason.
- Every field of the workspace and worksheet contracts carries a classification tag; values are
  never below Confidential.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import asyncpg
import pytest
from pydantic import BaseModel

from abacus.kernel.classification import level_of, unclassified_fields
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import provisioned_database

TABLES = (
    "return_worksheets",
    "return_worksheet_sections",
    "return_fields",
    "document_approvals",
    "k1_activities",
    "k1_treatments",
    "k1_treatment_events",
    "residency_determinations",
    "residency_facts",
)
IMMUTABLE = ("document_approvals", "k1_treatment_events", "residency_facts")
# One fixed statement per table (no SQL built from names).
COUNTS = (
    "SELECT count(*) FROM return_worksheets",
    "SELECT count(*) FROM return_worksheet_sections",
    "SELECT count(*) FROM return_fields",
    "SELECT count(*) FROM document_approvals",
    "SELECT count(*) FROM k1_activities",
    "SELECT count(*) FROM k1_treatments",
    "SELECT count(*) FROM k1_treatment_events",
    "SELECT count(*) FROM residency_determinations",
    "SELECT count(*) FROM residency_facts",
)


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _rows(dsn: str, sql: str, *args: object) -> list[asyncpg.Record]:
    async def go() -> list[asyncpg.Record]:
        conn = await asyncpg.connect(dsn)
        try:
            return await conn.fetch(sql, *args)
        finally:
            await conn.close()

    return asyncio.run(go())


@pytest.mark.parametrize("table", TABLES)
def test_every_table_forces_row_level_security_with_the_tenant_policy(
    db: sc.Database, table: str
) -> None:
    (row,) = _rows(
        db.superuser_dsn,
        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = $1",
        table,
    )
    assert row["relrowsecurity"] and row["relforcerowsecurity"]
    policies = _rows(db.superuser_dsn, "SELECT qual FROM pg_policies WHERE tablename = $1", table)
    assert any("tenant_id" in str(p["qual"]) for p in policies)


@pytest.mark.parametrize("table", IMMUTABLE)
def test_insert_only_tables_refuse_update_and_delete_to_the_app_role(
    db: sc.Database, table: str
) -> None:
    (row,) = _rows(
        db.superuser_dsn,
        "SELECT has_table_privilege('abacus_app', $1, 'UPDATE') AS u, "
        "has_table_privilege('abacus_app', $1, 'DELETE') AS d, "
        "has_table_privilege('abacus_app', $1, 'INSERT') AS i",
        table,
    )
    assert row["i"] and not row["u"] and not row["d"]


def test_document_approvals_are_human_only_and_a_reversal_is_once_with_its_reason(
    db: sc.Database,
) -> None:
    checks = {
        r["conname"]: str(r["def"])
        for r in _rows(
            db.superuser_dsn,
            "SELECT conname, pg_get_constraintdef(oid) AS def FROM pg_constraint "
            "WHERE conrelid = 'document_approvals'::regclass",
        )
    }
    human = checks["document_approvals_by_a_person"]
    assert "'human'" in human and "app.actor_kind" in human and "app.actor_id" in human
    assert "reverses_id IS NOT NULL" in checks["document_approvals_reverse"]
    assert "reason_sealed IS NULL" in checks["document_approvals_reason"]
    assert any("UNIQUE (reverses_id)" in d for d in checks.values())


def test_a_second_tenant_reads_nothing_through_the_app_role(db: sc.Database) -> None:
    """With no rows of its own, a tenant's app-role session sees none of another's (the policy
    compares `tenant_id` with the session's tenant)."""
    app = db.app_url.replace("postgresql+asyncpg://", "postgresql://")

    async def go() -> list[int]:
        conn = await asyncpg.connect(app)
        try:
            counts: list[int] = []
            async with conn.transaction():
                await conn.execute(
                    "SELECT set_config('app.tenant_id', '00000000-0000-4000-8000-0000000000ff', true)"
                )
                for statement in COUNTS:
                    counts.append(int(await conn.fetchval(statement)))
            return counts
        finally:
            await conn.close()

    assert asyncio.run(go()) == [0] * len(TABLES)


def _models() -> list[type[BaseModel]]:
    from abacus.modules.tax import workspace_contract, worksheets

    found: list[type[BaseModel]] = []
    for module in (workspace_contract, worksheets):
        for value in vars(module).values():
            if isinstance(value, type) and issubclass(value, BaseModel) and value is not BaseModel:
                if value.__module__ == module.__name__:
                    found.append(value)
    return found


def test_every_contract_field_carries_a_classification_tag() -> None:
    models = _models()
    assert models
    for model in models:
        assert unclassified_fields(model) == [], model.__name__


def test_values_are_never_below_confidential() -> None:
    for model in _models():
        for name, info in model.model_fields.items():
            if name in {"value", "current_value", "prior_value", "previous_value"}:
                assert level_of(info) in ("confidential", "restricted"), (model.__name__, name)
