"""A-04-T06 (TASK-2817; DEC-1866): migration 0613 `assurance_planning`.

Row acceptance: "up/down/up passes, a decided materiality row without a decision_id is refused,
and an agent-context insert into fraud_minutes_approvals fails at the database." Down to 0612
removes the seven tables, and up again restores them with forced row-level security. A decided
version needs a decision, and that decision must be the person's on the version's own card. The
minutes approval is refused to an agent session and to a person who is not the approver. A
management-override risk is never rebuttable. The app role never updates an insert-only table or
deletes a planning row. The status CHECKs are the status vocabulary's codes.

The guards are tested in a transaction with the session's settings set as `tenant_connection`
sets them. The rows name no real work item: a refusal from a CHECK or a guard comes before the
foreign keys, and a row that passes them fails on its foreign key instead, which shows the guard
let it through.
"""

from __future__ import annotations

import asyncio
import importlib.util
import uuid
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import cast

import asyncpg
import pytest
import yaml

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

BEFORE = "0612"
REPO = Path(__file__).resolve().parents[3]
TABLES = (
    "materiality_versions",
    "risk_register_rows",
    "risk_linkages",
    "service_organizations",
    "fraud_brainstorm_sessions",
    "fraud_minutes_approvals",
    "fraud_inquiries",
)
INSERT_ONLY = ("materiality_versions", "fraud_minutes_approvals")
HASH = "a" * 64


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql))


def _migration() -> ModuleType:
    path = REPO / "backend" / "migrations" / "versions" / "0613_assurance_planning.py"
    spec = importlib.util.spec_from_file_location("assurance_planning_0613", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _as(dsn: str, kind: str, actor: str, sql: str, *args: object) -> None:
    """One statement whose session settings name `kind` and `actor` (`Seeder.as_actor`; the
    tenant is the row's first argument)."""
    await Seeder(dsn).as_actor(cast(uuid.UUID, args[0]), (kind, actor), sql, *args)


def _materiality(status: str, decision: uuid.UUID | None) -> tuple[str, tuple[object, ...]]:
    return (
        "INSERT INTO materiality_versions (tenant_id, engagement_id, work_item_id, version_no, "
        "status, basis, benchmark_key, rate_pct, overall, pm_pct, pm, ct_pct, ct, engine_name, "
        "engine_version, inputs_hash, computed_at, created_by_kind, created_by_user_id, "
        "decision_card_id, decision_id) VALUES ($1, $2, $3, 2, $4, 'unadjusted', 'net_assets', "
        "1.5, 252200, 75, 189150, 5, 12610, 'materiality', '1', $5, now(), 'human', $6, $7, $8)",
        (
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
            status,
            HASH,
            uuid.uuid4(),
            uuid.uuid4() if decision is not None else None,
            decision,
        ),
    )


def _approval(approver: uuid.UUID) -> tuple[str, tuple[object, ...]]:
    return (
        "INSERT INTO fraud_minutes_approvals (tenant_id, engagement_id, work_item_id, "
        "session_id, minutes_hash, approved_by_user_id, actor_kind) "
        "VALUES ($1, $2, $3, $4, $5, $6, 'human')",
        (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), HASH, approver),
    )


def test_ac_0613_goes_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, BEFORE, down=True)
    for table in TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    migrate(private_db.owner_url, "head")
    for table in TABLES:
        forced = asyncio.run(
            Seeder(private_db.superuser_dsn).value(
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
                table,
            )
        )
        assert forced, table


def test_ac_a_decided_materiality_row_without_a_decision_is_refused(
    private_db: sc.Database,
) -> None:
    sql, args = _materiality("decided", None)
    with pytest.raises(asyncpg.CheckViolationError, match="decided_by_a_person"):
        asyncio.run(_as(private_db.superuser_dsn, "human", str(uuid.uuid4()), sql, *args))


@pytest.mark.parametrize("status", ["reassessed", "revised"])
def test_every_status_past_proposed_needs_a_decision(private_db: sc.Database, status: str) -> None:
    sql, args = _materiality(status, None)
    with pytest.raises(asyncpg.CheckViolationError, match="decided_by_a_person"):
        asyncio.run(_as(private_db.superuser_dsn, "human", str(uuid.uuid4()), sql, *args))


