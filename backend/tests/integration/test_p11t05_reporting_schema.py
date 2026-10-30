"""P-11-T05 (TASK-2207; SPEC-520 AC-33, AC-27, AC-15, AC-16; P-11 §4.2) against Postgres:
migration 0430.

The row's acceptance: every table is tenant-RLS, versions, files, fields and events reject UPDATE
and DELETE for every role, the mode CHECKs hold, and the single-head check passes. Also from §4.2:
a final version is a person's with the approval it rests on (its content hash), an agent's
request is a draft naming its run, a file is evidence or a sample (never both, never neither),
and an out-of-date event names keys, not values. Rows are seeded as the superuser; the app's
statements run as `abacus_app` with the tenant set.
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

from abacus.modules.reporting import registry
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

REVISION = "0430"
_SCRIPTS = ScriptDirectory.from_config(
    Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
)
BEFORE = cast(str, _SCRIPTS.get_revision(REVISION).down_revision)
HASH = "a" * 64


@dataclass(frozen=True)
class Firm:
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    client_id: uuid.UUID


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
    await _sql(db, "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Reporting')", tenant_id)
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
    await _sql(
        db,
        "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
        "VALUES ($1, $2, NULL, 'active')",
        tenant_id,
        user_id,
    )
    client_id = cast(
        uuid.UUID,
        await _sql(
            db, "INSERT INTO clients (tenant_id, name) VALUES ($1, 'C') RETURNING id", tenant_id
        ),
    )
    return Firm(tenant_id, user_id, client_id)


async def _document(db: sc.Database, firm: Firm) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await _sql(
            db,
            "INSERT INTO generated_documents (tenant_id, kind, owner_type, owner_id, client_id, "
            "created_by_kind) VALUES ($1, 'engagement_letter', 'engagement_letter', $2, $3, "
            "'human') RETURNING id",
            firm.tenant_id,
            uuid.uuid4(),
            firm.client_id,
        ),
    )


_VERSION = (
    "INSERT INTO generated_document_versions (tenant_id, generated_document_id, version_no, mode, "
    "template_version_id, layout_key, layout_version, snapshot_key, snapshot_sha256, "
    "content_hash, engine_version, approval_ref, requested_by_kind, requested_by_user_id, "
    "requested_by_run_id) VALUES ($1, $2, $3, $4, $5, 'letter', 1, 'snap/1', $6, $6, "
    "'weasyprint 70.0', $7::jsonb, $8, $9, $10) RETURNING id"
)


async def _version(
    db: sc.Database,
    firm: Firm,
    document: uuid.UUID,
    n: int,
    *,
    mode: str = "draft",
    approval: dict[str, str] | None = None,
    kind: str = "human",
    run: uuid.UUID | None = None,
    content_hash: str = HASH,
) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await _sql(
            db,
            _VERSION,
            firm.tenant_id,
            document,
            n,
            mode,
            uuid.uuid4(),
            content_hash,
            None if approval is None else json.dumps(approval),
            kind,
            firm.user_id if kind == "human" else None,
            run,
        ),
    )


def _approval(firm: Firm, content_hash: str = HASH) -> dict[str, str]:
    return {
        "kind": "letter_approval",
        "id": str(uuid.uuid4()),
        "content_hash": content_hash,
        "approver_user_id": str(firm.user_id),
    }


def test_ac33_the_migration_applies_and_reverses_on_a_seeded_database(db: sc.Database) -> None:
    migrate(db.owner_url, BEFORE, down=True)
    firm = asyncio.run(_firm(db))
    assert asyncio.run(_sql(db, "SELECT to_regclass('public.generated_documents')")) is None
    migrate(db.owner_url, "head")
    document = asyncio.run(_document(db, firm))
    asyncio.run(_version(db, firm, document, 1))
    migrate(db.owner_url, BEFORE, down=True)
    for table in registry.TABLES:
        assert asyncio.run(_sql(db, f"SELECT to_regclass('public.{table}')")) is None
    assert asyncio.run(_sql(db, "SELECT count(*) FROM clients WHERE id = $1", firm.client_id)) == 1
    migrate(db.owner_url, "head")
    for table in registry.TABLES:
        assert asyncio.run(_sql(db, f"SELECT to_regclass('public.{table}')")) is not None


def test_ac33_the_single_head_check_stays_green() -> None:
    assert len(_SCRIPTS.get_heads()) == 1


def test_ac33_every_table_is_tenant_scoped_with_forced_rls(db: sc.Database) -> None:
    for table in registry.TABLES:
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


@pytest.mark.parametrize("table", sorted(registry.INSERT_ONLY))
def test_ac27_insert_only_tables_refuse_update_delete_and_truncate(
    db: sc.Database, table: str
) -> None:
    for privilege in ("UPDATE", "DELETE", "TRUNCATE"):
        granted = asyncio.run(
            _sql(db, "SELECT has_table_privilege('abacus_app', $1, $2)", table, privilege)
        )
        assert granted is False, (table, privilege)
    triggers = asyncio.run(
        _sql(
            db,
            "SELECT count(*) FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid "
            "WHERE t.tgrelid = $1::regclass AND p.proname = 'reporting_rows_immutable'",
            table,
        )
    )
    assert triggers == 2  # row UPDATE or DELETE, and statement TRUNCATE
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(_sql(db, f"TRUNCATE {table} CASCADE"))


def test_ac27_a_version_once_written_is_never_changed_by_any_role(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    version = asyncio.run(_version(db, firm, asyncio.run(_document(db, firm)), 1))
    for statement in (
        "UPDATE generated_document_versions SET mode = 'final' WHERE id = $1",
        "DELETE FROM generated_document_versions WHERE id = $1",
    ):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            asyncio.run(_sql(db, statement, version))  # the superuser too
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            asyncio.run(_as_app(db, firm, statement, version))


def test_ac33_another_firms_documents_are_invisible(db: sc.Database) -> None:
    a, b = asyncio.run(_firm(db)), asyncio.run(_firm(db))
    asyncio.run(_document(db, a))
    assert asyncio.run(_as_app(db, b, "SELECT count(*) FROM generated_documents")) == 0
    assert asyncio.run(_as_app(db, a, "SELECT count(*) FROM generated_documents")) == 1


def test_ac15_a_final_version_needs_an_approval_and_a_person(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    document = asyncio.run(_document(db, firm))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_version(db, firm, document, 1, mode="final"))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _version(db, firm, document, 1, mode="final", approval=_approval(firm), kind="system")
        )
    asyncio.run(_version(db, firm, document, 1, mode="final", approval=_approval(firm)))


def test_ac15_the_approval_names_this_versions_content_hash(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    document = asyncio.run(_document(db, firm))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _version(
                db,
                firm,
                document,
                1,
                mode="final",
                approval=_approval(firm, content_hash="b" * 64),
            )
        )


def test_ac16_an_agents_request_is_a_draft_that_names_its_run(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    document = asyncio.run(_document(db, firm))
    run = uuid.uuid4()
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_version(db, firm, document, 1, kind="agent"))  # no run
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _version(
                db,
                firm,
                document,
                1,
                mode="final",
                approval=_approval(firm),
                kind="agent",
                run=run,
            )
        )
    asyncio.run(_version(db, firm, document, 1, kind="agent", run=run))


def test_ac25_a_file_is_evidence_or_a_sample_never_both(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    version = asyncio.run(_version(db, firm, asyncio.run(_document(db, firm)), 1))
    insert = (
        "INSERT INTO generated_document_files (tenant_id, version_id, format, "
        "evidence_version_id, sample_object_key, render_hash, page_count, byte_size) "
        "VALUES ($1, $2, $3, $4, $5, $6, 3, 1024)"
    )
    digest = bytes(32)
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_sql(db, insert, firm.tenant_id, version, "pdf", None, None, digest))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _sql(db, insert, firm.tenant_id, version, "pdf", uuid.uuid4(), "sample/1", digest)
        )
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_sql(db, insert, firm.tenant_id, version, "pdf", uuid.uuid4(), None, b"x"))
    asyncio.run(_sql(db, insert, firm.tenant_id, version, "pdf", uuid.uuid4(), None, digest))


def test_out_of_date_names_keys_never_values(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    document = asyncio.run(_document(db, firm))
    insert = (
        "INSERT INTO generated_document_events (tenant_id, generated_document_id, kind, "
        "cause_ref, changed_keys, actor_kind) VALUES ($1, $2, 'out_of_date', 'engagement.fee', "
        "$3, 'system')"
    )
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_sql(db, insert, firm.tenant_id, document, None))
    asyncio.run(_sql(db, insert, firm.tenant_id, document, ["engagement.monthly_fee"]))


def test_render_jobs_move_only_through_their_state_columns(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    document = asyncio.run(_document(db, firm))
    job = asyncio.run(
        _as_app(
            db,
            firm,
            "INSERT INTO render_jobs (tenant_id, generated_document_id, target_version_no, "
            "workflow_id) VALUES ($1, $2, 1, 'render:t:d:1') RETURNING id",
            firm.tenant_id,
            document,
        )
    )
    asyncio.run(_as_app(db, firm, "UPDATE render_jobs SET status = 'running' WHERE id = $1", job))
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(
            _as_app(db, firm, "UPDATE render_jobs SET target_version_no = 2 WHERE id = $1", job)
        )
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _as_app(
                db,
                firm,
                "UPDATE render_jobs SET status = 'failed', finished_at = now() WHERE id = $1",
                job,
            )
        )
