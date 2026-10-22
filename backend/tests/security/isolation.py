"""What the generated tenant-isolation test checks for one table (Q-02-T13; ADR-014, ADR-080):
row-level security is on and forced, the tenant isolation policy is on it, and, read as the
app role under firm A, no row of firm B comes back. Hand-written; the table list is generated."""

from __future__ import annotations

import uuid

from sqlalchemy import column, func, select, table
from sqlalchemy.exc import DBAPIError

from abacus.kernel.db import TenantContext, tenant_session

from .support import Seeder


async def problems(seed: Seeder, name: str, a: TenantContext, b: uuid.UUID) -> list[str]:
    found: list[str] = []
    flags = await seed.rows(
        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
        "WHERE oid = to_regclass('public.' || $1)",
        name,
    )
    if not flags:
        return ["no such table"]
    if not flags[0]["relrowsecurity"]:
        found.append("row-level security is off")
    if not flags[0]["relforcerowsecurity"]:
        found.append("row-level security is not forced")
    # `tenant_table()` names the policy that keys a table to the session's tenant.
    policies = await seed.value(
        "SELECT count(*) FROM pg_policies WHERE schemaname = 'public' AND tablename = $1 "
        "AND policyname = 'tenant_isolation'",
        name,
    )
    if not policies:
        found.append("no tenant_isolation policy")
    owned = table(name, column("tenant_id"))
    query = select(func.count()).select_from(owned).where(column("tenant_id") == b)
    try:
        async with tenant_session(a) as session:
            leaked = (await session.execute(query)).scalar_one()
    except DBAPIError:
        return found  # the app role can't read it at all: nothing leaks
    if leaked:
        found.append(f"{leaked} of firm B's rows read under firm A")
    return found
