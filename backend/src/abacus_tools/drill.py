"""Restore-drill verification (Q-01-T38; Q-01 F9; ADR-093, ADR-096). Run as an ECS one-off
`abacus-ops` task by `drill.yml`, against a point-in-time restore in the drill subnet; never from
a laptop. Read only: it changes nothing on the source or the restored instance.

    python -m abacus_tools.drill verify --env production --restored-host <endpoint> \
        --restore-point 2026-12-08T03:14:00Z --restore-started-at 2026-12-10T15:00:02Z \
        --rpo-lag-seconds 212 --replica-bucket <bucket>

The source is the configured owner and app URLs (`migrations_database_url`, `database_url`); the
restored instance is the same URLs with the host swapped (a restore keeps roles and passwords),
so no credential passes through the workflow. Checks, each up to the cutoff (the restore point
minus the settle window, so a transaction still committing at the restore point is not a
mismatch):

- **Which firms.** Every firm the platform created (`firm_provisioning_requests`, used signup
  codes; global tables the owner reads), on either side, plus any named with `--tenant`. Each
  firm's rows are read as the app role under that firm's own context (`tenant_session`): the
  owner is subject to forced row-level security, and no read crosses firms.
- **Row counts.** Every insert-only table with `tenant_id`, a creation timestamp and the app's
  SELECT grant, per firm, must match the source. Tables that update or delete rows are listed as
  unchecked: the source has moved on since the restore point.
- **Sequence continuity.** `audit_events.seq` is one global identity, so continuity is checked
  against the source: the restored instance holds every `seq` the source holds, per firm. The
  first missing one is named.
- **Evidence sample.** 1% of evidence versions, at least 50 (all when fewer), read through
  `evidence.api.read_content` from the replica bucket with the KMS key service in the replica
  region: the tenant binding, the envelope, the SHA-256 fingerprint and the size are checked.
- **Seal recompute.** Registered checks (`register_seal_check`); v1 recomputes each firm's audit
  hash chain (Q-02-T21). P-43/A-07 add seal manifests.

The report is JSON of codes, counts and identifiers only, never content, with the restore-to-
verified time and whether the RPO lag was within 5 minutes. Exit 1 when anything fails.

Guards (security review, S8 wave B): the restored host decides where the production owner and
app passwords go, so it must be the drill's own restore, `abacus-drill-<run id>.<id>.<us-east-2
or us-west-2>.rds.amazonaws.com` (drill.yml names the instance after its run), and the task must
set `ABACUS_DATABASE_CA_FILE` to the RDS CA bundle so every connection verifies the server
(verify-full). Both are checked before anything connects; a refusal exits 2. The command is not
an ops-request command: it runs only from drill.yml.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import secrets
import sys
from collections.abc import AsyncGenerator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final, cast
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

import asyncpg
from sqlalchemy import text

from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.crypto import KmsKeyService, configure_key_service
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus.kernel.storage import kms_client, s3_client
from abacus.kernel.uow.chain import verify_chain
from abacus.modules.evidence.api import StoredObject, configure_storage, read_content
from abacus_tools.db_connect import connect
from abacus_tools.quality.schema_check import INSERT_ONLY_TABLES

RPO_SECONDS: Final = 300  # ADR-093: a restore loses at most 5 minutes
SAMPLE_SHARE: Final = 0.01
SAMPLE_MINIMUM: Final = 50
SETTLE_SECONDS: Final = 300
_TIMESTAMPS: Final = ("created_at", "occurred_at", "recorded_at")
_DRILL_ACTOR: Final = "drill:verify"
# drill.yml restores to `abacus-drill-<github run id>`; RDS endpoints are
# `<instance>.<account-specific id>.<region>.rds.amazonaws.com`, in the two permitted regions.
_DRILL_HOST: Final = re.compile(
    r"abacus-drill-[0-9]{1,20}\.[a-z0-9]{6,20}\.(?:us-east-2|us-west-2)\.rds\.amazonaws\.com"
)


class Refused(Exception):
    """A guard refused the drill before it connected to anything."""


def check_restored_host(host: str) -> str:
    """The drill instance's RDS endpoint, or `Refused`: the passwords go nowhere else."""
    if not _DRILL_HOST.fullmatch(host):
        raise Refused(
            "--restored-host must be the drill's own restore, "
            "abacus-drill-<run id>.<id>.<us-east-2|us-west-2>.rds.amazonaws.com"
        )
    return host


def check_ca_file(ca_file: str | None) -> str:
    """The RDS CA bundle every drill connection verifies the server against (verify-full)."""
    if not ca_file or not Path(ca_file).is_file():
        raise Refused("ABACUS_DATABASE_CA_FILE must name the RDS CA bundle (verify-full)")
    return ca_file


