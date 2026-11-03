"""P-11-T24 (TASK-3255; DEC-2235): migration 0666 `ocr_v1`.

Row acceptance: "Every new table is tenant-RLS and insert-only for all roles, sealed values are
never selected by list queries, and the single-head check passes." Also: a TIN is only ever a
sealed value with its last four; a refused run names its reason; an OCR page names its run.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Iterator
from pathlib import Path

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

TABLES = ("ocr_runs", "extracted_fields", "extracted_tables", "extracted_table_cells")
SRC = Path(__file__).resolve().parents[2] / "src" / "abacus"


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def test_ac_0666_goes_down_and_up_with_forced_rls_and_insert_only(
    private_db: sc.Database,
) -> None:
    migrate(private_db.owner_url, "0665", down=True)
    for table in TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    migrate(private_db.owner_url, "head")
    for table in TABLES:
        assert _value(
            private_db,
            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
            table,
        ), table
        for privilege in ("UPDATE", "DELETE", "TRUNCATE"):
            assert not _value(
                private_db, f"SELECT has_table_privilege('abacus_app', '{table}', '{privilege}')"
            ), (table, privilege)


def test_ac_the_app_keeps_inserting_evidence_pages_with_the_new_columns(
    private_db: sc.Database,
) -> None:
    for column in ("page_no", "text_source", "ocr_run_id", "mean_confidence"):
        assert _value(
            private_db,
            "SELECT has_column_privilege('abacus_app', 'evidence_pages', $1, 'INSERT')",
            column,
        ), column


def test_ac_a_tin_is_sealed_and_a_refusal_names_its_reason(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        tenant = await seed.firm()
        person = await seed.person(tenant)
        entity = await seed.entity(tenant)
        engagement = await seed.engagement(tenant, entity, person.user_id)
        item = await seed.value(
            "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
            "created_by_id) VALUES ($1, $2, 'CP2000.pdf', 'human', 'seed') RETURNING id",
            tenant,
            engagement,
        )
        version = await seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method) VALUES ($1, $2, $3, 1, repeat('d', 64), "
            "'tenants/' || $1::uuid::text || '/sha256/' || repeat('d', 64), 'v1', 10, "
            "'application/pdf', 'client_upload', 'uploaded') RETURNING id",
            tenant,
            engagement,
            item,
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.run(
                "INSERT INTO ocr_runs (tenant_id, evidence_version_id, provider, api, status, "
                "basis) VALUES ($1, $2, 'textract', 'detect_text', 'refused', 'synthetic')",
                tenant,
                version,
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.run(
                "INSERT INTO extracted_fields (tenant_id, evidence_version_id, form_type, "
                "form_map_version, field_key, label, value_type, value_text, last4, page_no, "
                "bbox, confidence, low_confidence, extractor_kind, extractor_version, match_id) "
                "VALUES ($1, $2, 'irs_notice_header', 'v1', 'notice.tin', 'TIN', 'tin', "
                "'000-00-6789', '6789', 1, '{0,0,1,1}', 0.99, false, 'form_map', 'v1', "
                "'ev:00000000-0000-4000-8000-000000000000#field:notice.tin')",
                tenant,
                version,
            )

    asyncio.run(scenario())


def test_ac_no_list_query_selects_a_sealed_extracted_value() -> None:
    offenders = [
        str(path.relative_to(SRC))
        for path in SRC.rglob("*.py")
        if re.search(r"extracted_fields[\s\S]{0,400}value_sealed", path.read_text())
        and "reveal" not in path.name
        and path.name != "registry.py"  # the column registry declares columns; it runs no query
    ]
    assert offenders == []
