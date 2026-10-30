"""T-01-T08 (TASK-2109; SPEC-501 AC-15, AC-16; T-01 §3.1, §4.2) against Postgres: migration 0402,
the §7216 consents.

The row's acceptance: generated tenancy tests pass for the four tables (`tests/security/
test_tenant_isolation.py`), one purpose per consent with at least one tax year, a second open
request for a declined purpose is refused, and events are insert-only. Also up/down/up, and the app
never deletes a consent. Values are synthetic probes.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import cast

import asyncpg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

REVISION = "0402"
_SCRIPTS = ScriptDirectory.from_config(
    Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
)
BEFORE = cast(str, _SCRIPTS.get_revision(REVISION).down_revision)
SHA = hashlib.sha256(b"probe consent text").digest()
INSERT_CONSENT = (
    "INSERT INTO consents (tenant_id, client_id, client_entity_id, purpose, tax_years, "
    "provider_terms_version, template_version_id, text_sha256, source, status, created_by, "
    "declined_at) VALUES ($1, $2, $3, $4, $5, 'v1', gen_random_uuid(), $6, 'record', $7, $8, "
    "CASE WHEN $7 = 'declined' THEN now() END) RETURNING id"
)


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


class Firm:
    def __init__(
        self, tenant: uuid.UUID, user: uuid.UUID, client: uuid.UUID, entity: uuid.UUID
    ) -> None:
        self.tenant, self.user, self.client, self.entity = tenant, user, client, entity


@pytest.fixture
async def firm(db: sc.Database) -> Firm:
    conn = await asyncpg.connect(db.superuser_dsn)
    try:
        tenant = uuid.uuid4()
        await conn.execute("INSERT INTO firms (tenant_id, name) VALUES ($1, 'T01')", tenant)
        subject = f"sub-{uuid.uuid4().hex}"
        user = cast(
            uuid.UUID,
            await conn.fetchval(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ('https://identity.abacus.local', $1, $2, 'Probe') RETURNING id",
                subject,
                f"{subject}@example.test",
            ),
        )
        await conn.execute(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
            "VALUES ($1, $2, 'firm_admin', 'active')",
            tenant,
            user,
        )
        client = cast(
            uuid.UUID,
            await conn.fetchval(
                "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Probe client') RETURNING id",
                tenant,
            ),
        )
        entity = cast(
            uuid.UUID,
            await conn.fetchval(
                "INSERT INTO client_entities (tenant_id, client_id, name) "
                "VALUES ($1, $2, 'Probe taxpayer') RETURNING id",
                tenant,
                client,
            ),
        )
        return Firm(tenant, user, client, entity)
    finally:
        await conn.close()


@pytest.fixture
async def app(db: sc.Database, firm: Firm) -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(_dsn(db.app_url))
    await conn.execute("SELECT set_config('app.tenant_id', $1, false)", str(firm.tenant))
    try:
        yield conn
    finally:
        await conn.close()


async def _consent(
    conn: asyncpg.Connection, firm: Firm, purpose: str, years: list[int], status: str
) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await conn.fetchval(
            INSERT_CONSENT,
            firm.tenant,
            firm.client,
            firm.entity,
            purpose,
            years,
            SHA,
            status,
            firm.user,
        ),
    )


def test_ac16_the_migration_passes_up_down_up(db: sc.Database) -> None:
    migrate(db.owner_url, BEFORE, down=True)
    migrate(db.owner_url, "head")
    migrate(db.owner_url, BEFORE, down=True)
    migrate(db.owner_url, "head")
    assert sc.check(db.owner_url, db.app_url) == []


async def test_ac15_one_purpose_and_at_least_one_year(app: asyncpg.Connection, firm: Firm) -> None:
    assert await _consent(app, firm, "use", [2025], "requested")
    with pytest.raises(asyncpg.CheckViolationError):
        await _consent(app, firm, "use_and_disclosure", [2025], "requested")
    with pytest.raises(asyncpg.CheckViolationError):
        await _consent(app, firm, "ai_disclosure", [], "requested")


async def test_ac15_a_declined_purpose_is_not_requested_again(
    app: asyncpg.Connection, firm: Firm
) -> None:
    await _consent(app, firm, "ai_disclosure", [2025], "declined")
    with pytest.raises(asyncpg.UniqueViolationError):
        await _consent(app, firm, "ai_disclosure", [2025], "requested")
    # Another year is another request.
    assert await _consent(app, firm, "ai_disclosure", [2026], "requested")


async def test_ac15_events_are_insert_only_and_nothing_is_deleted(
    app: asyncpg.Connection, firm: Firm
) -> None:
    consent = await _consent(app, firm, "use", [2024], "requested")
    await app.execute(
        "INSERT INTO consent_events (tenant_id, consent_id, kind, actor_kind, actor_id) "
        "VALUES ($1, $2, 'requested', 'human', $3)",
        firm.tenant,
        consent,
        str(firm.user),
    )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await app.execute(
            "UPDATE consent_events SET kind = 'signed' WHERE consent_id = $1", consent
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await app.execute("DELETE FROM consents WHERE id = $1", consent)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await app.execute("UPDATE consents SET purpose = 'firm_defined' WHERE id = $1", consent)
