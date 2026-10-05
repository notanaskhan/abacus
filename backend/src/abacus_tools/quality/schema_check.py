"""Tenant and row-level security schema check (ADR-014, ADR-080; stage 2). PROTECTED.

Run: python -m abacus_tools.quality.schema_check

There are no tables yet, so there is nothing to check and this passes. The moment a migration
exists it fails until SPEC-000 replaces this with the real check (every table has a non-null
tenant_id and a row-level security policy), so a schema can never land unchecked.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3]
MIGRATIONS = BACKEND / "migrations" / "versions"
NOT_IMPLEMENTED = (
    "schema_check is not implemented: SPEC-000 must add the tenant and row-level security "
    "schema check with its first migration"
)


def check(migrations: Path) -> list[str]:
    if not migrations.is_dir():
        return []
    if any(p.name != "__init__.py" for p in migrations.rglob("*.py")):
        return [NOT_IMPLEMENTED]
    return []


def check_orm(backend: Path) -> list[str]:
    """Any sign of a schema outside migrations: Alembic config or ORM model modules."""
    package = backend / "src" / "abacus"
    models = package.is_dir() and (
        any(package.rglob("models.py")) or any(p.is_dir() for p in package.rglob("models"))
    )
    if (backend / "alembic.ini").exists() or models:
        return [NOT_IMPLEMENTED]
    return []


def main() -> int:
    problems = sorted(set(check(MIGRATIONS) + check_orm(BACKEND)))
    for p in problems:
        print(p)
    if problems:
        return 1
    print("schema_check: no migrations yet; nothing to check.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
