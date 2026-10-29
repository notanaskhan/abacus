"""K-02-T04 (TASK-2103; SPEC-500 AC-11, AC-12; K-02 US-3.2, US-3.3) against Postgres: migration
0401, firm standards and threshold policies.

The row's acceptance: generated tenancy tests pass (`tests/security/test_tenant_isolation.py`
lists the four tables) and trigger tests show a published version cannot change and a second
draft is refused. Also: versions are numbered 1, 2, 3 per parent; a draft moves only to
published or discarded; publishing needs `published_actor_kind = 'human'` and a person's session;
nothing is ever deleted; the app has no DELETE.

Values are synthetic probes, never a firm's standard (AGENTS 16).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import cast

import asyncpg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from abacus.kernel._statuses import FirmStandardVersionStatus, ReferenceSetVersionStatus
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

REVISION = "0401"
_SCRIPTS = ScriptDirectory.from_config(
    Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
)
BEFORE = cast(str, _SCRIPTS.get_revision(REVISION).down_revision)
PAIRS = (
    ("firm_standards", "firm_standard_versions", "review_levels"),
    ("threshold_policies", "threshold_policy_versions", "aje_thresholds"),
)
PAYLOAD = json.dumps({"kind": "probe"})
HASH = "sha256:" + hashlib.sha256(PAYLOAD.encode()).hexdigest()


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


class Firm:
    def __init__(self, tenant_id: uuid.UUID, partner: uuid.UUID) -> None:
        self.tenant_id = tenant_id
        self.partner = partner


@pytest.fixture
async def firm(db: sc.Database) -> Firm:
    conn = await asyncpg.connect(db.superuser_dsn)
    try:
        tenant_id = uuid.uuid4()
        await conn.execute("INSERT INTO firms (tenant_id, name) VALUES ($1, 'K02')", tenant_id)
        subject = f"sub-{uuid.uuid4().hex}"
        user_id = cast(
            uuid.UUID,
            await conn.fetchval(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ('https://identity.abacus.local', $1, $2, 'Probe partner') RETURNING id",
                subject,
                f"{subject}@example.test",
            ),
        )
        await conn.execute(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
            "VALUES ($1, $2, 'quality_partner', 'active')",
            tenant_id,
            user_id,
        )
        return Firm(tenant_id, user_id)
    finally:
        await conn.close()


@pytest.fixture
async def app(db: sc.Database) -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(_dsn(db.app_url))
    try:
        yield conn
    finally:
        await conn.close()


async def _as(conn: asyncpg.Connection, firm: Firm, actor_kind: str = "human") -> None:
    await conn.execute("SELECT set_config('app.tenant_id', $1, false)", str(firm.tenant_id))
    await conn.execute("SELECT set_config('app.actor_kind', $1, false)", actor_kind)
    await conn.execute("SELECT set_config('app.actor_id', $1, false)", str(firm.partner))


async def _standard(conn: asyncpg.Connection, firm: Firm, parent: str, kind: str) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await conn.fetchval(
            f"INSERT INTO {parent} (tenant_id, kind, key, name, owner_id, created_by) "  # noqa: S608 -- fixed names
            "VALUES ($1, $2, $3, 'Probe standard', $4, $4) RETURNING id",
            firm.tenant_id,
            kind,
            f"probe-{uuid.uuid4().hex[:8]}",
            firm.partner,
        ),
    )


async def _draft(
    conn: asyncpg.Connection, firm: Firm, versions: str, parent_id: uuid.UUID, version: int
) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await conn.fetchval(
            f"INSERT INTO {versions} (tenant_id, parent_id, version, payload, payload_hash, "  # noqa: S608 -- fixed names
            "drafted_by) VALUES ($1, $2, $3, $4::jsonb, $5, $6) RETURNING id",
            firm.tenant_id,
            parent_id,
            version,
            PAYLOAD,
            HASH,
            firm.partner,
        ),
    )


async def _publish(conn: asyncpg.Connection, firm: Firm, versions: str, vid: uuid.UUID) -> None:
    await conn.execute(
        f"UPDATE {versions} SET status = 'published', effective_from = '2026-10-01', "  # noqa: S608 -- fixed names
        "published_by = $2, published_actor_kind = 'human', published_at = now() WHERE id = $1",
        vid,
        firm.partner,
    )


def test_the_migration_passes_up_down_up(db: sc.Database) -> None:
    migrate(db.owner_url, BEFORE, down=True)
    migrate(db.owner_url, "head")
    migrate(db.owner_url, BEFORE, down=True)
    migrate(db.owner_url, "head")
    assert sc.check(db.owner_url, db.app_url) == []


@pytest.mark.parametrize(("parent", "versions", "kind"), PAIRS)
async def test_ac11_a_published_version_cannot_change(
    app: asyncpg.Connection, firm: Firm, parent: str, versions: str, kind: str
) -> None:
    await _as(app, firm)
    standard = await _standard(app, firm, parent, kind)
    v1 = await _draft(app, firm, versions, standard, 1)
    await _publish(app, firm, versions, v1)
    for change in (
        "SET payload = '{}'::jsonb",
        "SET effective_from = '2030-01-01'",
        "SET status = 'discarded', published_by = NULL, published_actor_kind = NULL, "
        "published_at = NULL",
    ):
        statement = f"UPDATE {versions} {change} WHERE id = $1"
        with pytest.raises(asyncpg.PostgresError, match="version_frozen"):
            await app.execute(statement, v1)


@pytest.mark.parametrize(("parent", "versions", "kind"), PAIRS)
async def test_ac11_a_second_draft_is_refused(
    app: asyncpg.Connection, firm: Firm, parent: str, versions: str, kind: str
) -> None:
    await _as(app, firm)
    standard = await _standard(app, firm, parent, kind)
    await _draft(app, firm, versions, standard, 1)
    with pytest.raises(asyncpg.UniqueViolationError):
        await _draft(app, firm, versions, standard, 2)


@pytest.mark.parametrize(("parent", "versions", "kind"), PAIRS)
async def test_ac11_versions_are_numbered_in_order(
    app: asyncpg.Connection, firm: Firm, parent: str, versions: str, kind: str
) -> None:
    await _as(app, firm)
    standard = await _standard(app, firm, parent, kind)
    with pytest.raises(asyncpg.CheckViolationError, match="version_not_next"):
        await _draft(app, firm, versions, standard, 2)
    v1 = await _draft(app, firm, versions, standard, 1)
    await _publish(app, firm, versions, v1)
    with pytest.raises(asyncpg.CheckViolationError, match="version_not_next"):
        await _draft(app, firm, versions, standard, 3)
    assert await _draft(app, firm, versions, standard, 2)


@pytest.mark.parametrize(("parent", "versions", "kind"), PAIRS)
async def test_us33_publishing_is_a_persons(
    app: asyncpg.Connection, firm: Firm, parent: str, versions: str, kind: str
) -> None:
    await _as(app, firm)
    standard = await _standard(app, firm, parent, kind)
    v1 = await _draft(app, firm, versions, standard, 1)
    # The CHECK: no other actor kind is ever stored.
    with pytest.raises(asyncpg.CheckViolationError):
        await app.execute(
            f"UPDATE {versions} SET status = 'published', effective_from = '2026-10-01', "  # noqa: S608 -- fixed names
            "published_by = $2, published_actor_kind = 'agent', published_at = now() "
            "WHERE id = $1",
            v1,
            firm.partner,
        )
    # The trigger: an agent's session cannot publish, even writing 'human'.
    await _as(app, firm, actor_kind="agent")
    with pytest.raises(asyncpg.PostgresError, match="publisher_not_human"):
        await _publish(app, firm, versions, v1)
    await _as(app, firm)
    await _publish(app, firm, versions, v1)


@pytest.mark.parametrize(("parent", "versions", "kind"), PAIRS)
async def test_ac11_nothing_is_deleted_and_a_draft_may_be_discarded(
    app: asyncpg.Connection, firm: Firm, parent: str, versions: str, kind: str
) -> None:
    await _as(app, firm)
    standard = await _standard(app, firm, parent, kind)
    v1 = await _draft(app, firm, versions, standard, 1)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await app.execute(f"DELETE FROM {versions} WHERE id = $1", v1)  # noqa: S608 -- fixed names
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await app.execute(f"DELETE FROM {parent} WHERE id = $1", standard)  # noqa: S608 -- fixed names
    await app.execute(f"UPDATE {versions} SET status = 'discarded' WHERE id = $1", v1)  # noqa: S608 -- fixed names
    with pytest.raises(asyncpg.PostgresError, match="version_frozen"):
        await app.execute(f"UPDATE {versions} SET status = 'draft' WHERE id = $1", v1)  # noqa: S608 -- fixed names


def test_ac12_the_status_registry_has_both_version_objects() -> None:
    assert {s.value for s in FirmStandardVersionStatus} == {
        "draft",
        "published",
        "superseded",
        "discarded",
    }
    assert {s.value for s in ReferenceSetVersionStatus} == {
        "draft",
        "published",
        "superseded",
        "withdrawn",
    }
