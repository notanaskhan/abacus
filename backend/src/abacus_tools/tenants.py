"""Operator commands for tenants (Q-01-T45; ADR-156, P-65; platform-ops contract section 3.5).
Run as an ECS one-off `abacus-ops` task, never from a laptop against a hosted database.

    python -m abacus_tools.tenants provision --name "Canary & Co" --slug canary-co --synthetic \
        --plan pilot --admins admin@sink.example.test --idempotency-key provision-canary-1 \
        --operator <handle>
    python -m abacus_tools.tenants status --tenant <tenant_id>
    make entitlement FIRM=<tenant_id> MODULE=attest ENABLED=true SEATS=10 OPERATOR=<handle> \
        REASON="pilot plan"

`provision` calls `provision_firm(...)` as `abacus_ops` (`ops_database_url`; EXECUTE only, no
table privileges), which refuses any region but `us` and returns the same tenant for the same
idempotency key, then starts `TenantProvisioningWorkflow`; a repeat starts no second workflow.
There is no region argument (ADR-156). `status` is read-only. `entitlement` writes one
`tenant_entitlements` row and its `tenant.entitlements_changed` audit event in one transaction, as
`operator:<handle>`, through the owner role (`migrations_database_url`), as `agent_stage` does:
the app role only reads entitlements and `abacus_ops` has no definer for them yet.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from typing import Final, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import asyncpg
from temporalio.service import RPCError, RPCStatusCode

from abacus.kernel.config import settings
from abacus.kernel.db.session import configure_engine, dispose_engine
from abacus.kernel.temporal import temporal_client
from abacus.modules.identity.api import firm_tenancy
from abacus.modules.platform.api import (
    MODULES,
    OPERATOR_HANDLE,
    Module,
    ProvisionTenantInput,
    entitlement,
    operator_context,
    provisioning_workflow_id,
    start_provisioning,
)

REGION: Final = "us"  # the only region offered (firms.region CHECK; ADR-156)
DEFAULT_TIME_ZONE: Final = "America/New_York"  # firms.time_zone default (migration 0040)
_SLUG = re.compile(r"[a-z0-9][a-z0-9-]{1,62}")
_PLAN = re.compile(r"[a-z][a-z0-9_]{1,40}")  # plans.code (migration 0088)
_MODULES: Final = tuple(sorted(MODULES))


class Refused(Exception):
    """The command was refused before or by the database; nothing was written."""


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


def _operator(operator: str) -> str:
    if not OPERATOR_HANDLE.fullmatch(operator):
        raise Refused("--operator is a lower-case handle, never an email address")
    return operator


@dataclass(frozen=True)
class ProvisionRequest:
    name: str
    slug: str
    synthetic: bool
    plan: str
    admins: tuple[str, ...]
    idempotency_key: str
    operator: str
    time_zone: str = DEFAULT_TIME_ZONE

    def checked(self) -> ProvisionRequest:
        if not 1 <= len(self.name.strip()) <= 200:
            raise Refused("--name is 1 to 200 characters")
        if not _SLUG.fullmatch(self.slug):
            raise Refused("--slug is lower-case letters, digits and '-'")
        if not _PLAN.fullmatch(self.plan):
            raise Refused("--plan is a plan code")
        if not self.admins or any(
            not 3 <= len(a) <= 320 or a.count("@") != 1 for a in self.admins
        ):
            raise Refused("--admins is one or more email addresses, comma-separated")
        if not 8 <= len(self.idempotency_key) <= 200:
            raise Refused("--idempotency-key is 8 to 200 characters")
        try:
            ZoneInfo(self.time_zone)
        except (ZoneInfoNotFoundError, ValueError):
            raise Refused("--time-zone is an IANA time zone") from None
        _operator(self.operator)
        return self


@dataclass(frozen=True)
class ProvisionOutcome:
    tenant_id: UUID
    workflow_id: str
    already_provisioned: bool


async def create_firm(ops_dsn: str, request: ProvisionRequest, *, region: str = REGION) -> UUID:
    """`provision_firm(...)` as `abacus_ops`. `region` exists only so the refusal can be shown;
    the command line has no region argument."""
    connection = await asyncpg.connect(_dsn(ops_dsn))
    try:
        found = await connection.fetchval(
            "SELECT provision_firm($1, $2, $3, $4, $5, $6)",
            request.name.strip(),
            request.synthetic,
            region,
            request.time_zone,
            request.idempotency_key,
            request.operator,
        )
    except asyncpg.CheckViolationError:
        raise Refused(f"region {region!r} is not offered; firms are provisioned in 'us'") from None
    finally:
        await connection.close()
    return cast(UUID, found)


async def provision(ops_dsn: str, request: ProvisionRequest) -> ProvisionOutcome:
    """The firm (or the one this idempotency key already made), then its provisioning workflow."""
    request = request.checked()
    tenant_id = await create_firm(ops_dsn, request)
    started = await start_provisioning(
        ProvisionTenantInput(
            tenant_id=str(tenant_id),
            slug=request.slug,
            synthetic=request.synthetic,
            plan=request.plan,
            admins=request.admins,
            idempotency_key=request.idempotency_key,
            operator=request.operator,
        )
    )
    return ProvisionOutcome(tenant_id, provisioning_workflow_id(str(tenant_id)), not started)


async def workflow_state(tenant_id: UUID) -> str | None:
    """The provisioning run's Temporal status (`RUNNING`, `COMPLETED`, ...), or None."""
    client = await temporal_client()
    handle = client.get_workflow_handle(provisioning_workflow_id(str(tenant_id)))
    try:
        described = await handle.describe()
    except RPCError as exc:
        if exc.status == RPCStatusCode.NOT_FOUND:
            return None
        raise
    return described.status.name if described.status is not None else None


