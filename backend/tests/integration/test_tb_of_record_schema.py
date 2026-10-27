"""SPEC-333 AC-32 to AC-34 (A-02-T04; TASK-1187): migration 0149, labels on ledger snapshots and
the second immutability layer on trial balance versions.

One private database, migrated to head without the round trip, so the tests can step it down to
0149's parent and back with rows in place. They run in file order: the downgrade guard comes
last, because a labelled snapshot can never be removed (ADR-004). Rows are seeded as the
superuser; statements that must fail for `abacus_app` run as that role with the tenant set, as
`tenant_session` would. Expectations come from A-02 §4.2 and the T04 row, not from the code.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

import asyncpg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.exc import DBAPIError

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

REVISION = "0149"
_SCRIPTS = ScriptDirectory.from_config(
    Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
)
# 0149's parent, read from the script so a re-chain at merge needs no edit here.
BEFORE = cast(str, _SCRIPTS.get_revision(REVISION).down_revision)
START, END = date(2025, 1, 1), date(2025, 12, 31)
PULLED_AT = datetime(2026, 9, 14, 14, 26, tzinfo=UTC)


@dataclass(frozen=True)
class Firm:
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    entity_id: uuid.UUID
    engagement_id: uuid.UUID
    work_item_id: uuid.UUID


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _fingerprint() -> str:
    return hashlib.sha256(uuid.uuid4().bytes).hexdigest()


async def _superuser(db: sc.Database) -> asyncpg.Connection:
    return await asyncpg.connect(db.superuser_dsn)


async def _firm(db: sc.Database) -> Firm:
    conn = await _superuser(db)
    try:
        tenant_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO firms (tenant_id, name) VALUES ($1, 'TB labels')", tenant_id
        )
        subject = f"sub-{uuid.uuid4().hex}"
        user_id = cast(
            uuid.UUID,
            await conn.fetchval(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ('https://identity.abacus.local', $1, $2, 'Test person') RETURNING id",
                subject,
                f"{subject}@example.test",
            ),
        )
        await conn.execute(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
            "VALUES ($1, $2, NULL, 'active')",
            tenant_id,
            user_id,
        )
        client_id = await conn.fetchval(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Seeded client') RETURNING id",
            tenant_id,
        )
        entity_id = cast(
            uuid.UUID,
            await conn.fetchval(
                "INSERT INTO client_entities (tenant_id, client_id, name) "
                "VALUES ($1, $2, 'Seeded entity') RETURNING id",
                tenant_id,
                client_id,
            ),
        )
        engagement_id = cast(
            uuid.UUID,
            await conn.fetchval(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                "fiscal_period_start, fiscal_period_end, created_by) "
                "VALUES ($1, $2, $3, 'Seeded audit', $4, $5, $6) RETURNING id",
                tenant_id,
                client_id,
                entity_id,
                START,
                END,
                user_id,
            ),
        )
        # An engagement may already carry its assurance item (one per engagement).
        work_item_id = await conn.fetchval(
            "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
            engagement_id,
        ) or await conn.fetchval(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, "
            "kind, name, created_by) VALUES ($1, $2, $3, $4, 'assurance', 'Audit', $5) "
            "RETURNING id",
            tenant_id,
            engagement_id,
            client_id,
            entity_id,
            user_id,
        )
        return Firm(tenant_id, user_id, entity_id, engagement_id, cast(uuid.UUID, work_item_id))
    finally:
        await conn.close()


_SNAPSHOT = (
    "INSERT INTO ledger_snapshots (tenant_id, client_entity_id, period_start, period_end, "
    "pulled_at, source, raw_fingerprint, line_count, total_debit, total_credit) "
    "VALUES ($1, $2, $3, $4, $5, $6, $7, 0, 0, 0) RETURNING id"
)
_LABELLED = (
    "INSERT INTO ledger_snapshots (tenant_id, client_entity_id, period_start, period_end, "
    "pulled_at, source, raw_fingerprint, line_count, total_debit, total_credit, label) "
    "VALUES ($1, $2, $3, $4, $5, $6, $7, 0, 0, 0, $8) RETURNING id"
)


async def _snapshot(
    db: sc.Database, firm: Firm, source: str, label: str | None = None
) -> uuid.UUID:
    conn = await _superuser(db)
    try:
        args = (firm.tenant_id, firm.entity_id, START, END, PULLED_AT, source, _fingerprint())
        if label is None:
            return cast(uuid.UUID, await conn.fetchval(_SNAPSHOT, *args))
        return cast(uuid.UUID, await conn.fetchval(_LABELLED, *args, label))
    finally:
        await conn.close()


async def _version(db: sc.Database, firm: Firm) -> uuid.UUID:
    snapshot = await _snapshot(db, firm, "import_netsuite")
    conn = await _superuser(db)
    try:
        tb = await conn.fetchval(
            "INSERT INTO trial_balances (tenant_id, engagement_id, work_item_id, "
            "client_entity_id, period_start, period_end, created_by) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
            firm.tenant_id,
            firm.engagement_id,
            firm.work_item_id,
            firm.entity_id,
            START,
            END,
            firm.user_id,
        )
        return cast(
            uuid.UUID,
            await conn.fetchval(
                "INSERT INTO trial_balance_versions (tenant_id, trial_balance_id, "
                "client_entity_id, version_no, snapshot_id, adopted_by, actor_kind, "
                "content_fingerprint) VALUES ($1, $2, $3, 1, $4, $5, 'human', $6) RETURNING id",
                firm.tenant_id,
                tb,
                firm.entity_id,
                snapshot,
                firm.user_id,
                _fingerprint(),
            ),
        )
    finally:
        await conn.close()


async def _as_app(db: sc.Database, firm: Firm, statement: str, *args: object) -> None:
    """One statement as `abacus_app` in the firm's tenant, as `tenant_session` sets it."""
    conn = await asyncpg.connect(_dsn(db.app_url))
    try:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.tenant_id', $1, true)", str(firm.tenant_id))
            await conn.execute(statement, *args)
    finally:
        await conn.close()


