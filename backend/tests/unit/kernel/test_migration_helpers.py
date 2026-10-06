"""AC-5, AC-13: the migration helpers emit exactly the SQL in TASK-005 Design section 2."""

from __future__ import annotations

from typing import cast

import pytest
from alembic.operations import Operations

from abacus.kernel.db.migration import insert_columns, insert_only, tenant_table

TENANT_ISOLATION = (
    "CREATE POLICY tenant_isolation ON {t} "
    "USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
    "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
)


class RecordingOp:
    """Stands in for alembic's `op`; the helpers only call `op.execute(<str>)`."""

    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, sql: str) -> None:
        self.statements.append(sql)


def _tenant_table(table: str) -> list[str]:
    op = RecordingOp()
    tenant_table(cast(Operations, op), table)
    return op.statements


def _insert_only(table: str) -> list[str]:
    op = RecordingOp()
    insert_only(cast(Operations, op), table)
    return op.statements


def test_ac5_tenant_table_emits_exactly_three_statements_in_order() -> None:
    assert _tenant_table("documents") == [
        "ALTER TABLE documents ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE documents FORCE ROW LEVEL SECURITY",
        TENANT_ISOLATION.format(t="documents"),
    ]


def test_ac5_tenant_table_statements_are_single_line_without_semicolon() -> None:
    for statement in _tenant_table("t1"):
        assert "\n" not in statement
        assert "  " not in statement
        assert not statement.rstrip().endswith(";")


def test_ac5_tenant_table_uses_the_given_table_name_in_every_statement() -> None:
    first, second, third = _tenant_table("_ledger_entries2")
    assert "ALTER TABLE _ledger_entries2 " in first
    assert "ALTER TABLE _ledger_entries2 " in second
    assert "ON _ledger_entries2 " in third


def test_ac13_insert_only_emits_one_revoke() -> None:
    assert _insert_only("documents") == ["REVOKE UPDATE, DELETE ON documents FROM abacus_app"]


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "Users",
        "a-b",
        "public.t",
        '"t"',
        "1t",
        "t t",
        "t;",
        "t; DROP TABLE x",
        "t\n",
        " t",
        "ünï",
    ],
)
def test_ac5_tenant_table_rejects_invalid_names_without_emitting(bad: str) -> None:
    op = RecordingOp()
    with pytest.raises(ValueError):
        tenant_table(cast(Operations, op), bad)
    assert op.statements == []


@pytest.mark.parametrize(
    "bad", ["", "Users", "a-b", "public.t", '"t"', "1t", "t;", "t; DROP TABLE x", "t\n"]
)
def test_ac13_insert_only_rejects_invalid_names_without_emitting(bad: str) -> None:
    op = RecordingOp()
    with pytest.raises(ValueError):
        insert_only(cast(Operations, op), bad)
    assert op.statements == []


@pytest.mark.parametrize("good", ["t", "_t", "t1", "a_b_c", "_"])
def test_ac5_valid_names_are_accepted(good: str) -> None:
    assert len(_tenant_table(good)) == 3
    assert len(_insert_only(good)) == 1


def _insert_columns(table: str, columns: list[str]) -> list[str]:
    op = RecordingOp()
    insert_columns(cast(Operations, op), table, columns)
    return op.statements


def test_ac13_insert_columns_emits_a_revoke_then_a_column_grant_in_the_given_order() -> None:
    assert _insert_columns("outbox", ["tenant_id", "id", "payload"]) == [
        "REVOKE INSERT ON outbox FROM abacus_app",
        "GRANT INSERT (tenant_id, id, payload) ON outbox TO abacus_app",
    ]


def test_ac13_insert_columns_with_one_column_has_no_trailing_comma() -> None:
    assert _insert_columns("t", ["a"]) == [
        "REVOKE INSERT ON t FROM abacus_app",
        "GRANT INSERT (a) ON t TO abacus_app",
    ]


@pytest.mark.parametrize("bad", ["", "Users", "a-b", "public.t", "t;", "t; DROP TABLE x", "1t"])
def test_ac13_insert_columns_rejects_invalid_table_names_without_emitting(bad: str) -> None:
    op = RecordingOp()
    with pytest.raises(ValueError):
        insert_columns(cast(Operations, op), bad, ["a"])
    assert op.statements == []


@pytest.mark.parametrize(
    "bad", ["", "Col", "a-b", "t.c", "c;", "c) TO public; --", '"c"', "1c", "c c", "c\n"]
)
def test_ac13_insert_columns_rejects_invalid_column_names_without_emitting(bad: str) -> None:
    op = RecordingOp()
    with pytest.raises(ValueError):
        insert_columns(cast(Operations, op), "t", ["good", bad])
    assert op.statements == []
