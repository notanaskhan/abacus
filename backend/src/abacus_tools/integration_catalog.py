"""The integration catalogue load (A-02-T12; C20 v1; P-62): a local and dev command for now.

Not an allowlisted operator command (security review M3, DEC-438): a hosted load needs the
reviewed document to reach the ops task through the ops-request PR with its digest checked, and
the operator taken from the validated request rather than `--operator`. That path is follow-up
work for the catalogue-content task; until then this runs only against a local database.

    python -m abacus_tools.integration_catalog load --document <reviewed.yaml> --dry-run \
        --operator <handle>
    python -m abacus_tools.integration_catalog load --document <reviewed.yaml> --operator <handle>
    python -m abacus_tools.integration_catalog import --document <reviewed-v2.yaml> --dry-run \
        --operator <handle> --note "<why>"
    python -m abacus_tools.integration_catalog import --document <reviewed-v2.yaml> \
        --operator <handle> --note "<why>"

The document is reviewed content (`version: 1`, `rows: [...]`; `integrations.api.
CatalogDocument`), never a seed or a constant (AGENTS 16). Both forms validate it and print the
plan (each added key; each changed key with the columns that differ). `--dry-run` stops there and
writes nothing. A load writes through `integration_catalog_load(rows, operator)` as `abacus_ops`
(EXECUTE only) and checks that what the database changed equals the plan: a mismatch exits 3.

`import` (W-01-T07; SPEC-659 AC-32, AC-33) is C20 v2's: the `version: 2` document (the WB-10
tiles and the portal's client feeds; `integrations.api.CatalogDocumentV2`), planned against
every row (adds, changes, and the workbench rows it no longer names, which are unpublished). A
dry run prints the plan and writes nothing. An apply writes through
`integration_catalog_import(...)` (0901), which logs one `integration_catalog_imports` row with
the document's SHA-256 and the note, checks the database's changes equal the plan (exit 3), then
tells each person who asked about a key that became available, firm by firm (`notify_available`).
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
from abacus.modules.identity.api import firm_tenant_ids
from abacus.modules.integrations.api import (
    CatalogDocument,
    CatalogDocumentV2,
    ImportPlan,
    LoadPlan,
    document_sha256,
    notify_available,
    plan_import,
    plan_load,
)
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
    dry_run: bool = False

    @property
    def matches_plan(self) -> bool:
        """What the database changed is exactly the plan (always true for a dry run)."""
        if self.dry_run:
            return True
        planned = {(k, "added") for k in self.plan.added}
        planned |= {(k, "changed") for k, _ in self.plan.changed}
        return set(self.written) == planned and len(self.written) == len(planned)


async def load(
    ops_dsn: str, document: CatalogDocument, operator: str, *, dry_run: bool
) -> LoadResult:
    """Plan the document against the catalogue; write it unless `dry_run`."""
    if not OPERATOR_HANDLE.fullmatch(operator):
        raise Refused("--operator is a lower-case handle, never an email address")
    plan = plan_load(await current_rows(ops_dsn), document)
    if dry_run or not plan.writes:
        return LoadResult(plan, (), dry_run=dry_run)
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


def read_document_v2(path: Path) -> tuple[CatalogDocumentV2, str]:
    """The v2 document and its SHA-256 (of the bytes as reviewed)."""
    try:
        raw = path.read_bytes()
        return CatalogDocumentV2.model_validate(yaml.safe_load(raw)), document_sha256(raw)
    except (OSError, yaml.YAMLError) as exc:
        raise Refused(f"the document can't be read: {type(exc).__name__}") from exc
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()})
        raise Refused(f"the document does not validate: {', '.join(fields)}") from exc


_V2_DEFAULTS: dict[str, object] = {
    "categories": [],
    "description": None,
    "auth_line": None,
    "published_at": None,
    "prerequisite": None,
}


async def current_rows_v2(dsn: str) -> list[Mapping[str, object]]:
    """Every catalogue row with its v2 columns: the v1 reader's rows, the workbench reader's
    columns over them (a portal-only row has none of its own)."""
    rows = {str(r["key"]): {**_V2_DEFAULTS, **r} for r in await current_rows(dsn)}
    connection = await connect_db(_dsn(dsn))
    try:
        bench = await connection.fetch("SELECT * FROM integration_catalog_workbench()")
    finally:
        await connection.close()
    for b in bench:
        row = rows.setdefault(str(b["key"]), {})
        for column in ("categories", "description", "auth_line", "published_at"):
            row[column] = b[column]
        row["categories"] = list(cast(list[str], b["categories"] or []))
        pre = b["prerequisite"]
        row["prerequisite"] = json.loads(pre) if isinstance(pre, str) else pre
        # 0933's detail copy (C-02-T40's write consent lives in it): without it every re-import
        # planned a change the database, rightly, never wrote (S53 main CI).
        detail = b["detail_copy"]
        row["detail_copy"] = json.loads(detail) if isinstance(detail, str) else detail
    return list(rows.values())


@dataclass(frozen=True)
class ImportResult:
    plan: ImportPlan
    written: tuple[tuple[str, str], ...]  # key, added | changed | unpublished
    import_id: str | None
    told: int = 0

    @property
    def matches_plan(self) -> bool:
        planned = {(k, "added") for k in self.plan.added}
        planned |= {(k, "changed") for k, _ in self.plan.changed}
        planned |= {(k, "unpublished") for k in self.plan.unpublished}
        return set(self.written) == planned and len(self.written) == len(planned)


async def import_v2(
    ops_dsn: str,
    document: CatalogDocumentV2,
    sha256: str,
    operator: str,
    note: str,
    *,
    environment: str,
    dry_run: bool,
) -> ImportResult:
    """Plan the v2 document; apply it unless `dry_run`; tell who asked about what became
    available."""
    if not OPERATOR_HANDLE.fullmatch(operator):
        raise Refused("--operator is a lower-case handle, never an email address")
    if not 1 <= len(note.strip()) <= 500:
        raise Refused("--note says why, in at most 500 characters")
    plan = plan_import(await current_rows_v2(ops_dsn), document)
    if dry_run or not plan.writes:
        return ImportResult(plan, (), None)
    connection = await connect_db(_dsn(ops_dsn))
    try:
        rows = await connection.fetch(
            "SELECT import_id, key, change FROM integration_catalog_import($1::jsonb, $2, $3, "
            "$4, $5)",
            json.dumps([r.as_row() for r in document.rows]),
            operator,
            environment,
            sha256,
            note.strip(),
        )
    finally:
        await connection.close()
    written = tuple((str(r["key"]), str(r["change"])) for r in rows)
    result = ImportResult(plan, written, str(rows[0]["import_id"]) if rows else None)
    if not result.matches_plan:
        return result
    told = 0
    if plan.became_available:
        for tenant_id in await firm_tenant_ids():
            told += await notify_available(tenant_id, plan.became_available)
    return ImportResult(plan, written, result.import_id, told)


def _print_import(result: ImportResult, *, dry_run: bool) -> None:
    for key in result.plan.added:
        print(f"add {key}")
    for key, columns in result.plan.changed:
        print(f"change {key}: {', '.join(columns)}")
    for key in result.plan.unpublished:
        print(f"unpublish {key}")
    print(
        f"{len(result.plan.added)} to add, {len(result.plan.changed)} to change, "
        f"{len(result.plan.unpublished)} to unpublish, {len(result.plan.unchanged)} unchanged"
        + (" (dry run: nothing written)" if dry_run else f"; {result.told} told it is available")
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.integration_catalog")
    sub = parser.add_subparsers(dest="command", required=True)
    loading = sub.add_parser("load")
    loading.add_argument("--document", required=True, type=Path)
    loading.add_argument("--operator", required=True)
    loading.add_argument("--dry-run", action="store_true")
    importing = sub.add_parser("import")
    importing.add_argument("--document", required=True, type=Path)
    importing.add_argument("--operator", required=True)
    importing.add_argument("--note", required=True)
    importing.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    s = settings()
    try:
        if s.ops_database_url is None:
            raise Refused("ops_database_url (the abacus_ops role) is not set")
        if args.command == "import":
            v2, sha = read_document_v2(args.document)
            imported = asyncio.run(
                import_v2(
                    s.ops_database_url.get_secret_value(),
                    v2,
                    sha,
                    args.operator,
                    args.note,
                    environment=s.environment,
                    dry_run=args.dry_run,
                )
            )
            _print_import(imported, dry_run=args.dry_run)
            if not args.dry_run and not imported.matches_plan:
                print("mismatch: the database's changes differ from the plan", file=sys.stderr)
                return 3
            return 0
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
        if not result.matches_plan:
            print(
                "mismatch: the database's changes differ from the plan: "
                + ", ".join(f"{k} {c}" for k, c in result.written),
                file=sys.stderr,
            )
            return 3
        return 0
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