@dataclass(frozen=True)
class Side:
    """One database as the drill reads it: the owner URL for the catalogue and the firm
    registries, the app URL for each firm's rows under its own context."""

    owner_url: str
    app_url: str

    async def owner_fetch(self, sql: str, *args: object) -> list[asyncpg.Record]:
        conn = await connect(self.owner_url)
        try:
            async with conn.transaction(readonly=True):
                return list(await conn.fetch(sql, *args))
        finally:
            await conn.close()

    @asynccontextmanager
    async def firms(self) -> AsyncGenerator[None]:
        """The app engine on this side while the block runs (one engine at a time)."""
        await dispose_engine()
        configure_engine(self.app_url)
        try:
            yield
        finally:
            await dispose_engine()


def _firm(tenant: UUID) -> TenantContext:
    return TenantContext(tenant, "system", _DRILL_ACTOR)


async def _rows(tenant: UUID, sql: str, **params: object) -> list[tuple[object, ...]]:
    async with tenant_session(_firm(tenant)) as session:
        return [tuple(r) for r in (await session.execute(text(sql), params)).all()]


@dataclass(frozen=True)
class CountMismatch:
    table: str
    tenant_id: str
    source: int
    restored: int


@dataclass(frozen=True)
class SequenceGap:
    tenant_id: str
    first_missing_seq: int
    missing: int


@dataclass(frozen=True)
class EvidenceMismatch:
    tenant_id: str
    evidence_version_id: str
    reason: str  # the refusal's class name: never its text


@dataclass(frozen=True)
class SealMismatch:
    check: str
    tenant_id: str
    detail: str  # checkpoint numbers or codes only


@dataclass
class DrillReport:
    env: str
    restore_point: str
    cutoff: str
    tenants: int = 0
    tables_checked: list[str] = field(default_factory=list[str])
    tables_unchecked: list[str] = field(default_factory=list[str])
    count_mismatches: list[CountMismatch] = field(default_factory=list[CountMismatch])
    sequence_gaps: list[SequenceGap] = field(default_factory=list[SequenceGap])
    evidence_population: int = 0
    evidence_sampled: int = 0
    evidence_mismatches: list[EvidenceMismatch] = field(default_factory=list[EvidenceMismatch])
    seal_checks: list[str] = field(default_factory=list[str])
    seal_mismatches: list[SealMismatch] = field(default_factory=list[SealMismatch])
    restore_started_at: str | None = None
    verified_at: str | None = None
    restore_to_verified_seconds: float | None = None
    rpo_lag_seconds: float | None = None
    rpo_ok: bool | None = None

    @property
    def passed(self) -> bool:
        return not (
            self.count_mismatches
            or self.sequence_gaps
            or self.evidence_mismatches
            or self.seal_mismatches
            or self.rpo_ok is False
        )

    def as_json(self) -> str:
        return json.dumps({**asdict(self), "passed": self.passed}, sort_keys=True)


# --- Which firms and tables ------------------------------------------------------------------

# Every firm the platform created: `provision_firm` records each in `firm_provisioning_requests`
# and `firm_signup` marks the code it used (both global tables the owner reads). A firm inserted
# any other way (a local seed) is named with `--tenant`.
_TENANTS = (
    "SELECT tenant_id FROM firm_provisioning_requests "
    "UNION SELECT used_tenant_id FROM signup_codes WHERE used_tenant_id IS NOT NULL"
)
_COLUMNS = """
SELECT c.table_name::text, array_agg(c.column_name::text),
       has_table_privilege($1, quote_ident(c.table_name), 'SELECT')
  FROM information_schema.columns c
  JOIN information_schema.tables t
    ON t.table_schema = c.table_schema AND t.table_name = c.table_name
 WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE'
 GROUP BY c.table_name
"""


async def tenant_universe(*sides: Side, extra: Sequence[UUID] = ()) -> list[UUID]:
    found: set[UUID] = set(extra)
    for side in sides:
        found |= {cast(UUID, r[0]) for r in await side.owner_fetch(_TENANTS)}
    return sorted(found)


def _role_of(url: str) -> str:
    return urlsplit(url).username or ""


async def comparable_tables(side: Side) -> tuple[dict[str, str], list[str]]:
    """Insert-only tables with `tenant_id`, a creation timestamp and the app's SELECT grant
    (table -> its timestamp column), and the tenant tables left unchecked."""
    checked: dict[str, str] = {}
    unchecked: list[str] = []
    rows = [tuple(r) for r in await side.owner_fetch(_COLUMNS, _role_of(side.app_url))]
    for table_name, names, readable in sorted(rows, key=lambda r: str(r[0])):
        table, columns = str(table_name), set(cast(list[str], names))
        stamp = next((c for c in _TIMESTAMPS if c in columns), None)
        if "tenant_id" not in columns:
            continue
        if table in INSERT_ONLY_TABLES and stamp is not None and bool(readable):
            checked[table] = stamp
        else:
            unchecked.append(table)
    return checked, unchecked


