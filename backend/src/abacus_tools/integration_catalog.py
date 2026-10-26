"""The integration catalogue load, the operator's command (A-02-T12; C20 v1; P-62).
Run as an ECS one-off `abacus-ops` task, never from a laptop against a hosted database.

    python -m abacus_tools.integration_catalog load --document <reviewed.yaml> --dry-run \
        --operator <handle>
    python -m abacus_tools.integration_catalog load --document <reviewed.yaml> --operator <handle>

The document is reviewed content (`version: 1`, `rows: [...]`; `integrations.api.
CatalogDocument`), never a seed or a constant (AGENTS 16). Both forms validate it and print the
plan (each added key; each changed key with the columns that differ). `--dry-run` stops there and
writes nothing. A load writes through `integration_catalog_load(rows, operator)` as `abacus_ops`
(EXECUTE only) and prints what the database changed, which must equal the plan.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml
from pydantic import ValidationError

from abacus.kernel.config import settings
from abacus.modules.integrations.api import CatalogDocument, LoadPlan, plan_load
from abacus.modules.platform.api import OPERATOR_HANDLE
from abacus_tools.db_connect import connect as connect_db


class Refused(Exception):
    """The command was refused before or by the database; nothing was written."""


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


def read_document(path: Path) -> CatalogDocument:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return CatalogDocument.model_validate(raw)
    except (OSError, yaml.YAMLError) as exc:
        raise Refused(f"the document can't be read: {type(exc).__name__}") from exc
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()})
        raise Refused(f"the document does not validate: {', '.join(fields)}") from exc


async def current_rows(dsn: str) -> list[Mapping[str, object]]:
    """The catalogue as `integration_catalog_rows()` returns it (JSON columns decoded)."""
    connection = await connect_db(_dsn(dsn))
    try:
        rows = await connection.fetch("SELECT * FROM integration_catalog_rows()")
    finally:
        await connection.close()
    out: list[Mapping[str, object]] = []
    for r in rows:
        row = dict(r)
        for column in ("consent_copy", "scopes"):
            if isinstance(row[column], str):
                row[column] = json.loads(cast(str, row[column]))
        row["surfaces"] = list(cast(list[str], row["surfaces"]))
        out.append(row)
    return out


@dataclass(frozen=True)
class LoadResult:
    plan: LoadPlan
    written: tuple[tuple[str, str], ...]  # key, added | changed (empty on a dry run)


async def load(
    ops_dsn: str, document: CatalogDocument, operator: str, *, dry_run: bool
) -> LoadResult:
    """Plan the document against the catalogue; write it unless `dry_run`."""
    if not OPERATOR_HANDLE.fullmatch(operator):
        raise Refused("--operator is a lower-case handle, never an email address")
    plan = plan_load(await current_rows(ops_dsn), document)
    if dry_run or not plan.writes:
        return LoadResult(plan, ())
    connection = await connect_db(_dsn(ops_dsn))
    try:
        rows = await connection.fetch(
            "SELECT key, change FROM integration_catalog_load($1::jsonb, $2)",
            json.dumps([r.as_row() for r in document.rows]),
            operator,
        )
    finally:
        await connection.close()
    return LoadResult(plan, tuple((str(r["key"]), str(r["change"])) for r in rows))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.integration_catalog")
    sub = parser.add_subparsers(dest="command", required=True)
    loading = sub.add_parser("load")
    loading.add_argument("--document", required=True, type=Path)
    loading.add_argument("--operator", required=True)
    loading.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    s = settings()
    try:
        if s.ops_database_url is None:
            raise Refused("ops_database_url (the abacus_ops role) is not set")
        document = read_document(args.document)
        result = asyncio.run(
            load(
                s.ops_database_url.get_secret_value(),
                document,
                args.operator,
                dry_run=args.dry_run,
            )
        )
        for key in result.plan.added:
            print(f"add {key}")
        for key, columns in result.plan.changed:
            print(f"change {key}: {', '.join(columns)}")
        print(
            f"{len(result.plan.added)} to add, {len(result.plan.changed)} to change, "
            f"{len(result.plan.unchanged)} unchanged"
            + (" (dry run: nothing written)" if args.dry_run else "")
        )
        return 0
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
