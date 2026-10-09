"""Sign-up codes for design partners (SPEC-024 Q1; TASK-040 D2). Founder tooling, never the app.

    python -m abacus_tools.signup_codes issue --note "Design partner: Whitfield & Lane" [--days 30]
    python -m abacus_tools.signup_codes list

A code is printed once and stored only as its SHA-256; it is single-use and expires. Runs as
the owner role (`migrations_database_url`): the app role has no access to `signup_codes`.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import secrets
import sys
from datetime import UTC, datetime, timedelta

import asyncpg

from abacus.kernel.config import settings


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


def new_code() -> str:
    """Grouped for reading aloud: ABCD-EFGH-JKMN-PQRS (no 0/O/1/I/L)."""
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    raw = "".join(secrets.choice(alphabet) for _ in range(16))
    return "-".join(raw[i : i + 4] for i in range(0, 16, 4))


async def issue(url: str, note: str, days: int) -> str:
    code = new_code()
    connection = await asyncpg.connect(_dsn(url))
    try:
        await connection.execute(
            "INSERT INTO signup_codes (code_hash, note, expires_at) VALUES ($1, $2, $3)",
            hashlib.sha256(code.encode()).hexdigest(),
            note,
            datetime.now(UTC) + timedelta(days=days),
        )
    finally:
        await connection.close()
    return code


async def listing(url: str) -> list[asyncpg.Record]:
    connection = await asyncpg.connect(_dsn(url))
    try:
        return await connection.fetch(
            "SELECT note, created_at, expires_at, used_at, used_tenant_id "
            "FROM signup_codes ORDER BY created_at DESC LIMIT 100"
        )
    finally:
        await connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="signup-codes")
    sub = parser.add_subparsers(dest="command", required=True)
    issuing = sub.add_parser("issue")
    issuing.add_argument("--note", required=True)
    issuing.add_argument("--days", type=int, default=30)
    sub.add_parser("list")
    args = parser.parse_args(argv)
    url = settings().migrations_database_url
    if url is None:
        print(
            "migrations_database_url is not set (the owner role holds the codes)", file=sys.stderr
        )
        return 2
    if args.command == "issue":
        note = str(args.note).strip()
        if not 1 <= len(note) <= 200 or not 1 <= args.days <= 90:
            print("a note of 1-200 characters and 1-90 days, please", file=sys.stderr)
            return 2
        code = asyncio.run(issue(url.get_secret_value(), note, args.days))
        print(f"sign-up code (shown once): {code}")
        return 0
    for row in asyncio.run(listing(url.get_secret_value())):
        state = (
            "used"
            if row["used_at"]
            else ("expired" if row["expires_at"] < datetime.now(UTC) else "open")
        )
        print(f"{row['created_at']:%Y-%m-%d}  {state:8}  {row['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
