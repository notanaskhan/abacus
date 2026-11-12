"""The runtime load test's stream subjects (P-10-T51; TASK-7428; DEC-4412).

`scenarios/runtime_v2.yaml` holds 1,500 streams; the API caps a person at 6, so the streams sign
in as `count` synthetic staff `<prefix>-0000`, `-0001`, … (`Stream.subjects`). This loads them
on Brightwater Hale (the synthetic firm, PF-X1), each staffed on the engagement the scenario's
topic names so `engagement:<id>` authorises, with the local sign-in issuer (on the perf stack,
`staging_personas` binds an identity where one is needed).

    python -m abacus_tools.loadtest.stream_subjects --engagement <id> [--count 250] [--staging]

The same guards as the load profiles (`synthetic.fleet`): loopback or the perf stack only, never
a firm that is not synthetic, never while a deploy holds the lock. Idempotent: each subject is one
loader step with its own trace, so a second run writes nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import sys
from dataclasses import dataclass
from datetime import timedelta
from typing import Final
from uuid import UUID

import asyncpg

from abacus.kernel.config import settings
from abacus_tools.db_connect import connect as connect_db
from abacus_tools.fakes.identity import ISSUER
from abacus_tools.loadtest.scenario import STREAMS_PER_SUBJECT, profile
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import (
    DEFAULT_SUPERUSER,
    SUPERUSER_ENV,
    TENANT,
    LoadRefused,
    bootstrap_write,
    guard,
    tenant_value,
)
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT

PREFIX: Final = "loadtest-stream"
LOADER: Final = "loadtest:stream_subjects"
VERSION: Final = "v1"
MAX_SUBJECTS: Final = 400  # 2,000 streams (the scenario's ceiling) / 6 per person, rounded up


def subjects_for(stream_count: int) -> int:
    """How many subjects `stream_count` streams need at the API's per-person cap."""
    return -(-stream_count // STREAMS_PER_SUBJECT)


def runtime_subjects() -> int:
    """The runtime scenario's own need (250 for 1,500 streams)."""
    (stream,) = profile("runtime_v2").streams
    return subjects_for(stream.count)


def subject(prefix: str, k: int) -> str:
    return f"{prefix}-{k:04d}"


def subject_user(prefix: str, k: int) -> UUID:
    return UUID(stable_id(f"loadtest-user:{prefix}:{k}"))


def _trace(prefix: str, engagement: UUID, k: int) -> str:
    key = f"stream_subjects:{VERSION}:{prefix}:{engagement}:{k}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


@dataclass(frozen=True)
class Result:
    written: int
    skipped: int


async def _done(conn: asyncpg.Connection, trace: str) -> bool:
    return bool(
        await tenant_value(
            conn,
            TENANT,
            "SELECT EXISTS (SELECT 1 FROM audit_events WHERE tenant_id = $1 AND trace_id = $2)",
            TENANT,
            trace,
        )
    )


async def load(
    dsn: str, engagement: UUID, *, count: int, prefix: str = PREFIX, staging: bool = False
) -> Result:
    if not 1 <= count <= MAX_SUBJECTS:
        raise LoadRefused(f"count is 1 to {MAX_SUBJECTS}")
    guard(dsn, staging=staging)
    conn = await connect_db(dsn)
    written = skipped = 0
    try:
        synthetic = await tenant_value(
            conn, TENANT, "SELECT synthetic FROM firms WHERE tenant_id = $1", TENANT
        )
        if synthetic is not True:
            raise LoadRefused("the stream subjects load only on the synthetic firm (PF-X1)")
        found = await tenant_value(
            conn,
            TENANT,
            # Explicit: the owner role is not held to RLS.
            "SELECT id FROM engagements WHERE id = $1 AND tenant_id = $2",
            engagement,
            TENANT,
        )
        if found is None:
            raise LoadRefused("the engagement is not the synthetic firm's")
        for k in range(count):
            trace = _trace(prefix, engagement, k)
            if await _done(conn, trace):
                skipped += 1
                continue
            user = subject_user(prefix, k)

            async def write(k: int = k, user: UUID = user) -> tuple[str, str, str]:
                await conn.execute(
                    "INSERT INTO users (id, idp_issuer, idp_subject, email, display_name) "
                    "VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
                    user,
                    ISSUER,
                    subject(prefix, k),
                    f"{subject(prefix, k)}@loadtest.invalid",
                    f"Load stream {k + 1:04d}",
                )
                await conn.execute(
                    "INSERT INTO memberships (tenant_id, user_id, status, kind, initials, "
                    "created_at) VALUES ($1, $2, 'active', 'staff', 'LS', $3) "
                    "ON CONFLICT DO NOTHING",
                    TENANT,
                    user,
                    SETUP_AT + timedelta(microseconds=k),
                )
                await conn.execute(
                    "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
                    "VALUES ($1, $2, $3, 'staff') ON CONFLICT DO NOTHING",
                    TENANT,
                    engagement,
                    user,
                )
                return "membership.created", "user", str(user)

            await bootstrap_write(
                conn,
                tenant=TENANT,
                actor_kind="system",
                actor_id=LOADER,
                at=SETUP_AT,
                trace=trace,
                write=write,
            )
            written += 1
    finally:
        await conn.close()
    return Result(written, skipped)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load the runtime load test's stream subjects.")
    parser.add_argument("--engagement", required=True, type=UUID)
    parser.add_argument("--count", type=int, default=None)
    parser.add_argument("--prefix", default=PREFIX)
    parser.add_argument("--staging", action="store_true")
    args = parser.parse_args(argv)
    owner = settings().migrations_database_url
    dsn = (
        owner.get_secret_value()
        if args.staging and owner is not None
        else os.environ.get(SUPERUSER_ENV, DEFAULT_SUPERUSER)
    )
    count = args.count if args.count is not None else runtime_subjects()
    try:
        result = asyncio.run(
            load(dsn, args.engagement, count=count, prefix=args.prefix, staging=args.staging)
        )
    except LoadRefused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 1
    print(f"stream subjects: {result.written} written, {result.skipped} already loaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
