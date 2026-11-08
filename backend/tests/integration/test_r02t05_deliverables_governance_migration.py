"""R-02-T05 (TASK-6101; R-02 §4.2; POR-08, POR-09, POR-15): migration 0710.

Row acceptance: "The migration passes up/down/up ..., insert-only tables refuse UPDATE and DELETE,
and an agent or firm actor cannot insert an acknowledgement." Up/down/up is the schema gate's
round trip (`provisioned_database(roundtrip=True)`); RLS forced, the A-07 body FKs validated and
the archive guard attached are checked here too.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import asyncpg
import pytest

from abacus.modules.assurance import registry as assurance_registry
from abacus.modules.reporting import registry as reporting_registry
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import provisioned_database

from .agent_tests.support import Seeder

TABLES = (
    "deliverables",
    "deliverable_audiences",
    "deliverable_versions",
    "deliverable_events",
    "deliverable_receipts",
    "governance_bodies",
    "governance_body_members",
    "uncorrected_misstatement_acknowledgements",
)
INSERT_ONLY = (
    "deliverable_audiences",
    "deliverable_versions",
    "deliverable_events",
    "uncorrected_misstatement_acknowledgements",
)
_HASH = "a" * 64


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=True) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def test_every_table_is_owned_by_its_module() -> None:
    assert {"deliverables", "deliverable_receipts"} <= reporting_registry.TABLES
    assert {"governance_bodies", "governance_body_members"} <= assurance_registry.TABLES
    assert set(INSERT_ONLY) <= reporting_registry.INSERT_ONLY | assurance_registry.INSERT_ONLY


@pytest.mark.parametrize("table", TABLES)
def test_rls_is_forced(db: sc.Database, table: str) -> None:
    assert (
        _value(
            db,
            "SELECT relforcerowsecurity AND relrowsecurity FROM pg_class WHERE relname = $1",
            table,
        )
        is True
    )


@pytest.mark.parametrize("table", INSERT_ONLY)
def test_insert_only_tables_refuse_update_delete_and_truncate(db: sc.Database, table: str) -> None:
    for privilege in ("UPDATE", "DELETE", "TRUNCATE"):
        granted = _value(db, "SELECT has_table_privilege('abacus_app', $1, $2)", table, privilege)
        assert granted is False, (table, privilege)
    triggers = _value(
        db,
        "SELECT count(*) FROM pg_trigger WHERE tgrelid = $1::regclass AND tgname IN ($2, $3)",
        table,
        f"{table}_immutable",
        f"{table}_no_truncate",
    )
    assert triggers == 2


@pytest.mark.parametrize("table", INSERT_ONLY)
def test_insert_only_triggers_refuse_even_the_owner(db: sc.Database, table: str) -> None:
    # Empty tables fire no row trigger, so the statement TRUNCATE trigger is the probe.
    async def truncate() -> None:
        conn = await asyncpg.connect(db.superuser_dsn)
        try:
            await conn.execute(f"TRUNCATE {table} CASCADE")
        finally:
            await conn.close()

    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(truncate())


async def _insert_acknowledgement(
    dsn: str, *, session_kind: str, row_kind: str, principal: str, same_actor: bool = True
) -> None:
    user = uuid.uuid4()
    actor_id = str(user) if same_actor else str(uuid.uuid4())
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.actor_kind', $1, true), "
                "set_config('app.actor_id', $2, true)",
                session_kind,
                str(user),
            )
            await conn.execute(
                "INSERT INTO uncorrected_misstatement_acknowledgements (tenant_id, "
                "engagement_id, work_item_id, sum_snapshot_id, net_effect, engine_version, "
                "inputs_hash, entry_ids, contact_id, actor_user_id, actor_kind, actor_id, "
                "principal_kind, grant_id, mfa_verified_at, seen_hash) VALUES ($1, $2, $3, $4, "
                "22250.00, 'sum-1', $5, ARRAY[$6]::uuid[], $7, $8, $9, $10, $11, $12, now(), $5)",
                *(uuid.uuid4() for _ in range(4)),
                _HASH,
                uuid.uuid4(),
                uuid.uuid4(),
                user,
                row_kind,
                actor_id,
                principal,
                uuid.uuid4(),
            )
    finally:
        await conn.close()


@pytest.mark.parametrize(
    ("session_kind", "row_kind", "principal", "same_actor"),
    [
        ("agent", "agent", "client", True),  # an agent context
        ("system", "system", "client", True),  # the platform
        ("agent", "human", "client", True),  # an agent claiming to be a person
        ("human", "human", "firm", True),  # a firm user's session
        ("human", "human", "client", False),  # someone else's name on the row
    ],
)
def test_ac12_only_a_client_acting_as_itself_can_acknowledge(
    db: sc.Database, session_kind: str, row_kind: str, principal: str, same_actor: bool
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _insert_acknowledgement(
                db.superuser_dsn,
                session_kind=session_kind,
                row_kind=row_kind,
                principal=principal,
                same_actor=same_actor,
            )
        )


def test_ac12_a_client_session_passes_the_actor_check(db: sc.Database) -> None:
    # The CHECK runs before the FK triggers: the made-up references are what fail, so the human
    # client acting as itself got past the actor check.
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        asyncio.run(
            _insert_acknowledgement(
                db.superuser_dsn, session_kind="human", row_kind="human", principal="client"
            )
        )


@pytest.mark.parametrize(
    ("table", "constraint"),
    [
        ("governance_recipients", "governance_recipients_body_fk"),
        ("governance_communication_sends", "governance_communication_sends_body_fk"),
    ],
)
def test_a07_governance_rows_reference_the_body(
    db: sc.Database, table: str, constraint: str
) -> None:
    validated = _value(
        db,
        "SELECT convalidated FROM pg_constraint WHERE conname = $1 AND conrelid = $2::regclass",
        constraint,
        table,
    )
    assert validated is True


@pytest.mark.parametrize(
    "constraint",
    [
        "deliverable_versions_comments_on_drafts",
        "deliverable_versions_draft_is_generated",
        "deliverable_versions_system_acts_for_someone",
    ],
)
def test_ac18_version_guards_exist(db: sc.Database, constraint: str) -> None:
    count = _value(
        db,
        "SELECT count(*) FROM pg_constraint WHERE conname = $1 "
        "AND conrelid = 'deliverable_versions'::regclass",
        constraint,
    )
    assert count == 1


@pytest.mark.parametrize("table", ["deliverables", "uncorrected_misstatement_acknowledgements"])
def test_scoped_tables_carry_the_archive_guard(db: sc.Database, table: str) -> None:
    count = _value(
        db,
        "SELECT count(*) FROM pg_trigger "
        "WHERE tgrelid = $1::regclass AND tgname = 'archived_guard'",
        table,
    )
    assert count == 1


def test_a_reissue_after_lock_may_add_a_deliverable() -> None:
    from abacus.kernel.db.archive_guard import ALLOWED_KINDS

    assert ALLOWED_KINDS["deliverables"] == ("post_issuance",)
    assert "uncorrected_misstatement_acknowledgements" not in ALLOWED_KINDS