async def _row(db: sc.Database, snapshot_id: uuid.UUID) -> dict[str, object]:
    """Every column of the snapshot, whatever the schema has at this revision."""
    conn = await _superuser(db)
    try:
        row = await conn.fetchval(
            "SELECT to_jsonb(s)::text FROM ledger_snapshots s WHERE id = $1", snapshot_id
        )
        assert row is not None
        return cast(dict[str, object], json.loads(cast(str, row)))
    finally:
        await conn.close()


async def _revision(db: sc.Database) -> str:
    conn = await _superuser(db)
    try:
        return cast(str, await conn.fetchval("SELECT version_num FROM alembic_version"))
    finally:
        await conn.close()


# --- AC-32: labels and source kinds, with no snapshot updated -----------------------------------


def test_ac32_a_snapshot_from_before_0149_reads_the_same_after_up_down_up(db: sc.Database) -> None:
    migrate(db.owner_url, BEFORE, down=True)
    firm = asyncio.run(_firm(db))
    snapshot = asyncio.run(_snapshot(db, firm, "import_qbo_tb_csv"))
    before = asyncio.run(_row(db, snapshot))
    # Up: the immutability trigger would refuse any UPDATE of the row, so success proves none ran.
    migrate(db.owner_url, "head")
    after = asyncio.run(_row(db, snapshot))
    assert {k: after[k] for k in before} == before
    assert (after["label"], after["source_kind"]) == ("standard", "import")
    migrate(db.owner_url, BEFORE, down=True)
    assert asyncio.run(_row(db, snapshot)) == before
    migrate(db.owner_url, "head")
    again = asyncio.run(_row(db, snapshot))
    assert again == after
    assert sc.check(db.owner_url, db.app_url) == []


# Every source the import formats and the fake connector write today (SPEC-028; `connections.
# import_formats.FORMATS`, `fake.SOURCE`). Anything else is `other`, never `import`: the kind is
# read from a known value, not from a prefix of free text (A-02 security review, DEC-316).
KNOWN_IMPORTS = (
    "import_qbo_tb_csv",
    "import_xero_tb_xlsx",
    "import_qbd_tb_xlsx",
    "import_netsuite_tb_csv",
    "import_intacct_tb_csv",
)


@pytest.mark.parametrize(
    ("source", "kind"),
    [
        *[(source, "import") for source in KNOWN_IMPORTS],
        ("fake", "fake"),
        ("import_unknown", "other"),  # an unknown format, whatever its prefix
        ("import_accrued_template", "import"),  # A-02-T22 registered the format (0235)
        ("import_qbo_tb_csv ", "other"),
        ("IMPORT_QBO_TB_CSV", "other"),
        ("quickbooks_online", "other"),  # until A-02-T26's connector joins the mapping
        ("importer", "other"),
    ],
)
def test_ac32_source_kind_is_generated_from_the_source(
    db: sc.Database, source: str, kind: str
) -> None:
    firm = asyncio.run(_firm(db))
    snapshot = asyncio.run(_snapshot(db, firm, source))
    row = asyncio.run(_row(db, snapshot))
    assert (row["label"], row["source_kind"]) == ("standard", kind)


@pytest.mark.parametrize("label", ["standard", "interim", "prior", "budget", "preliminary"])
def test_ac32_each_of_the_five_labels_is_accepted(db: sc.Database, label: str) -> None:
    firm = asyncio.run(_firm(db))
    snapshot = asyncio.run(_snapshot(db, firm, "fake", label))
    assert asyncio.run(_row(db, snapshot))["label"] == label


@pytest.mark.parametrize("label", ["final", "Standard", ""])
def test_ac32_a_label_outside_the_five_is_refused(db: sc.Database, label: str) -> None:
    firm = asyncio.run(_firm(db))
    with pytest.raises(asyncpg.CheckViolationError, match="ledger_snapshots_label"):
        asyncio.run(_snapshot(db, firm, "fake", label))