async def status(tenant_id: UUID, *, with_workflow: bool = True) -> dict[str, object]:
    """Read-only: the firm's region, synthetic flag, key state, entitlements and workflow."""
    ctx = operator_context(tenant_id, "status")
    facts = await firm_tenancy(ctx)
    if facts is None:
        raise Refused("no such firm")
    held: dict[str, int | None] = {}
    for module in _MODULES:
        found = await entitlement(ctx, cast(Module, module))
        if found is not None:
            held[module] = found.seats
    return {
        "tenant_id": str(tenant_id),
        "synthetic": facts.synthetic,
        "region": facts.region,
        "key_status": facts.kms_key_status,
        "key_ready": facts.kms_key_status == "replica_verified",
        "entitlements": held,
        "workflow": await workflow_state(tenant_id) if with_workflow else None,
    }


async def set_entitlement(
    owner_dsn: str,
    *,
    firm: UUID,
    module: str,
    enabled: bool,
    seats: int | None,
    operator: str,
    reason: str,
) -> None:
    """One `tenant_entitlements` row and `tenant.entitlements_changed`, in one transaction."""
    _operator(operator)
    if module not in MODULES:
        raise Refused(f"--module is one of {', '.join(_MODULES)}")
    if seats is not None and seats < 0:
        raise Refused("--seats is zero or more")
    reason = reason.strip()
    if not 1 <= len(reason) <= 200:
        raise Refused("--reason is 1 to 200 characters, with no client data")
    actor = f"operator:{operator}"
    connection = await asyncpg.connect(_dsn(owner_dsn))
    try:
        await connection.execute(
            "SELECT set_config('app.tenant_id', $1, false), "
            "set_config('app.actor_kind', 'system', false), set_config('app.actor_id', $2, false)",
            str(firm),
            actor,
        )
        async with connection.transaction():
            # A new row is valid from the firm's business date, not the server's (a firm west
            # of UTC is still on yesterday); a changed row keeps its dates.
            today = await connection.fetchval(
                "SELECT (clock_timestamp() AT TIME ZONE time_zone)::date FROM firms"
            )
            if today is None:
                raise Refused("no such firm")
            await connection.execute(
                "INSERT INTO tenant_entitlements (tenant_id, module, enabled, seats, set_by, "
                "valid_from) VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT (tenant_id, module) "
                "DO UPDATE SET enabled = EXCLUDED.enabled, seats = EXCLUDED.seats, "
                "set_by = EXCLUDED.set_by",
                firm,
                module,
                enabled,
                seats,
                operator,
                today,
            )
            # Audit references hold identifiers and fingerprints only (TASK-026 D2).
            after: dict[str, int | str] = {
                "module": _MODULES.index(module),
                "enabled": int(enabled),
                "reason": hashlib.sha256(reason.encode()).hexdigest(),
            }
            if seats is not None:
                after["seats"] = seats
            await connection.execute(
                "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, "
                "target_type, target_id, after_ref) VALUES ($1, 'system', $2, "
                "'tenant.entitlements_changed', 'firm', $3, $4::jsonb)",
                firm,
                actor,
                str(firm),
                json.dumps(after),
            )
    finally:
        await connection.close()


