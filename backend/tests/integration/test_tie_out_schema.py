"""A-02-T11 (TASK-1337; SPEC-333 AC-10): `tie_out_checks` and its insert-only versions after
migration 0193.

The row's acceptance: the migration passes up/down/up, and a version row with an expected value
but no citation id is refused by CHECK. A-02 §4.2 adds: a balanced check carries no expected
value, a version is never updated or deleted (by any role), only a human defines one, and the
issue link is whole and in the firm. Rows are seeded as the superuser; what must fail for the
app runs as `abacus_app` with the tenant set, as `tenant_session` would.
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

REVISION = "0193"
_SCRIPTS = ScriptDirectory.from_config(
    Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
)
BEFORE = cast(str, _SCRIPTS.get_revision(REVISION).down_revision)
SELECTOR = json.dumps({"total": "net_assets", "column": "eoy", "layer": "unadjusted"})
EXPECTED = json.dumps({"value": "16812400.00"})


@dataclass(frozen=True)
class Firm:
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    engagement_id: uuid.UUID


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _sql(db: sc.Database, statement: str, *args: object) -> object:
    conn = await asyncpg.connect(db.superuser_dsn)
    try:
        return await conn.fetchval(statement, *args)
    finally:
        await conn.close()


async def _firm(db: sc.Database) -> Firm:
    tenant_id = uuid.uuid4()
    await _sql(db, "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Ties')", tenant_id)
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
    client_id = await _sql(
        db, "INSERT INTO clients (tenant_id, name) VALUES ($1, 'C') RETURNING id", tenant_id
    )
    entity_id = await _sql(
        db,
        "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, 'E') "
        "RETURNING id",
        tenant_id,
        client_id,
    )
    engagement_id = cast(
        uuid.UUID,
        await _sql(
            db,
            "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
            "fiscal_period_start, fiscal_period_end, created_by) "
            "VALUES ($1, $2, $3, 'Audit', '2025-07-01', '2026-06-30', $4) RETURNING id",
            tenant_id,
            client_id,
            entity_id,
            user_id,
        ),
    )
    return Firm(tenant_id, user_id, engagement_id)


async def _check(db: sc.Database, firm: Firm, kind: str) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await _sql(
            db,
            "INSERT INTO tie_out_checks (tenant_id, engagement_id, target_type, target_id, key, "
            "kind, created_by) VALUES ($1, $2, 'trial_balance', $3, $4, $5, $6) RETURNING id",
            firm.tenant_id,
            firm.engagement_id,
            uuid.uuid4(),
            f"k-{uuid.uuid4().hex[:8]}",
            kind,
            firm.user_id,
        ),
    )


_VERSION = (
    "INSERT INTO tie_out_check_versions (tenant_id, check_id, version_no, label, "
    "actual_selector, expected, citation_ids, created_by, actor_kind) "
    "VALUES ($1, $2, 1, 'Net assets ↔ trust report', $3::jsonb, $4::jsonb, $5::uuid[], $6, $7) "
    "RETURNING id"
)


async def _as_app(db: sc.Database, firm: Firm, statement: str, *args: object) -> object:
    conn = await asyncpg.connect(_dsn(db.app_url))
    try:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.tenant_id', $1, true)", str(firm.tenant_id))
            return await conn.fetchval(statement, *args)
    finally:
        await conn.close()


async def _check_row(db: sc.Database, check_id: uuid.UUID) -> dict[str, object]:
    raw = await _sql(db, "SELECT to_jsonb(c)::text FROM tie_out_checks c WHERE id = $1", check_id)
    return cast(dict[str, object], json.loads(cast(str, raw)))


def test_ac10_existing_checks_survive_up_down_up(db: sc.Database) -> None:
    migrate(db.owner_url, BEFORE, down=True)
    firm = asyncio.run(_firm(db))
    check = asyncio.run(_check(db, firm, "tie"))
    before = asyncio.run(_check_row(db, check))
    migrate(db.owner_url, "head")
    after = asyncio.run(_check_row(db, check))
    assert {k: after[k] for k in before} == before
    assert (after["issue_id"], after["issue_linked_by"], after["issue_linked_at"]) == (
        None,
        None,
        None,
    )
    migrate(db.owner_url, BEFORE, down=True)
    assert asyncio.run(_check_row(db, check)) == before
    migrate(db.owner_url, "head")
    assert asyncio.run(_check_row(db, check)) == after
    assert sc.check(db.owner_url, db.app_url) == []


def test_ac10_an_expected_value_without_a_citation_is_refused_by_check(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    check = asyncio.run(_check(db, firm, "tie"))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _as_app(
                db,
                firm,
                _VERSION,
                firm.tenant_id,
                check,
                SELECTOR,
                EXPECTED,
                [],
                firm.user_id,
                "human",
            )
        )
    # Not vacuous: the same row with a citation is accepted.
    cited = asyncio.run(
        _as_app(
            db,
            firm,
            _VERSION,
            firm.tenant_id,
            check,
            SELECTOR,
            EXPECTED,
            [uuid.uuid4()],
            firm.user_id,
            "human",
        )
    )
    assert cited is not None


def test_a_balanced_check_takes_no_expected_value(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    check = asyncio.run(_check(db, firm, "balanced"))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _as_app(
                db,
                firm,
                _VERSION,
                firm.tenant_id,
                check,
                SELECTOR,
                EXPECTED,
                [uuid.uuid4()],
                firm.user_id,
                "human",
            )
        )
    plain = asyncio.run(
        _as_app(
            db, firm, _VERSION, firm.tenant_id, check, SELECTOR, None, [], firm.user_id, "human"
        )
    )
    assert plain is not None


def test_only_a_human_defines_a_check(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    check = asyncio.run(_check(db, firm, "tie"))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _as_app(
                db,
                firm,
                _VERSION,
                firm.tenant_id,
                check,
                SELECTOR,
                EXPECTED,
                [uuid.uuid4()],
                firm.user_id,
                "agent",
            )
        )


def test_a_version_is_never_updated_or_deleted_by_any_role(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    check = asyncio.run(_check(db, firm, "tie"))
    version = asyncio.run(
        _as_app(
            db,
            firm,
            _VERSION,
            firm.tenant_id,
            check,
            SELECTOR,
            EXPECTED,
            [uuid.uuid4()],
            firm.user_id,
            "human",
        )
    )
    for statement in (
        "UPDATE tie_out_check_versions SET label = 'x' WHERE id = $1",
        "DELETE FROM tie_out_check_versions WHERE id = $1",
    ):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            asyncio.run(_as_app(db, firm, statement, version))
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            asyncio.run(_sql(db, statement, version))  # the trigger refuses the superuser too


def test_the_issue_link_is_whole_and_in_the_firm(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    other = asyncio.run(_firm(db))
    check = asyncio.run(_check(db, firm, "tie"))
    link = (
        "UPDATE tie_out_checks SET issue_id = $2, issue_linked_by = $3, "
        "issue_linked_at = clock_timestamp() WHERE id = $1 RETURNING id"
    )
    # Half a link is refused.
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _as_app(
                db,
                firm,
                "UPDATE tie_out_checks SET issue_id = $2 WHERE id = $1",
                check,
                uuid.uuid4(),
            )
        )
    issue = uuid.uuid4()
    asyncio.run(
        _sql(
            db,
            "INSERT INTO issues (id, tenant_id, engagement_id, record_ref, kind, title_sealed) "
            "VALUES ($1, $2, $3, '{}'::jsonb, 'exception', '\\x01'::bytea)",
            issue,
            other.tenant_id,
            other.engagement_id,
        )
    )
    # Another firm's issue is not this firm's: the composite key refuses it.
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        asyncio.run(_as_app(db, firm, link, check, issue, firm.user_id))
    mine = uuid.uuid4()
    asyncio.run(
        _sql(
            db,
            "INSERT INTO issues (id, tenant_id, engagement_id, record_ref, kind, title_sealed) "
            "VALUES ($1, $2, $3, '{}'::jsonb, 'exception', '\\x01'::bytea)",
            mine,
            firm.tenant_id,
            firm.engagement_id,
        )
    )
    assert asyncio.run(_as_app(db, firm, link, check, mine, firm.user_id)) == check
    # The definition columns stay closed to the app.
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(
            _as_app(db, firm, "UPDATE tie_out_checks SET kind = 'balanced' WHERE id = $1", check)
        )