# --- One side's facts ----------------------------------------------------------------------------

_SEQ_SUMMARY = (
    "SELECT count(*), coalesce(sum(seq), 0)::text FROM audit_events WHERE occurred_at <= :cutoff"
)
_SEQS = "SELECT seq FROM audit_events WHERE occurred_at <= :cutoff"


@dataclass
class Facts:
    counts: dict[tuple[str, UUID], int] = field(default_factory=dict[tuple[str, UUID], int])
    sequences: dict[UUID, tuple[object, ...]] = field(
        default_factory=dict[UUID, tuple[object, ...]]
    )


def _count_sql(table: str, stamp: str) -> str:
    # Names come from the catalogue and the insert-only registry, never from input.
    return f'SELECT count(*) FROM "{table}" WHERE "{stamp}" <= :cutoff'


async def facts(
    side: Side, tables: dict[str, str], tenants: Sequence[UUID], cutoff: datetime
) -> Facts:
    found = Facts()
    async with side.firms():
        for tenant in tenants:
            for table, stamp in tables.items():
                [(count,)] = await _rows(tenant, _count_sql(table, stamp), cutoff=cutoff)
                found.counts[(table, tenant)] = int(cast(int, count))
            [summary] = await _rows(tenant, _SEQ_SUMMARY, cutoff=cutoff)
            found.sequences[tenant] = summary
    return found


async def _seqs(side: Side, tenant: UUID, cutoff: datetime) -> set[int]:
    async with side.firms():
        return {int(cast(int, r[0])) for r in await _rows(tenant, _SEQS, cutoff=cutoff)}


def count_mismatches(want: Facts, have: Facts) -> list[CountMismatch]:
    return [
        CountMismatch(table, str(tenant), count, have.counts.get((table, tenant), 0))
        for (table, tenant), count in sorted(want.counts.items(), key=lambda kv: str(kv[0]))
        if have.counts.get((table, tenant), 0) != count
    ]


async def sequence_gaps(
    source: Side, restored: Side, want: Facts, have: Facts, cutoff: datetime
) -> list[SequenceGap]:
    gaps: list[SequenceGap] = []
    for tenant, summary in sorted(want.sequences.items(), key=lambda kv: str(kv[0])):
        if have.sequences.get(tenant) == summary:
            continue
        expected = await _seqs(source, tenant, cutoff)
        held = await _seqs(restored, tenant, cutoff)
        missing = sorted(expected - held)
        if missing:
            gaps.append(SequenceGap(str(tenant), missing[0], len(missing)))
    return gaps


# --- Evidence sample ---------------------------------------------------------------------------

_POPULATION = "SELECT id FROM evidence_versions WHERE created_at <= :cutoff"
_VERSION = (
    "SELECT storage_key, storage_version_id, fingerprint, size_bytes FROM evidence_versions "
    "WHERE id = :id"
)
Fetch = Callable[[TenantContext, StoredObject], Awaitable[bytes]]


def sample_size(population: int) -> int:
    """1%, at least 50, never more than there are."""
    return min(population, max(SAMPLE_MINIMUM, math.ceil(population * SAMPLE_SHARE)))


async def check_evidence(
    restored: Side, cutoff: datetime, fetch: Fetch, tenants: Sequence[UUID]
) -> tuple[int, int, list[EvidenceMismatch]]:
    bad: list[EvidenceMismatch] = []
    async with restored.firms():
        population = [
            (tenant, cast(UUID, r[0]))
            for tenant in tenants
            for r in await _rows(tenant, _POPULATION, cutoff=cutoff)
        ]
        chosen = secrets.SystemRandom().sample(population, sample_size(len(population)))
        for tenant, version in chosen:
            [row] = await _rows(tenant, _VERSION, id=version)
            stored = StoredObject(str(row[0]), str(row[1]), str(row[2]), int(cast(int, row[3])))
            try:
                await fetch(_firm(tenant), stored)  # binding, envelope, fingerprint and size
            except Exception as exc:  # any refusal is a mismatch, named by its class only
                bad.append(EvidenceMismatch(str(tenant), str(version), type(exc).__name__))
    return len(population), len(chosen), bad


# --- Seal recompute hook -------------------------------------------------------------------------

SealCheck = Callable[[Sequence[UUID]], Awaitable[list[SealMismatch]]]
_SEAL_CHECKS: dict[str, SealCheck] = {}


def register_seal_check(name: str, check: SealCheck) -> None:
    """P-43/A-07: recompute a kind of seal on the restored instance (run with its app engine)."""
    if name in _SEAL_CHECKS:
        raise ValueError(f"seal check {name!r} is registered twice")
    _SEAL_CHECKS[name] = check