def _boolean(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered not in ("true", "false"):
        raise argparse.ArgumentTypeError("true or false")
    return lowered == "true"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.tenants")
    sub = parser.add_subparsers(dest="command", required=True)
    provisioning = sub.add_parser("provision")
    provisioning.add_argument("--name", required=True)
    provisioning.add_argument("--slug", required=True)
    provisioning.add_argument("--synthetic", action="store_true")
    provisioning.add_argument("--plan", required=True)
    provisioning.add_argument("--admins", required=True, help="comma-separated email addresses")
    provisioning.add_argument("--idempotency-key", required=True)
    provisioning.add_argument("--operator", required=True)
    provisioning.add_argument("--time-zone", default=DEFAULT_TIME_ZONE)
    showing = sub.add_parser("status")
    showing.add_argument("--tenant", type=UUID, required=True)
    entitling = sub.add_parser("entitlement")
    entitling.add_argument("--firm", type=UUID, required=True)
    entitling.add_argument("--module", required=True, choices=_MODULES)
    entitling.add_argument("--enabled", type=_boolean, required=True)
    entitling.add_argument("--seats", type=int, default=None)
    entitling.add_argument("--operator", required=True)
    entitling.add_argument("--reason", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    s = settings()
    try:
        if args.command == "entitlement":
            if s.migrations_database_url is None:
                raise Refused("migrations_database_url (the owner role) is not set")
            owner = s.migrations_database_url.get_secret_value()
            asyncio.run(
                set_entitlement(
                    owner,
                    firm=args.firm,
                    module=args.module,
                    enabled=args.enabled,
                    seats=args.seats,
                    operator=args.operator,
                    reason=args.reason,
                )
            )
            print(f"{args.module} for {args.firm}: enabled={args.enabled} seats={args.seats}")
            return 0
        if s.database_url is None:
            raise Refused("database_url is not set")
        app = s.database_url.get_secret_value()
        if args.command == "provision":
            if s.ops_database_url is None:
                raise Refused("ops_database_url (the abacus_ops role) is not set")
            ops = s.ops_database_url.get_secret_value()
            request = ProvisionRequest(
                name=args.name,
                slug=args.slug,
                synthetic=args.synthetic,
                plan=args.plan,
                admins=tuple(a.strip() for a in str(args.admins).split(",") if a.strip()),
                idempotency_key=args.idempotency_key,
                operator=args.operator,
                time_zone=args.time_zone,
            )

            async def run_provision() -> ProvisionOutcome:
                configure_engine(app)
                try:
                    return await provision(ops, request)
                finally:
                    await dispose_engine()

            outcome = asyncio.run(run_provision())
            print(json.dumps({**asdict(outcome), "tenant_id": str(outcome.tenant_id)}))
            return 0

        async def run_status() -> dict[str, object]:
            configure_engine(app)
            try:
                return await status(args.tenant)
            finally:
                await dispose_engine()

        print(json.dumps(asyncio.run(run_status())))
        return 0
    except Refused as refused:
        print(str(refused), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