def test_a_decision_that_is_not_on_the_versions_card_is_refused(private_db: sc.Database) -> None:
    sql, args = _materiality("decided", uuid.uuid4())
    with pytest.raises(asyncpg.CheckViolationError, match="decision on its own card"):
        asyncio.run(_as(private_db.superuser_dsn, "human", str(uuid.uuid4()), sql, *args))


def test_a_proposed_version_needs_no_decision(private_db: sc.Database) -> None:
    sql, args = _materiality("proposed", None)
    # Past the CHECK and the guard: the made-up work item is what stops it.
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        asyncio.run(_as(private_db.superuser_dsn, "agent", "agent-run", sql, *args))


@pytest.mark.parametrize("kind", ["agent", "system", "policy"])
def test_ac_an_agent_context_minutes_approval_fails_at_the_database(
    private_db: sc.Database, kind: str
) -> None:
    approver = uuid.uuid4()
    sql, args = _approval(approver)
    with pytest.raises(asyncpg.InsufficientPrivilegeError, match="session's own person"):
        asyncio.run(_as(private_db.superuser_dsn, kind, str(approver), sql, *args))


def test_a_person_may_not_approve_in_another_persons_name(private_db: sc.Database) -> None:
    sql, args = _approval(uuid.uuid4())
    with pytest.raises(asyncpg.InsufficientPrivilegeError, match="session's own person"):
        asyncio.run(_as(private_db.superuser_dsn, "human", str(uuid.uuid4()), sql, *args))


def test_the_approvers_own_session_passes_the_guard(private_db: sc.Database) -> None:
    approver = uuid.uuid4()
    sql, args = _approval(approver)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        asyncio.run(_as(private_db.superuser_dsn, "human", str(approver), sql, *args))


@pytest.mark.parametrize("fraud", ["rebuttal_proposed", "rebuttal_approved"])
def test_management_override_is_never_rebuttable(private_db: sc.Database, fraud: str) -> None:
    sql = (
        "INSERT INTO risk_register_rows (tenant_id, engagement_id, work_item_id, code, level, "
        "area_key, area_label, inherent_risk, control_risk, rmm, fraud, presumption_kind, "
        "content_hash) VALUES ($1, $2, $3, 'R1', 'financial_statement', 'journal_entries', "
        "'Journal entries', 'high', 'max', 'high', $4, 'management_override', $5)"
    )
    args = (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), fraud, HASH)
    with pytest.raises(asyncpg.CheckViolationError, match="override_not_rebuttable"):
        asyncio.run(_as(private_db.superuser_dsn, "human", str(uuid.uuid4()), sql, *args))


@pytest.mark.parametrize("table", TABLES)
def test_the_app_role_never_deletes(private_db: sc.Database, table: str) -> None:
    assert not _value(private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'DELETE')")


@pytest.mark.parametrize("table", INSERT_ONLY)
def test_versions_and_approvals_are_never_updated(private_db: sc.Database, table: str) -> None:
    assert not _value(
        private_db, f"SELECT has_any_column_privilege('abacus_app', '{table}', 'UPDATE')"
    )
    assert _value(
        private_db, f"SELECT has_any_column_privilege('abacus_app', '{table}', 'INSERT')"
    )


def test_the_status_checks_are_the_vocabularys_codes() -> None:
    vocabulary = yaml.safe_load(
        (REPO / "docs" / "product" / "status-vocabulary.yaml").read_text(encoding="utf-8")
    )["objects"]
    migration = _migration()
    stored = {
        "materiality_version": migration.MATERIALITY_VERSION,
        "risk_register_row": migration.RISK_REGISTER_ROW,
        "risk_significance": migration.RISK_SIGNIFICANCE,
        "risk_fraud": migration.RISK_FRAUD,
        "risk_linkage": migration.RISK_LINKAGE,
        "fraud_minutes": migration.FRAUD_MINUTES,
        "service_organization": migration.SERVICE_ORGANIZATION,
    }
    for name, codes in stored.items():
        words = set(vocabulary[name]["codes"])
        # "Superseded" is derived from a newer version, never stored (A-04 §4.2 M2).
        assert set(codes) == words - {"superseded"}, name
