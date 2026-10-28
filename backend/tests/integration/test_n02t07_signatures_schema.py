"""N-02-T07 (TASK-1726; N-02 §4.2 "T07", §3.13) against Postgres: migration 0292.

The row's acceptance: the migration applies and reverses on a seeded database, insert-only
triggers refuse UPDATE and DELETE, and the single-head check stays green. Also from §4.2: every
table is tenant-scoped with forced RLS, `sent_by`, `voided_by` and `imported_by` are set only by
the person the transaction names, a final envelope's status never moves, and an e-file
authorization policy keeps KBA and the handwritten fallback. Rows are seeded as the superuser; the
app's statements run as `abacus_app` with the tenant and actor set.
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

from abacus.modules.signatures import registry
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

REVISION = "0292"
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
    await _sql(db, "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Signatures')", tenant_id)
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


_ENVELOPE = (
    "INSERT INTO envelopes (tenant_id, number, purpose, policy_family, client_id, title, "
    "provider, drafted_by_kind, drafted_by) "
    "VALUES ($1, $2, 'engagement_letter', 'engagement_letter', $3, 'Letter', 'fake', 'human', $4) "
    "RETURNING id"
)


async def _envelope(db: sc.Database, firm: Firm, number: int) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await _sql(db, _ENVELOPE, firm.tenant_id, number, firm.client_id, firm.user_id),
    )


async def _signer(db: sc.Database, firm: Firm, envelope_id: uuid.UUID) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await _sql(
            db,
            'INSERT INTO envelope_signers (tenant_id, envelope_id, "order", party_kind, '
            "contact_id, identity_method) VALUES ($1, $2, 1, 'contact', $3, 'email_code') "
            "RETURNING id",
            firm.tenant_id,
            envelope_id,
            firm.contact_id,
        ),
    )


def test_ac_the_migration_applies_and_reverses_on_a_seeded_database(db: sc.Database) -> None:
    migrate(db.owner_url, BEFORE, down=True)
    firm = asyncio.run(_firm(db))
    assert asyncio.run(_sql(db, "SELECT to_regclass('public.envelopes')")) is None
    migrate(db.owner_url, "head")
    envelope = asyncio.run(_envelope(db, firm, 1))
    asyncio.run(_signer(db, firm, envelope))
    migrate(db.owner_url, BEFORE, down=True)
    for table in registry.TABLES:
        assert asyncio.run(_sql(db, f"SELECT to_regclass('public.{table}')")) is None
    assert asyncio.run(_sql(db, "SELECT count(*) FROM clients WHERE id = $1", firm.client_id)) == 1
    migrate(db.owner_url, "head")
    for table in registry.TABLES:
        assert asyncio.run(_sql(db, f"SELECT to_regclass('public.{table}')")) is not None


def test_ac_the_single_head_check_stays_green() -> None:
    assert len(_SCRIPTS.get_heads()) == 1


def test_every_table_is_tenant_scoped_with_forced_rls(db: sc.Database) -> None:
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
def test_ac_insert_only_tables_refuse_update_delete_and_truncate(
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
            "WHERE t.tgrelid = $1::regclass AND p.proname = 'signatures_rows_immutable'",
            table,
        )
    )
    assert triggers == 2  # row UPDATE or DELETE, and statement TRUNCATE
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(_sql(db, f"TRUNCATE {table}"))


def test_ac_an_envelope_event_once_written_is_never_changed(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    envelope = asyncio.run(_envelope(db, firm, 1))
    event = asyncio.run(
        _sql(
            db,
            "INSERT INTO envelope_events (tenant_id, envelope_id, kind, source, occurred_at) "
            "VALUES ($1, $2, 'envelope.created', 'firm', now()) RETURNING id",
            firm.tenant_id,
            envelope,
        )
    )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(_sql(db, "UPDATE envelope_events SET kind = 'x.y' WHERE id = $1", event))
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(_sql(db, "DELETE FROM envelope_events WHERE id = $1", event))
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(
            _as_app(db, firm, "UPDATE envelope_events SET kind = 'x.y' WHERE id = $1", event)
        )


def test_another_firms_envelopes_are_invisible(db: sc.Database) -> None:
    a, b = asyncio.run(_firm(db)), asyncio.run(_firm(db))
    asyncio.run(_envelope(db, a, 1))
    assert asyncio.run(_as_app(db, b, "SELECT count(*) FROM envelopes")) == 0
    assert asyncio.run(_as_app(db, a, "SELECT count(*) FROM envelopes")) == 1


def test_sent_by_is_the_person_the_transaction_names(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    envelope = asyncio.run(_envelope(db, firm, 1))
    send = (
        "UPDATE envelopes SET status = 'sent', sent_by = $2, sent_at = now() WHERE id = $1 "
        "RETURNING status"
    )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(_as_app(db, firm, send, envelope, firm.user_id, actor_kind="agent"))
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(_as_app(db, firm, send, envelope, firm.user_id, actor_id=str(uuid.uuid4())))
    assert asyncio.run(_as_app(db, firm, send, envelope, firm.user_id)) == "sent"
    # A later system update (a webhook's viewed) keeps the sender and passes.
    viewed = "UPDATE envelopes SET status = 'viewed' WHERE id = $1 RETURNING status"
    assert asyncio.run(_as_app(db, firm, viewed, envelope, actor_kind="system")) == "viewed"


def test_an_agent_can_never_import_or_void(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    imported = (
        "INSERT INTO envelopes (tenant_id, number, purpose, policy_family, client_id, title, "
        "provider, provider_name, drafted_by_kind, imported_by) "
        "VALUES ($1, 9, 'engagement_letter', 'engagement_letter', $2, 'Signed letter', "
        "'record', 'DocuSign', 'human', $3) RETURNING id"
    )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(
            _as_app(
                db,
                firm,
                imported,
                firm.tenant_id,
                firm.client_id,
                firm.user_id,
                actor_kind="agent",
            )
        )
    envelope = asyncio.run(_envelope(db, firm, 2))
    void = (
        "UPDATE envelopes SET status = 'voided', voided_by = $2, voided_at = now(), "
        "void_reason = 'replaced' WHERE id = $1 RETURNING status"
    )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(_as_app(db, firm, void, envelope, firm.user_id, actor_kind="agent"))
    assert asyncio.run(_as_app(db, firm, void, envelope, firm.user_id)) == "voided"


def test_a_voided_envelope_needs_a_reason_and_never_moves_again(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    envelope = asyncio.run(_envelope(db, firm, 1))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _as_app(
                db,
                firm,
                "UPDATE envelopes SET status = 'voided', voided_by = $2, voided_at = now() "
                "WHERE id = $1",
                envelope,
                firm.user_id,
            )
        )
    asyncio.run(
        _as_app(
            db,
            firm,
            "UPDATE envelopes SET status = 'voided', voided_by = $2, voided_at = now(), "
            "void_reason = 'other' WHERE id = $1",
            envelope,
            firm.user_id,
        )
    )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(
            _as_app(db, firm, "UPDATE envelopes SET status = 'sent' WHERE id = $1", envelope)
        )


def test_an_efile_authorization_policy_keeps_kba_and_the_handwritten_fallback(
    db: sc.Database,
) -> None:
    firm = asyncio.run(_firm(db))
    policy = (
        "INSERT INTO envelope_policies (tenant_id, policy_family, allowed_identity_methods, "
        "default_identity_method) VALUES ($1, 'efile_authorization', $2, $3) RETURNING id"
    )
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_sql(db, policy, firm.tenant_id, ["email_code"], "email_code"))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_sql(db, policy, firm.tenant_id, ["sms_code"], "sms_code"))
    assert asyncio.run(_sql(db, policy, firm.tenant_id, ["kba"], "kba")) is not None


def test_a_signer_fails_kba_at_most_three_times(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    signer = asyncio.run(_signer(db, firm, asyncio.run(_envelope(db, firm, 1))))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(_sql(db, "UPDATE envelope_signers SET kba_failures = 4 WHERE id = $1", signer))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _sql(
                db,
                "UPDATE envelope_signers SET status = 'verification_failed' WHERE id = $1",
                signer,
            )
        )


def test_a_signing_session_lasts_five_minutes_at_most(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    envelope = asyncio.run(_envelope(db, firm, 1))
    signer = asyncio.run(_signer(db, firm, envelope))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _sql(
                db,
                "INSERT INTO signing_sessions (tenant_id, envelope_id, signer_id, principal_id, "
                "presentation, issued_at, expires_at, return_token_hash) VALUES ($1, $2, $3, $4, "
                "'iframe', now(), now() + interval '6 minutes', $5)",
                firm.tenant_id,
                envelope,
                signer,
                uuid.uuid4(),
                "0" * 64,
            )
        )
