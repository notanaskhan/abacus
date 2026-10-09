"""Seed the local stack for sign-in and retrieval (TASK-012 Q2). Local only; idempotent.

Run: python -m abacus_tools.local.seed_dev   (`make seed`; run it again after creating an
                                              engagement to connect its client entity)

1. A firm, "Dev firm", with the sign-in server's dev users (`abacus_tools.fakes.oidc_server`):
   `dev-leader` (practice leader: may create engagements) and `dev-staff`.
2. Every client entity of the firm without an active connection gets a fake one (there is no
   connections UI in SPEC-000), and every engagement gets a balanced synthetic trial balance for
   its fiscal period in `fake_connector_dir`, so *Retrieve trial balance* works.

Writes as the local database superuser (seeding crosses identity and every firm table); refuses
to run outside the local and test environments.
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

import asyncpg

from abacus.kernel.config import settings
from abacus_tools.fakes.identity import ISSUER
from abacus_tools.fakes.oidc_server import DEV_USERS
from abacus_tools.flags import set_flag
from abacus_tools.synthetic import generate
from abacus_tools.synthetic.connector_fixtures import write_trial_balance

FIRM = UUID("00000000-0000-4000-8000-00000000d0e5")
FIRM_ROLES = {"dev-leader": "practice_leader", "dev-staff": None}
# The compose stack's superuser (docker-compose.yml); local only.
SUPERUSER_ENV = "ABACUS_LOCAL_SUPERUSER_DSN"
DEFAULT_SUPERUSER = "postgresql://postgres:postgres@127.0.0.1:55432/abacus"


def _local_only() -> Path:
    s = settings()
    if s.environment not in ("local", "test") or s.fake_connector_dir is None:
        raise RuntimeError("seed_dev is for local runs (with fake_connector_dir) only")
    return Path(s.fake_connector_dir)


async def _seed_people(conn: asyncpg.Connection) -> None:
    await conn.execute(
        "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Dev firm') ON CONFLICT DO NOTHING", FIRM
    )
    for subject, label in DEV_USERS:
        name = label.split(" (", 1)[0]
        user = await conn.fetchval(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ($1, $2, $3, $4) ON CONFLICT ON CONSTRAINT users_identity "
            "DO UPDATE SET display_name = EXCLUDED.display_name RETURNING id",
            ISSUER,
            subject,
            f"{subject}@dev.abacus.local",
            name,
        )
        exists = await conn.fetchval(
            "SELECT 1 FROM memberships WHERE tenant_id = $1 AND user_id = $2", FIRM, user
        )
        if not exists:
            await conn.execute(
                "INSERT INTO memberships (tenant_id, user_id, firm_role) VALUES ($1, $2, $3)",
                FIRM,
                user,
                FIRM_ROLES[subject],
            )


async def _connect_engagements(conn: asyncpg.Connection, fixtures: Path) -> int:
    rows = await conn.fetch(
        "SELECT e.client_entity_id, e.fiscal_period_start, e.fiscal_period_end, ce.name "
        "FROM engagements e JOIN client_entities ce "
        "ON ce.tenant_id = e.tenant_id AND ce.id = e.client_entity_id WHERE e.tenant_id = $1",
        FIRM,
    )
    tb = generate(7).client_entities[0].trial_balances[-1]
    connected = 0
    for row in rows:
        entity = row["client_entity_id"]
        connection = await conn.fetchval(
            "SELECT id FROM connections WHERE tenant_id = $1 AND client_entity_id = $2 "
            "AND status = 'active' ORDER BY created_at LIMIT 1",
            FIRM,
            entity,
        )
        if connection is None:
            connection = await conn.fetchval(
                "INSERT INTO connections (tenant_id, client_entity_id, provider, created_by) "
                "VALUES ($1, $2, 'fake', 'seed_dev') RETURNING id",
                FIRM,
                entity,
            )
            connected += 1
        start: date = row["fiscal_period_start"]
        end: date = row["fiscal_period_end"]
        write_trial_balance(
            fixtures,
            connection,
            replace(tb, as_of=end),
            period_start=start,
            entity_name=row["name"],
        )
    return connected


async def seed(dsn: str, fixtures: Path) -> int:
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            await _seed_people(conn)
            return await _connect_engagements(conn, fixtures)
    finally:
        await conn.close()


def _loopback(dsn: str) -> str:
    """Superuser writes only ever go to a database on this machine."""
    host = urlsplit(dsn).hostname
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError(f"{SUPERUSER_ENV} must point at a local database")
    return dsn


def main() -> int:
    fixtures = _local_only()
    dsn = _loopback(os.environ.get(SUPERUSER_ENV, DEFAULT_SUPERUSER))
    connected = asyncio.run(seed(dsn, fixtures))
    # SPEC-022 (TASK-038 D4): automatic retrieval is off by default; on for the local firm.
    asyncio.run(set_flag(FIRM, "retrieval.auto", "true", "seed", "local development"))
    print(f"seeded Dev firm; {connected} new fake connection(s); automatic retrieval on")
    return 0


if __name__ == "__main__":
    sys.exit(main())
