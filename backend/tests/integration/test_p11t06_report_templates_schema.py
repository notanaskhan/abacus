"""P-11-T06 (TASK-2303; SPEC-520 AC-1, AC-3, AC-4; P-11 §4.2 "Migration 2") against Postgres:
migration 0460.

Templates are firm content: every table is tenant-RLS, versions and publications reject UPDATE,
DELETE and TRUNCATE for every role (a correction is a new version; a rollback is a new
publication), a publication names a person and their second factor, and the migration inserts
no row (no template wording ever ships in a migration). Rows are seeded as the superuser; the
app's statements run as `abacus_app` with the tenant set.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import asyncpg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

REVISION = "0460"
_SCRIPTS = ScriptDirectory.from_config(
    Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
)
BEFORE = cast(str, _SCRIPTS.get_revision(REVISION).down_revision)
TABLES = ("report_templates", "report_template_versions", "report_template_publications")
INSERT_ONLY = ("report_template_versions", "report_template_publications")
HASH = "b" * 64


@dataclass(frozen=True)
class Firm:
    tenant_id: uuid.UUID
    user_id: uuid.UUID


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _app(db: sc.Database) -> str:
    return db.app_url.replace("postgresql+asyncpg://", "postgresql://")


async def _sql(db: sc.Database, statement: str, *args: object) -> object:
    conn = await asyncpg.connect(db.superuser_dsn)
    try:
        return await conn.fetchval(statement, *args)
    finally:
        await conn.close()


async def _as_app(db: sc.Database, firm: Firm, statement: str, *args: object) -> object:
    conn = await asyncpg.connect(_app(db))
    try:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.tenant_id', $1, true)", str(firm.tenant_id))
            return await conn.fetchval(statement, *args)
    finally:
        await conn.close()


async def _firm(db: sc.Database) -> Firm:
    tenant_id = uuid.uuid4()
    await _sql(db, "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Templates')", tenant_id)
    subject = f"sub-{uuid.uuid4().hex}"
    user_id = cast(
        uuid.UUID,
        await _sql(
            db,
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ('https://identity.abacus.local', $1, $2, 'Test person') RETURNING id",
            subject,
            f"{subject}@example.test",
        ),
    )
    return Firm(tenant_id, user_id)


async def _template(db: sc.Database, firm: Firm) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await _sql(
            db,
            "INSERT INTO report_templates (tenant_id, family, name, created_by_user_id) "
            "VALUES ($1, 'engagement_letter', $2, $3) RETURNING id",
            firm.tenant_id,
            f"Letter {uuid.uuid4().hex[:6]}",
            firm.user_id,
        ),
    )


async def _version(db: sc.Database, firm: Firm, template_id: uuid.UUID, n: int) -> uuid.UUID:
    body = json.dumps([{"type": "heading", "level": 1, "text": "Engagement letter"}])
    return cast(
        uuid.UUID,
        await _sql(
            db,
            "INSERT INTO report_template_versions (tenant_id, template_id, version_no, "
            "layout_key, body, source, content_sha256, imported_by_user_id) "
            "VALUES ($1, $2, $3, 'letter', $4::jsonb, 'import', $5, $6) RETURNING id",
            firm.tenant_id,
            template_id,
            n,
            body,
            HASH,
            firm.user_id,
        ),
    )


def test_ac1_the_migration_applies_reverses_and_inserts_no_template(db: sc.Database) -> None:
    migrate(db.owner_url, BEFORE, down=True)
    assert asyncio.run(_sql(db, "SELECT to_regclass('public.report_templates')")) is None
    migrate(db.owner_url, "head")
    for statement in (
        "SELECT count(*) FROM report_templates",
        "SELECT count(*) FROM report_template_versions",
        "SELECT count(*) FROM report_template_publications",
    ):
        assert asyncio.run(_sql(db, statement)) == 0
    assert len(_SCRIPTS.get_heads()) == 1


def test_ac1_every_table_is_tenant_scoped_with_forced_rls(db: sc.Database) -> None:
    for table in TABLES:
        row = asyncio.run(
            _sql(
                db,
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class "
                "WHERE relname = $1 AND relnamespace = 'public'::regnamespace",
                table,
            )
        )
        assert row is True, table
    assert sc.check(db.owner_url, db.app_url) == []


@pytest.mark.parametrize("table", INSERT_ONLY)
def test_ac4_versions_and_publications_refuse_update_delete_and_truncate(
    db: sc.Database, table: str
) -> None:
    for privilege in ("UPDATE", "DELETE", "TRUNCATE"):
        granted = asyncio.run(
            _sql(db, "SELECT has_table_privilege('abacus_app', $1, $2)", table, privilege)
        )
        assert granted is False, (table, privilege)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(_sql(db, f"TRUNCATE {table} CASCADE"))


def test_ac4_a_version_once_written_never_changes_for_any_role(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    version = asyncio.run(_version(db, firm, asyncio.run(_template(db, firm)), 1))
    for statement in (
        "UPDATE report_template_versions SET layout_key = 'report' WHERE id = $1",
        "DELETE FROM report_template_versions WHERE id = $1",
    ):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            asyncio.run(_sql(db, statement, version))  # the superuser too
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            asyncio.run(_as_app(db, firm, statement, version))


def test_ac3_a_publication_names_a_person_and_their_second_factor(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    version = asyncio.run(_version(db, firm, asyncio.run(_template(db, firm)), 1))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _as_app(
                db,
                firm,
                "INSERT INTO report_template_publications (tenant_id, version_id, action, "
                "by_user_id) VALUES ($1, $2, 'published', $3)",
                firm.tenant_id,
                version,
                firm.user_id,
            )
        )
    asyncio.run(
        _as_app(
            db,
            firm,
            "INSERT INTO report_template_publications (tenant_id, version_id, action, "
            "by_user_id, mfa_at) VALUES ($1, $2, 'published', $3, now())",
            firm.tenant_id,
            version,
            firm.user_id,
        )
    )


def test_ac1_an_unknown_layout_never_reaches_a_row(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    template = asyncio.run(_template(db, firm))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _sql(
                db,
                "INSERT INTO report_template_versions (tenant_id, template_id, version_no, "
                "layout_key, body, source, content_sha256, imported_by_user_id) "
                "VALUES ($1, $2, 1, 'brochure', '[]'::jsonb, 'import', $3, $4)",
                firm.tenant_id,
                template,
                HASH,
                firm.user_id,
            )
        )


def test_ac1_another_firms_templates_are_invisible(db: sc.Database) -> None:
    a, b = asyncio.run(_firm(db)), asyncio.run(_firm(db))
    asyncio.run(_template(db, a))
    assert asyncio.run(_as_app(db, b, "SELECT count(*) FROM report_templates")) == 0
