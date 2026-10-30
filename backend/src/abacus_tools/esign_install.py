"""Operator commands for a firm's DocuSeal install (N-02-T18 install path; ADR-342; TASK-2152;
DEC-1279). Run as an ECS one-off `abacus-ops` task (an ops request), never from a laptop against a
hosted database.

    python -m abacus_tools.esign_install connect --tenant <id> --requested-by <member user id> \
        --operator <handle>
    python -m abacus_tools.esign_install rotate --tenant <id> --operator <handle>
    python -m abacus_tools.esign_install disconnect --tenant <id> --operator <handle>
    python -m abacus_tools.esign_install status --tenant <id> --operator <handle>

The API key is read only from `ABACUS_ESIGN_INSTALL_API_KEY`, which the environment maps from
its secret store into the ops task alone: never an argument (an ops request is a file in a public
repository), never printed, never logged. `connect` and `rotate` first ask DocuSeal whether the
key works (`GET /user`; a refusal writes nothing), then make sure the catalogue holds the hidden
`docuseal` row (this package's reviewed `catalogue/esignature.yaml`, through the catalogue's
operator load as `abacus_ops`), then write through `integrations.api` in the operator's context:
the install and its sealed secret, one unit of work. Nothing here opens W7: an install with W7
closed still sends nothing (`esign_install_secret`).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Final
from uuid import UUID

import httpx
from sqlalchemy.exc import IntegrityError

from abacus.kernel.config import settings
from abacus.kernel.db.session import configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.modules.integrations.api import (
    EsignInstallExists,
    connect_esign_install,
    disconnect_esign_install,
    esign_install_state,
    rotate_esign_secret,
)
from abacus.modules.platform.api import operator_context
from abacus_tools import integration_catalog

KEY_ENV: Final = "ABACUS_ESIGN_INSTALL_API_KEY"
API_HOST: Final = "api.docuseal.com"  # signatures.docuseal.ALLOWED_HOSTS
DOCUMENT: Final = Path(__file__).parent / "catalogue" / "esignature.yaml"
_KEY = re.compile(r"[A-Za-z0-9_-]{20,200}")
_TIMEOUT: Final = httpx.Timeout(20.0, connect=10.0)


class Refused(Exception):
    """The command was refused before or by the database or DocuSeal; nothing was written."""


def api_key(environ: dict[str, str] | None = None) -> str:
    """The key from the ops task's environment, checked for shape only (never echoed)."""
    raw = (environ if environ is not None else dict(os.environ)).get(KEY_ENV, "").strip()
    if not raw:
        raise Refused(f"{KEY_ENV} is not set in this task's environment")
    if not _KEY.fullmatch(raw):
        raise Refused(f"{KEY_ENV} does not look like a DocuSeal API key")
    return raw


def secret_of(key: str) -> bytes:
    """What the install seals: the account JSON `DocuSealAccount.from_secret` opens."""
    return json.dumps({"api_key": key, "api_host": API_HOST}).encode()


async def check_key(key: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
    """DocuSeal accepts the key (`GET /user`), or `Refused`; the response body is not read."""
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, follow_redirects=False, transport=transport
    ) as http:
        try:
            got = await http.get(f"https://{API_HOST}/user", headers={"X-Auth-Token": key})
        except httpx.HTTPError as exc:
            raise Refused("DocuSeal could not be reached") from exc
    if got.status_code in (401, 403):
        raise Refused("DocuSeal refused the key")
    if got.status_code != 200:
        raise Refused(f"DocuSeal answered {got.status_code}")


async def ensure_catalogue_row(ops_dsn: str, operator: str) -> str:
    """The hidden `docuseal` row, loaded from the reviewed document (added, changed or kept)."""
    try:
        document = integration_catalog.read_document(DOCUMENT)
        result = await integration_catalog.load(ops_dsn, document, operator, dry_run=False)
    except integration_catalog.Refused as exc:
        raise Refused(str(exc)) from exc
    if not result.matches_plan:
        raise Refused("the catalogue's changes differ from the plan")
    return "added" if result.plan.added else "changed" if result.plan.changed else "unchanged"


async def run(
    command: str,
    *,
    tenant_id: UUID,
    operator: str,
    requested_by: UUID | None,
    app_dsn: str,
    ops_dsn: str | None,
    environ: dict[str, str] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, str]:
    try:
        tenant = operator_context(tenant_id, operator)
    except ValueError as exc:
        raise Refused("--operator is a lower-case handle, never an email address") from exc
    out: dict[str, str] = {"tenant": str(tenant_id)}
    key: str | None = None
    if command in ("connect", "rotate"):
        if command == "connect" and requested_by is None:
            raise Refused("connect needs --requested-by, a member of the firm")
        if ops_dsn is None:
            raise Refused("ops_database_url (the abacus_ops role) is not set")
        key = api_key(environ)
        await check_key(key, transport)
        out["catalogue"] = await ensure_catalogue_row(ops_dsn, operator)
    configure_engine(app_dsn)
    try:
        if command == "connect" and key is not None and requested_by is not None:
            try:
                install = await connect_esign_install(tenant, requested_by, secret_of(key))
            except EsignInstallExists as exc:
                raise Refused(
                    "the firm has a live DocuSeal install: rotate or disconnect"
                ) from exc
            except IntegrityError as exc:  # created_by is not a member, or no such firm
                raise Refused("--requested-by is not a member of this firm") from exc
            out["install"] = str(install)
        elif command == "rotate" and key is not None:
            try:
                out["install"] = str(await rotate_esign_secret(tenant, secret_of(key)))
            except NotFound as exc:
                raise Refused("the firm has no live DocuSeal install") from exc
        elif command == "disconnect":
            try:
                out["install"] = str(await disconnect_esign_install(tenant))
            except NotFound as exc:
                raise Refused("the firm has no live DocuSeal install") from exc
        out["state"] = await esign_install_state(tenant)
    finally:
        await dispose_engine()
    return out


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.esign_install")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("connect", "rotate", "disconnect", "status"):
        command = sub.add_parser(name)
        command.add_argument("--tenant", required=True, type=UUID)
        command.add_argument("--operator", required=True)
        if name == "connect":
            command.add_argument("--requested-by", required=True, type=UUID)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    s = settings()
    try:
        if s.database_url is None:
            raise Refused("database_url (the app role) is not set")
        out = asyncio.run(
            run(
                args.command,
                tenant_id=args.tenant,
                operator=args.operator,
                requested_by=getattr(args, "requested_by", None),
                app_dsn=s.database_url.get_secret_value(),
                ops_dsn=s.ops_database_url.get_secret_value() if s.ops_database_url else None,
            )
        )
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
