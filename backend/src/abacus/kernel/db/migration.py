"""Migration helpers for tenant tables (ADR-014) and insert-only tables (ADR-004). PROTECTED.

Every migration that creates a tenant table calls `tenant_table(op, name)`; `schema_check` fails
any table that doesn't end up with the result. Evidence and ledger tables also call `insert_only`.
Identifiers can't be bound parameters, so table names are validated against a strict pattern.

From migration 0686, `tenant_table` also attaches `archived_guard()` to a table with a
`work_item_id` or `engagement_id` column, unless `archive_guard.EXEMPT` lists it (A-07-T13).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol

from abacus.kernel.db.archive_guard import EXEMPT, trigger_arguments

_IDENTIFIER = re.compile(r"[a-z_][a-z0-9_]*")
# NULLIF: after a transaction ends, a reused connection reads the setting as '' (not NULL), and
# ''::uuid would raise. Both NULL and '' must mean "no tenant": no rows, no inserts.
_TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"


class Executes(Protocol):
    """The part of Alembic's `op` these helpers use."""

    def execute(self, sqltext: str) -> object: ...


def _checked(table: str) -> str:
    if not _IDENTIFIER.fullmatch(table):
        raise ValueError(
            f"table name {table!r} must match {_IDENTIFIER.pattern} (unquoted, unqualified)"
        )
    return table


def tenant_table(op: Executes, table: str) -> None:
    """Enable and force row-level security with the tenant isolation policy."""
    t = _checked(table)
    op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {t} "
        f"USING (tenant_id = {_TENANT}) WITH CHECK (tenant_id = {_TENANT})"
    )
    if t not in EXEMPT:
        _attach_archived_guard(op, t)


_ATTACH_GUARD = """
    DO $guard$
    BEGIN
        IF to_regprocedure('archived_guard()') IS NOT NULL AND EXISTS (
            SELECT 1 FROM information_schema.columns
             WHERE table_name = '@table'
               AND column_name IN ('work_item_id', 'engagement_id')
        ) THEN
            CREATE TRIGGER archived_guard BEFORE INSERT OR UPDATE OR DELETE ON @table
                FOR EACH ROW EXECUTE FUNCTION archived_guard(@kinds);
        END IF;
    END;
    $guard$
"""


def _attach_archived_guard(op: Executes, table: str) -> None:
    """Skipped before 0686 (no function yet: 0686 attaches to what exists) and for a table with
    neither column. `table` is checked by `tenant_table`; kinds come from the reviewed registry."""
    op.execute(_ATTACH_GUARD.replace("@table", table).replace("@kinds", trigger_arguments(table)))


def insert_columns(op: Executes, table: str, columns: Sequence[str]) -> None:
    """The application role may insert only these columns: defaults, identities and server-set
    columns (ids, sequence numbers, timestamps, delivery state) stay out of its hands."""
    t = _checked(table)
    names = [_checked(column) for column in columns]
    if not names:
        raise ValueError("insert_columns needs at least one column")
    op.execute(f"REVOKE INSERT ON {t} FROM abacus_app")
    op.execute(f"GRANT INSERT ({', '.join(names)}) ON {t} TO abacus_app")


def insert_only(op: Executes, table: str) -> None:
    """The application role may insert and read, never update or delete (AC-13 mechanism)."""
    op.execute(f"REVOKE UPDATE, DELETE ON {_checked(table)} FROM abacus_app")
