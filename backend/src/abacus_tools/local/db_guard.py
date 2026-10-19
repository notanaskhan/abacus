"""Refuse to run a local database target against a hosted database (F-01-T09).

Run: python -m abacus_tools.local.db_guard

Exits 1, naming the setting (never its value), when any database URL the settings resolve to has
a host outside the local stack. `make migrate`, `make seed`, `make seed-staging` and
`make loadtest` run it first. Sanctioned operator flows against staging arrive with Q-01, with
their own checks (deploy in flight, deploy lock).
"""

from __future__ import annotations

import sys
from urllib.parse import urlsplit

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


def main() -> int:
    found = violations()
    for name in found:
        print(f"{name}: never point a local run at a hosted database", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
