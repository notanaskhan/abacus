"""Kill switches, the operator's command (Q-01-T36, T37; P-66; platform-ops contract section 3.7).
Run as an ECS one-off `abacus-ops` task, never from a laptop against a hosted database.

    python -m abacus_tools.platform_control set --control ai_pause --scope platform --on \
        --operator <handle> --reason "SEV1: provider returning another firm's text"
    python -m abacus_tools.platform_control set --control read_only --scope firm \
        --tenant <tenant_id> --off --operator <handle> --reason "restore verified"
    python -m abacus_tools.platform_control set --control model_route_block --scope platform \
        --route bedrock --on --operator <handle> --reason "regional outage"
    python -m abacus_tools.platform_control list

`set` calls `set_platform_control(...)` as `abacus_ops` (`ops_database_url`; EXECUTE only), which
upserts the row, appends to the insert-only `platform_control_changes` and, for a firm, writes
`platform_control.changed` into that firm's audit trail as `operator:<handle>`. Every process
sees the change within the controls cache (10 seconds). `list` reads the active rows through
`platform_control_state()` as the app role. `portal_sign_in` is the P-08 BFF's per-firm switch.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from typing import Final, cast
from uuid import UUID

from abacus.kernel.config import settings
from abacus.modules.platform.api import OPERATOR_HANDLE
from abacus_tools.db_connect import connect as connect_db

CONTROLS: Final = ("ai_pause", "model_route_block", "email_pause", "read_only", "portal_sign_in")
_FIRM_ONLY: Final = frozenset({"portal_sign_in"})
_PLATFORM_ONLY: Final = frozenset({"model_route_block"})
ROUTES: Final = ("direct", "bedrock")


class Refused(Exception):
    """The command was refused before or by the database; nothing was written."""


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


@dataclass(frozen=True)
class ControlChange:
    control: str
    scope: str
    tenant: UUID | None
    route: str | None
    active: bool
    operator: str
    reason: str
    request_ref: str | None = None

    def checked(self) -> ControlChange:
        if self.control not in CONTROLS:
            raise Refused(f"--control is one of {', '.join(CONTROLS)}")
        if self.scope not in ("platform", "firm"):
            raise Refused("--scope is platform or firm")
        if (self.scope == "firm") != (self.tenant is not None):
            raise Refused("--tenant is given for a firm, and only for a firm")
        if self.control in _FIRM_ONLY and self.scope != "firm":
            raise Refused(f"{self.control} is set per firm")
        if self.control in _PLATFORM_ONLY and self.scope != "platform":
            raise Refused(f"{self.control} is set for the platform")
        if (self.control == "model_route_block") != (self.route is not None):
            raise Refused("--route is given for model_route_block, and only for it")
        if self.route is not None and self.route not in ROUTES:
            raise Refused(f"--route is one of {', '.join(ROUTES)}")
        if not OPERATOR_HANDLE.fullmatch(self.operator):
            raise Refused("--operator is a lower-case handle, never an email address")
        if not 1 <= len(self.reason.strip()) <= 200:
            raise Refused("--reason is 1 to 200 characters")
        if self.request_ref is not None and not 1 <= len(self.request_ref) <= 200:
            raise Refused("--request-ref is 1 to 200 characters")
        return self


async def set_control(ops_dsn: str, change: ControlChange) -> int:
    """The row's new version, written through `set_platform_control` as `abacus_ops`."""
    change = change.checked()
    connection = await connect_db(_dsn(ops_dsn))
    try:
        version = await connection.fetchval(
            "SELECT set_platform_control($1, $2, $3, $4, $5, $6, $7, $8)",
            change.control,
            change.scope,
            change.tenant,
            change.route,
            change.active,
            change.reason.strip(),
            change.operator,
            change.request_ref,
        )
    finally:
        await connection.close()
    return cast(int, version)


async def active_controls(app_dsn: str) -> list[dict[str, object]]:
    """The active rows, as the app reads them."""
    connection = await connect_db(_dsn(app_dsn))
    try:
        rows = await connection.fetch(
            "SELECT control, scope, tenant_id, route FROM platform_control_state() "
            "ORDER BY control, scope, tenant_id, route"
        )
    finally:
        await connection.close()
    return [
        {
            "control": r["control"],
            "scope": r["scope"],
            "tenant_id": str(r["tenant_id"]) if r["tenant_id"] is not None else None,
            "route": r["route"],
        }
        for r in rows
    ]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.platform_control")
    sub = parser.add_subparsers(dest="command", required=True)
    setting = sub.add_parser("set")
    setting.add_argument("--control", required=True, choices=CONTROLS)
    setting.add_argument("--scope", required=True, choices=("platform", "firm"))
    setting.add_argument("--tenant", type=UUID, default=None)
    setting.add_argument("--route", choices=ROUTES, default=None)
    turning = setting.add_mutually_exclusive_group(required=True)
    turning.add_argument("--on", dest="active", action="store_true")
    turning.add_argument("--off", dest="active", action="store_false")
    setting.add_argument("--operator", required=True)
    setting.add_argument("--reason", required=True)
    setting.add_argument("--request-ref", default=None)
    sub.add_parser("list")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    s = settings()
    try:
        if args.command == "set":
            if s.ops_database_url is None:
                raise Refused("ops_database_url (the abacus_ops role) is not set")
            change = ControlChange(
                control=args.control,
                scope=args.scope,
                tenant=args.tenant,
                route=args.route,
                active=args.active,
                operator=args.operator,
                reason=args.reason,
                request_ref=args.request_ref,
            )
            version = asyncio.run(set_control(s.ops_database_url.get_secret_value(), change))
            state = "on" if change.active else "off"
            print(f"{change.control} ({change.scope}) {state}, version {version}")
            return 0
        if s.database_url is None:
            raise Refused("database_url is not set")
        for row in asyncio.run(active_controls(s.database_url.get_secret_value())):
            print(row)
        return 0
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
