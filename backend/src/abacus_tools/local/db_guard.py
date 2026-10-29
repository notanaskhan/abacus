"""Refuse to run a local database target against a hosted database (F-01-T09).

Run: python -m abacus_tools.local.db_guard

Exits 1, naming the setting (never its value), when any database URL the settings resolve to has
a host outside the local stack. `make migrate`, `make seed` and `make seed-staging` run it first;
the load-test harness applies the same checks in-process before a run (Q-03-T114). Sanctioned
operator flows against staging arrive with Q-01, with their own checks (deploy in flight, deploy
lock).

Q-01-T18 (platform-ops contract 3.4): with `ABACUS_DEPLOY_LOCK_ENV` set (`staging` or
`production`), it also exits 1 while that environment's deploy lock is held, naming the holder:
nothing touches a database a deploy is migrating (the working agreement: no local production
build or manual migration while a hosted build uses the same database).
"""

from __future__ import annotations

import os
import sys
from urllib.parse import urlsplit

from abacus.kernel.clock import system_now
from abacus.kernel.config import settings

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "db"})
URLS = ("database_url", "migrations_database_url", "relay_database_url", "identity_database_url")


def hosted(url: str) -> bool:
    """True unless the URL's host is part of the local stack (an unparseable URL counts)."""
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return True
    return host is None or host.lower() not in LOCAL_HOSTS


def violations() -> list[str]:
    current = settings()
    found: list[str] = []
    for name in URLS:
        value = getattr(current, name)
        if value is not None and hosted(value.get_secret_value()):
            found.append(f"ABACUS_{name.upper()}")
    return found


def lock_holder() -> str | None:
    """The deploy lock's holder for `ABACUS_DEPLOY_LOCK_ENV`, or None (unset, or free)."""
    env = os.environ.get("ABACUS_DEPLOY_LOCK_ENV")
    if not env:
        return None
    from abacus_tools.deploy_lock import describe, held  # boto3 only when asked

    found = held(env)
    return describe(found, system_now()) if found is not None else None


def main() -> int:
    found = violations()
    for name in found:
        print(f"{name}: never point a local run at a hosted database", file=sys.stderr)
    holder = lock_holder()
    if holder is not None:
        print(f"deploy lock {holder}: wait for the deploy to finish", file=sys.stderr)
    return 1 if found or holder is not None else 0


if __name__ == "__main__":
    sys.exit(main())
