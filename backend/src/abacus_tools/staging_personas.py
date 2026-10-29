"""Bind a synthetic persona to a staging identity-provider user (F-04-T13 staging mode; Q-01-T20;
DEC-1011). Run as the ECS one-off `abacus-ops` task on staging, never from a laptop:

    python -m abacus_tools.staging_personas bind --email <persona email> \
        --issuer <WorkOS issuer> --subject <WorkOS user id> --operator <handle>

The scenario loader creates Brightwater Hale's people with the local fake identity server's issuer
(`abacus_tools.fakes.identity.ISSUER`), so on staging no real sign-in finds them. `bind` repoints
one persona's `(idp_issuer, idp_subject)` at a WorkOS user the builder created (with an inbox they
own), so that person signs in as the persona: Grace Holloway for R-01-T25 and P-07-T50.

Refuses unless `ABACUS_ENVIRONMENT=staging`; refuses a person with no membership, or with any
membership in a firm that is not synthetic (a real person's identity is never moved); refuses an
identity already bound to someone else. Writes through the owner role (the app role cannot touch
`users`), and audits `user.identity_bound` in each of the person's synthetic firms in the same
transaction, naming the person, never the address or the subject.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Final, cast
from uuid import UUID

import asyncpg

from abacus.kernel.config import settings
from abacus_tools.db_connect import connect as connect_db

ACTOR_PREFIX: Final = "operator:"


class BindRefused(Exception):
    """The bind would touch something it must not; the message names why, never a value."""


def _owner_dsn() -> str:
    url = settings().migrations_database_url
    if url is None:
        raise BindRefused("ABACUS_MIGRATIONS_DATABASE_URL (the owner role) is not set")
    return url.get_secret_value().replace("postgresql+asyncpg://", "postgresql://")


def guard_environment() -> None:
    if os.environ.get("ABACUS_ENVIRONMENT") != "staging":
        raise BindRefused("staging_personas runs on staging only")


async def bind(email: str, issuer: str, subject: str, operator: str) -> UUID:
    guard_environment()
    if not issuer.startswith("https://") or not 1 <= len(subject) <= 255:
        raise BindRefused("issuer is an https URL and subject a provider user id")
    connection = await connect_db(_owner_dsn())
    try:
        async with connection.transaction():
            user_id = cast(
                UUID | None,
                await connection.fetchval(
                    "SELECT id FROM users WHERE lower(email) = lower($1) FOR UPDATE", email
                ),
            )
            if user_id is None:
                raise BindRefused("no person with that email")
            firms = await connection.fetch(
                "SELECT m.tenant_id, f.synthetic FROM memberships m "
                "JOIN firms f ON f.tenant_id = m.tenant_id WHERE m.user_id = $1",
                user_id,
            )
            if not firms:
                raise BindRefused("the person has no membership")
            if not all(bool(f["synthetic"]) for f in firms):
                raise BindRefused("the person belongs to a firm that is not synthetic")
            taken = await connection.fetchval(
                "SELECT 1 FROM users WHERE idp_issuer = $1 AND idp_subject = $2 AND id <> $3",
                issuer,
                subject,
                user_id,
            )
            if taken:
                raise BindRefused("that identity is already bound to another person")
            await connection.execute(
                "UPDATE users SET idp_issuer = $1, idp_subject = $2 WHERE id = $3",
                issuer,
                subject,
                user_id,
            )
            actor = f"{ACTOR_PREFIX}{operator}"
            for firm in {cast(UUID, f["tenant_id"]) for f in firms}:
                await connection.execute(
                    "SELECT set_config('app.tenant_id', $1, true), "
                    "set_config('app.actor_kind', 'system', true), "
                    "set_config('app.actor_id', $2, true)",
                    str(firm),
                    actor,
                )
                await connection.execute(
                    "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, "
                    "target_type, target_id, after_ref) VALUES ($1, 'system', $2, "
                    "'user.identity_bound', 'user', $3, $4::jsonb)",
                    firm,
                    actor,
                    str(user_id),
                    json.dumps({"bound": 1}),
                )
    finally:
        await connection.close()
    return user_id


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.staging_personas")
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("bind", help="bind a synthetic persona to a staging identity")
    b.add_argument("--email", required=True)
    b.add_argument("--issuer", required=True)
    b.add_argument("--subject", required=True)
    b.add_argument("--operator", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        user_id = asyncio.run(bind(args.email, args.issuer, args.subject, args.operator))
    except (BindRefused, asyncpg.PostgresError) as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 1
    print(f"bound person {user_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