async def _audit_chain(tenants: Sequence[UUID]) -> list[SealMismatch]:
    """Q-02-T21: each firm's checkpoints recompute to its recorded chain (a firm with no
    checkpoint has nothing to recompute)."""
    found: list[SealMismatch] = []
    for tenant in tenants:
        bad = await verify_chain(tenant)
        if bad:
            found.append(SealMismatch("audit_chain", str(tenant), ",".join(map(str, bad))))
    return found


register_seal_check("audit_chain", _audit_chain)


# --- The drill ---------------------------------------------------------------------------------


async def verify(
    *,
    env: str,
    source: Side,
    restored: Side,
    restore_point: datetime,
    fetch: Fetch = read_content,
    settle: timedelta = timedelta(seconds=SETTLE_SECONDS),
    restore_started_at: datetime | None = None,
    rpo_lag_seconds: float | None = None,
    seal_checks: Sequence[str] | None = None,
    extra_tenants: Sequence[UUID] = (),
) -> DrillReport:
    cutoff = restore_point - settle
    report = DrillReport(env, restore_point.isoformat(), cutoff.isoformat())
    tenants = await tenant_universe(source, restored, extra=extra_tenants)
    report.tenants = len(tenants)
    tables, report.tables_unchecked = await comparable_tables(restored)
    report.tables_checked = sorted(tables)
    want = await facts(source, tables, tenants, cutoff)
    have = await facts(restored, tables, tenants, cutoff)
    report.count_mismatches = count_mismatches(want, have)
    report.sequence_gaps = await sequence_gaps(source, restored, want, have, cutoff)
    (
        report.evidence_population,
        report.evidence_sampled,
        report.evidence_mismatches,
    ) = await check_evidence(restored, cutoff, fetch, tenants)
    names = list(_SEAL_CHECKS) if seal_checks is None else list(seal_checks)
    async with restored.firms():
        for name in names:
            report.seal_mismatches.extend(await _SEAL_CHECKS[name](tenants))
    report.seal_checks = names
    verified = system_now()
    report.verified_at = verified.isoformat()
    if restore_started_at is not None:
        report.restore_started_at = restore_started_at.isoformat()
        report.restore_to_verified_seconds = (verified - restore_started_at).total_seconds()
    if rpo_lag_seconds is not None:
        report.rpo_lag_seconds = rpo_lag_seconds
        report.rpo_ok = rpo_lag_seconds <= RPO_SECONDS
    return report


def with_host(url: str, host: str) -> str:
    """The same URL on another host (the restored instance keeps roles and passwords)."""
    parts = urlsplit(url)
    credentials = parts.netloc.rpartition("@")[0]
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{credentials}@{host}{port}" if credentials else f"{host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("an ISO 8601 time with an offset")
    return parsed


async def _run_verify(args: argparse.Namespace) -> DrillReport:
    s = settings()
    if s.migrations_database_url is None or s.database_url is None:
        raise Refused("the owner and app database URLs must be set")
    owner = s.migrations_database_url.get_secret_value()
    app = s.database_url.get_secret_value()
    # Evidence reads go to the replica bucket through the replica region's key (P-65 aliases
    # exist in both regions).
    configure_key_service(
        KmsKeyService(
            kms_client(region=s.kms_replica_region),
            alias_prefix=s.kms_alias_prefix,
            platform_key=s.kms_platform_key_alias,
        )
    )
    configure_storage(s3_client(region=args.replica_region), args.replica_bucket)
    return await verify(
        env=args.env,
        source=Side(owner, app),
        restored=Side(with_host(owner, args.restored_host), with_host(app, args.restored_host)),
        restore_point=args.restore_point,
        settle=timedelta(seconds=args.settle_seconds),
        restore_started_at=args.restore_started_at,
        rpo_lag_seconds=args.rpo_lag_seconds,
        extra_tenants=tuple(args.tenant),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.drill")
    sub = parser.add_subparsers(dest="command", required=True)
    verifying = sub.add_parser("verify")
    verifying.add_argument("--env", required=True, choices=("staging", "production"))
    verifying.add_argument("--restored-host", required=True)
    verifying.add_argument("--restore-point", required=True, type=_instant)
    verifying.add_argument("--restore-started-at", type=_instant)
    verifying.add_argument("--rpo-lag-seconds", type=float)
    verifying.add_argument("--settle-seconds", type=int, default=SETTLE_SECONDS)
    verifying.add_argument("--replica-bucket", required=True)
    verifying.add_argument("--replica-region", default="us-west-2")
    verifying.add_argument("--tenant", action="append", type=UUID, default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        check_restored_host(args.restored_host)
        check_ca_file(settings().database_ca_file)
        report = asyncio.run(_run_verify(args))
    except Refused as refused:
        print(f"refused: {refused}", file=sys.stderr)
        return 2
    print(report.as_json())
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
