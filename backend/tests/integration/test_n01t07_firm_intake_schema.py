"""N-01-T07 (TASK-1727; N-01 §4.2 "T07") against Postgres: migration 0293.

The row's acceptance: upgrade and downgrade pass, and an UPDATE or a non-human insert on
`triage_decisions` is refused by the database. Also from §4.2: messages and flags are
insert-only, every table is tenant-scoped with forced RLS, and a thread is matched exactly when it
names a client. Rows are seeded as the superuser; the app's statements run as `abacus_app` with the
tenant and actor set.
"""

from __future__ import annotations

import asyncio
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

REVISION = "0293"
_SCRIPTS = ScriptDirectory.from_config(
    Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
)
BEFORE = cast(str, _SCRIPTS.get_revision(REVISION).down_revision)


@dataclass(frozen=True)
class Firm:
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    client_id: uuid.UUID
    contact_id: uuid.UUID


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


async def _as_app(
    db: sc.Database,
    firm: Firm,
    statement: str,
    *args: object,
    actor_kind: str = "human",
    actor_id: str | None = None,
) -> object:
    conn = await asyncpg.connect(_app(db))
    try:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.tenant_id', $1, true)", str(firm.tenant_id))
            await conn.execute("SELECT set_config('app.actor_kind', $1, true)", actor_kind)
            await conn.execute(
                "SELECT set_config('app.actor_id', $1, true)", actor_id or str(firm.user_id)
            )
            return await conn.fetchval(statement, *args)
    finally:
        await conn.close()


async def _firm(db: sc.Database) -> Firm:
    tenant_id = uuid.uuid4()
    await _sql(db, "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Intake')", tenant_id)
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
    contact_id = cast(
        uuid.UUID,
        await _sql(
            db,
            "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind) "
            "VALUES ($1, $2, 'Signer', 'client_person') "
            "RETURNING id",
            tenant_id,
            client_id,
        ),
    )
    return Firm(tenant_id, user_id, client_id, contact_id)


_TABLES = (
    "inbox_threads",
    "inbound_messages",
    "inbox_attachments",
    "triage_decisions",
    "inbox_sender_rules",
    "inbox_attachment_flags",
)
_INSERT_ONLY = ("inbound_messages", "triage_decisions", "inbox_attachment_flags")


async def _attachment(db: sc.Database, firm: Firm) -> tuple[uuid.UUID, uuid.UUID]:
    thread = cast(
        uuid.UUID,
        await _sql(
            db,
            "INSERT INTO inbox_threads (tenant_id, source_kind, subject_display, sender_display, "
            "first_received_at, last_received_at) VALUES ($1, 'mailbox', '1099s', "
            "'Feliks', now(), now()) RETURNING id",
            firm.tenant_id,
        ),
    )
    message = await _sql(
        db,
        "INSERT INTO inbound_messages (tenant_id, thread_id, channel, sender_display, "
        "subject_display, received_at) VALUES ($1, $2, 'email', 'Feliks', '1099s', now()) "
        "RETURNING id",
        firm.tenant_id,
        thread,
    )
    attachment = cast(
        uuid.UUID,
        await _sql(
            db,
            "INSERT INTO inbox_attachments (tenant_id, message_id, thread_id, file_name, "
            "media_type, size_bytes, fingerprint, storage_key, key_mode) VALUES ($1, $2, $3, "
            "'1099-B.pdf', 'application/pdf', 10, $4, 'intake/k', 'content') RETURNING id",
            firm.tenant_id,
            message,
            thread,
            "a" * 64,
        ),
    )
    return thread, attachment


_HOLD = (
    "INSERT INTO triage_decisions (tenant_id, attachment_id, thread_id, decision) "
    "VALUES ($1, $2, $3, 'hold') RETURNING id"
)


def test_ac_upgrade_and_downgrade_pass(db: sc.Database) -> None:
    migrate(db.owner_url, BEFORE, down=True)
    for table in _TABLES:
        assert asyncio.run(_sql(db, f"SELECT to_regclass('public.{table}')")) is None
    migrate(db.owner_url, "head")
    firm = asyncio.run(_firm(db))
    asyncio.run(_attachment(db, firm))
    migrate(db.owner_url, BEFORE, down=True)
    assert asyncio.run(_sql(db, "SELECT count(*) FROM clients WHERE id = $1", firm.client_id)) == 1
    migrate(db.owner_url, "head")
    assert sc.check(db.owner_url, db.app_url) == []


def test_ac_a_non_human_insert_on_triage_decisions_is_refused(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    thread, attachment = asyncio.run(_attachment(db, firm))
    for kind in ("agent", "system", "policy"):
        with pytest.raises(asyncpg.CheckViolationError):
            asyncio.run(
                _as_app(db, firm, _HOLD, firm.tenant_id, attachment, thread, actor_kind=kind)
            )
    assert asyncio.run(_as_app(db, firm, _HOLD, firm.tenant_id, attachment, thread)) is not None


def test_ac_an_update_on_triage_decisions_is_refused(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    thread, attachment = asyncio.run(_attachment(db, firm))
    decision = asyncio.run(_as_app(db, firm, _HOLD, firm.tenant_id, attachment, thread))
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(
            _as_app(
                db, firm, "UPDATE triage_decisions SET decision = 'file' WHERE id = $1", decision
            )
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(
            _sql(db, "UPDATE triage_decisions SET keep_both = true WHERE id = $1", decision)
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(_sql(db, "DELETE FROM triage_decisions WHERE id = $1", decision))


@pytest.mark.parametrize("table", _INSERT_ONLY)
def test_insert_only_tables_refuse_update_delete_and_truncate(db: sc.Database, table: str) -> None:
    for privilege in ("UPDATE", "DELETE", "TRUNCATE"):
        granted = asyncio.run(
            _sql(db, "SELECT has_table_privilege('abacus_app', $1, $2)", table, privilege)
        )
        assert granted is False, (table, privilege)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(_sql(db, f"TRUNCATE {table}"))


def test_a_thread_is_matched_exactly_when_it_names_a_client(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    thread, _ = asyncio.run(_attachment(db, firm))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _as_app(
                db,
                firm,
                "UPDATE inbox_threads SET match_method = 'contact_email' WHERE id = $1",
                thread,
            )
        )
    matched = asyncio.run(
        _as_app(
            db,
            firm,
            "UPDATE inbox_threads SET client_id = $2, match_method = 'manual', matched_by = $3, "
            "matched_at = now() WHERE id = $1 RETURNING match_method",
            thread,
            firm.client_id,
            firm.user_id,
        )
    )
    assert matched == "manual"


def test_another_firms_inbox_is_invisible(db: sc.Database) -> None:
    a, b = asyncio.run(_firm(db)), asyncio.run(_firm(db))
    asyncio.run(_attachment(db, a))
    assert asyncio.run(_as_app(db, b, "SELECT count(*) FROM inbox_threads")) == 0
    assert asyncio.run(_as_app(db, b, "SELECT count(*) FROM inbox_attachments")) == 0
