"""Migration helpers for tenant tables (ADR-014) and insert-only tables (ADR-004). PROTECTED.

Every migration that creates a tenant table calls `tenant_table(op, name)`; `schema_check` fails
any table that doesn't end up with the result. Evidence and ledger tables also call `insert_only`.
Identifiers can't be bound parameters, so table names are validated against a strict pattern.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol

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
