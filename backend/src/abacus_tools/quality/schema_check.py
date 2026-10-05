"""Tenant and row-level security schema check (ADR-014, ADR-080; stage 2). PROTECTED.

Run: python -m abacus_tools.quality.schema_check

There are no tables yet, so there is nothing to check and this passes. The moment a migration
exists it fails until SPEC-000 replaces this with the real check (every table has a non-null
tenant_id and a row-level security policy), so a schema can never land unchecked.
"""

from __future__ import annotations

import sys
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[3] / "migrations" / "versions"
NOT_IMPLEMENTED = (
    "schema_check is not implemented: SPEC-000 must add the tenant and row-level security "
    "schema check with its first migration"
)


def check(migrations: Path) -> list[str]:
    if not migrations.is_dir():
        return []
    if any(p.name != "__init__.py" for p in migrations.glob("*.py")):
        return [NOT_IMPLEMENTED]
    return []


def main() -> int:
    problems = check(MIGRATIONS)
    for p in problems:
        print(p)
    if problems:
        return 1
    print("schema_check: no migrations yet; nothing to check.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
