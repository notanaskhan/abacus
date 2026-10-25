"""Operator and tooling connections with the app's TLS rule (G-09; P-08-T21 security review).

Every `abacus_tools` connection goes through `connect`, which hands asyncpg the same decision as
the app's engines (`abacus.kernel.db_tls.database_tls`): plain only on the local stack when
nothing asks for TLS, otherwise `verify-full` against `ABACUS_DATABASE_CA_FILE` (or the system
store); outside local and test a DSN that turns TLS off is refused. The environment is read from
`ABACUS_ENVIRONMENT` directly, so a one-off ops task needs none of the app's other settings.
`quality.banned_patterns` (TLS-001) refuses `asyncpg.connect` without `ssl=` in this package;
only the local-only `stack.py` and `local/seed_dev.py` are exempt.
"""

from __future__ import annotations

import os

import asyncpg

from abacus.kernel.config import LOCAL_STACK
from abacus.kernel.db_tls import DatabaseTls, database_tls


def tls_for(dsn: str) -> DatabaseTls:
    environment = os.environ.get("ABACUS_ENVIRONMENT", "local")
    ca_file = os.environ.get("ABACUS_DATABASE_CA_FILE") or None
    tls = database_tls(dsn, local=environment in LOCAL_STACK, ca_file=ca_file)
    return DatabaseTls(tls.url.replace("postgresql+asyncpg://", "postgresql://", 1), tls.ssl)


async def connect(dsn: str) -> asyncpg.Connection:
    tls = tls_for(dsn)
    return await asyncpg.connect(tls.url, ssl=tls.ssl)