# --- AC-33: what the app may write ---------------------------------------------------------------

_APP_SNAPSHOT = (
    "INSERT INTO ledger_snapshots (id, tenant_id, client_entity_id, period_start, period_end, "
    "pulled_at, source, raw_fingerprint, line_count, total_debit, total_credit{extra}) "
    "VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, 'fake', $6, 0, 0, 0{value})"
)


def test_ac33_the_app_supplies_a_snapshots_label(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    statement = _APP_SNAPSHOT.format(extra=", label", value=", 'interim'")
    asyncio.run(
        _as_app(
            db,
            firm,
            statement,
            firm.tenant_id,
            firm.entity_id,
            START,
            END,
            PULLED_AT,
            _fingerprint(),
        )
    )

    async def labels() -> list[str]:
        conn = await _superuser(db)
        try:
            rows = await conn.fetch(
                "SELECT label FROM ledger_snapshots WHERE tenant_id = $1", firm.tenant_id
            )
            return [r["label"] for r in rows]
        finally:
            await conn.close()

    assert asyncio.run(labels()) == ["interim"]


def test_ac33_the_app_never_supplies_a_source_kind(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    statement = _APP_SNAPSHOT.format(extra=", source_kind", value=", 'import'")
    with pytest.raises(asyncpg.PostgresError):
        asyncio.run(
            _as_app(
                db,
                firm,
                statement,
                firm.tenant_id,
                firm.entity_id,
                START,
                END,
                PULLED_AT,
                _fingerprint(),
            )
        )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE trial_balance_versions SET reason = 'changed' WHERE id = $1",
        "DELETE FROM trial_balance_versions WHERE id = $1",
    ],
    ids=["update", "delete"],
)
def test_ac33_the_app_cannot_update_or_delete_a_version(db: sc.Database, statement: str) -> None:
    firm = asyncio.run(_firm(db))
    version = asyncio.run(_version(db, firm))
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(_as_app(db, firm, statement, version))


def test_ac33_the_app_cannot_record_a_version_adopted_by_an_agent(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    version = asyncio.run(_version(db, firm))

    async def adopted() -> tuple[uuid.UUID, uuid.UUID]:
        conn = await _superuser(db)
        try:
            row = await conn.fetchrow(
                "SELECT trial_balance_id, snapshot_id FROM trial_balance_versions WHERE id = $1",
                version,
            )
            assert row is not None
            return row["trial_balance_id"], row["snapshot_id"]
        finally:
            await conn.close()

    tb, snapshot = asyncio.run(adopted())
    newer = asyncio.run(_snapshot(db, firm, "import_netsuite"))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _as_app(
                db,
                firm,
                "INSERT INTO trial_balance_versions (tenant_id, trial_balance_id, "
                "client_entity_id, version_no, snapshot_id, prior_snapshot_id, adopted_by, "
                "actor_kind, reason, content_fingerprint) "
                "VALUES ($1, $2, $3, 2, $4, $5, $6, 'agent', 'agent re-version', $7)",
                firm.tenant_id,
                tb,
                firm.entity_id,
                newer,
                snapshot,
                firm.user_id,
                _fingerprint(),
            )
        )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE trial_balance_versions SET reason = 'changed' WHERE id = $1",
        "DELETE FROM trial_balance_versions WHERE id = $1",
        "TRUNCATE trial_balance_versions",
    ],
    ids=["update", "delete", "truncate"],
)
def test_ac33_the_trigger_refuses_every_role_even_the_superuser(
    db: sc.Database, statement: str
) -> None:
    firm = asyncio.run(_firm(db))
    version = asyncio.run(_version(db, firm))

    async def run() -> None:
        conn = await _superuser(db)
        try:
            args = [] if statement.startswith("TRUNCATE") else [version]
            await conn.execute(statement, *args)
        finally:
            await conn.close()

    with pytest.raises(asyncpg.InsufficientPrivilegeError, match="immutable"):
        asyncio.run(run())


# --- AC-34: the downgrade guard (last: a labelled snapshot can never be removed) -----------------


def test_ac34_the_downgrade_is_refused_while_a_snapshot_is_not_standard(db: sc.Database) -> None:
    firm = asyncio.run(_firm(db))
    asyncio.run(_snapshot(db, firm, "import_netsuite", "prior"))
    head = asyncio.run(_revision(db))
    with pytest.raises(DBAPIError, match="refusing to downgrade 0149"):
        migrate(db.owner_url, BEFORE, down=True)
    # The guard held: 0149 is still applied. Later migrations in the chain downgrade first, each
    # in its own transaction, so the database stops at 0149, not at head (S8 wave A assembly).
    assert asyncio.run(_revision(db)) == REVISION
    migrate(db.owner_url, head)
    assert asyncio.run(_revision(db)) == head
    assert sc.check(db.owner_url, db.app_url) == []
