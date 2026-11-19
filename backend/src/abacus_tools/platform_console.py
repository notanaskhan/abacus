"""The console's global writes, as the operator (G-04-T10; SPEC-680 AC-52, AC-55, AC-57;
DEC-5417).

Status incidents (post, update, resolve) and help articles (draft, publish, withdraw) are global
rows behind owner functions that 0947 grants to `abacus_ops` only (ADR-156: the EXECUTE-only role
the API and worker never hold). The functions enforce the rules (two-person publish:
`approver_is_drafter`; an incident note is at most 280 characters and names no firm or client);
this command refuses bad input before it connects.

    python -m abacus_tools.platform_console incident-post --component quickbooks_online_sync \
        --severity degraded --title "QuickBooks Online sync delayed" --note "…" --operator rowan
    python -m abacus_tools.platform_console article-publish --id <uuid> --operator jordan \
        --reason "Reviewed against SHL-05 copy"

G-04-T20 (DEC-5702): `content-import --dir <folder>` loads a reviewed content folder kept outside
the repository (no content row is committed): `status_components.json` and `regions.json` (lists of
rows), `support_hours.json` (`{"value": {...}, "expected_version": n}`) and `articles/*.json` (one
help article each, drafted for a second platform admin to publish). `--dry-run` checks the folder
and prints what it would write without connecting. Email templates for new notification kinds go
through `POST /v1/platform/email-templates/import` (R-01's import), not this command.

    python -m abacus_tools.platform_console content-import --dir ~/content/2026-10 \
        --operator rowan --reason "Production content v1, reviewed Oct 2"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Final, cast
from uuid import UUID

from abacus.kernel.config import settings
from abacus.modules.platform.api import OPERATOR_HANDLE
from abacus_tools.db_connect import connect as connect_db

SEVERITIES: Final = ("degraded", "outage", "maintenance")
NOTE_MAX: Final = 280
_COMPONENT: Final = re.compile(r"[a-z0-9_]{3,80}")
_SLUG: Final = re.compile(r"[a-z0-9-]{3,120}")


class Refused(ValueError):
    pass


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


def check_note(note: str) -> str:
    """AC-55: at most 280 characters, never empty."""
    cleaned = note.strip()
    if not 1 <= len(cleaned) <= NOTE_MAX:
        raise Refused(f"--note is 1 to {NOTE_MAX} characters")
    return cleaned


def check_operator(operator: str) -> str:
    if not OPERATOR_HANDLE.fullmatch(operator):
        raise Refused("--operator is a lower-case handle, never an email address")
    return operator


async def _call(ops_dsn: str, sql: str, *args: object) -> object:
    connection = await connect_db(_dsn(ops_dsn))
    try:
        return await connection.fetchval(sql, *args)
    finally:
        await connection.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.platform_console")
    sub = parser.add_subparsers(dest="command", required=True)
    post = sub.add_parser("incident-post")
    post.add_argument("--component", required=True)
    post.add_argument("--severity", required=True, choices=SEVERITIES)
    post.add_argument("--title", required=True)
    post.add_argument("--note", required=True)
    post.add_argument("--operator", required=True)
    for name in ("incident-update", "incident-resolve"):
        change = sub.add_parser(name)
        change.add_argument("--id", required=True, type=UUID)
        change.add_argument("--note", required=True)
        change.add_argument("--operator", required=True)
    draft = sub.add_parser("article-draft")
    draft.add_argument("--file", required=True, type=Path, help="a JSON article (schema v1)")
    draft.add_argument("--operator", required=True)
    draft.add_argument("--reason", required=True)
    content = sub.add_parser("content-import")
    content.add_argument("--dir", required=True, type=Path, help="the reviewed content folder")
    content.add_argument("--operator", required=True)
    content.add_argument("--reason", required=True)
    content.add_argument("--dry-run", action="store_true")
    for name in ("article-publish", "article-withdraw"):
        decide = sub.add_parser(name)
        decide.add_argument("--id", required=True, type=UUID)
        decide.add_argument("--operator", required=True)
        decide.add_argument("--reason", required=True)
    return parser


def _article(path: Path) -> dict[str, object]:
    found = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
    slug = str(found.get("slug", ""))
    if not _SLUG.fullmatch(slug):
        raise Refused("the article's slug is 3 to 120 of a-z, 0-9 and -")
    if not isinstance(found.get("body"), list):
        raise Refused("the article's body is a list of schema v1 blocks")
    return found


_KINDS: Final = ("core", "integration")
_REGIONS: Final = ("us", "eu", "uk")


def _rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    found = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(found, list):
        raise Refused(f"{path.name} is a list of rows")
    return cast("list[dict[str, object]]", found)


def content_plan(folder: Path) -> list[tuple[str, tuple[object, ...]]]:
    """The writes a content folder asks for, checked before anything connects: (SQL, args)."""
    if not folder.is_dir():
        raise Refused("--dir is a content folder")
    plan: list[tuple[str, tuple[object, ...]]] = []
    for i, row in enumerate(_rows(folder / "status_components.json")):
        key, kind = str(row.get("key", "")), str(row.get("kind", ""))
        integration = row.get("integration_key")
        if not _COMPONENT.fullmatch(key) or kind not in _KINDS:
            raise Refused(f"status component {i}: key a-z0-9_ and kind core or integration")
        if (kind == "integration") != (integration is not None):
            raise Refused(f"status component {key}: an integration row names its integration")
        plan.append((
            "SELECT status_component_upsert($1, $2, $3, $4, $5::smallint, $6, $7, $8)",
            (key, str(row.get("label", "")), kind, integration,
             int(cast(int, row.get("display_order", 100))), bool(row.get("active", True))),
        ))  # fmt: skip
    for row in _rows(folder / "regions.json"):
        code = str(row.get("code", ""))
        if code not in _REGIONS or row.get("status") not in ("live", "planned"):
            raise Refused(f"region {code!r}: code us, eu or uk and status live or planned")
        plan.append((
            "SELECT platform_region_upsert($1, $2, $3, $4, $5, $6, $7, $8, $9)",
            (code, str(row.get("label", "")), row["status"], row.get("planned_label"),
             row.get("storage_label"), row.get("backup_label"), row.get("inference_label")),
        ))  # fmt: skip
    hours = folder / "support_hours.json"
    if hours.exists():
        found = cast("dict[str, object]", json.loads(hours.read_text(encoding="utf-8")))
        if not isinstance(found.get("value"), dict):
            raise Refused("support_hours.json holds a value object and expected_version")
        plan.append((
            "SELECT platform_setting_put($1, $2::jsonb, $3, $4, $5)",
            ("support_hours", json.dumps(found["value"]),
             int(cast(int, found.get("expected_version", 0)))),
        ))  # fmt: skip
    for path in sorted((folder / "articles").glob("*.json")):
        a = _article(path)
        plan.append((
            "SELECT help_article_draft($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9)",
            (a["slug"], a.get("title"), a.get("summary"), a.get("group_key"),
             a.get("context_screen_ids") or [], a.get("read_minutes"), json.dumps(a["body"])),
        ))  # fmt: skip
    if not plan:
        raise Refused("the folder holds no content files")
    return plan


async def _import(ops_dsn: str, plan: list[tuple[str, tuple[object, ...]]], operator: str,
                  reason: str) -> int:  # fmt: skip
    """Every write in one transaction: the folder loads whole or not at all."""
    connection = await connect_db(_dsn(ops_dsn))
    try:
        async with connection.transaction():
            for sql, args in plan:
                await connection.fetchval(sql, *args, operator, reason)
    finally:
        await connection.close()
    return len(plan)


async def run(ops_dsn: str, args: argparse.Namespace) -> object:
    operator = check_operator(args.operator)
    if args.command == "incident-post":
        if not _COMPONENT.fullmatch(args.component):
            raise Refused("--component is a status component key")
        return await _call(
            ops_dsn,
            "SELECT status_incident_post($1, $2, $3, $4, $5)",
            args.component, args.severity, args.title.strip()[:160], check_note(args.note),
            operator,
        )  # fmt: skip
    if args.command in ("incident-update", "incident-resolve"):
        fn = (
            "status_incident_update"
            if args.command == "incident-update"
            else ("status_incident_resolve")
        )
        return await _call(
            ops_dsn, f"SELECT {fn}($1, $2, $3)", args.id, check_note(args.note), operator
        )
    reason = str(args.reason).strip()
    if not 10 <= len(reason) <= 500:
        raise Refused("--reason is 10 to 500 characters")
    if args.command == "content-import":
        plan = content_plan(args.dir)
        if args.dry_run:
            return f"{len(plan)} writes (dry run)"
        return await _import(ops_dsn, plan, operator, reason)
    if args.command == "article-draft":
        a = _article(args.file)
        return await _call(
            ops_dsn,
            "SELECT help_article_draft($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9)",
            a["slug"], a.get("title"), a.get("summary"), a.get("group_key"),
            a.get("context_screen_ids") or [], a.get("read_minutes"), json.dumps(a["body"]),
            operator, reason,
        )  # fmt: skip
    fn = "help_article_publish" if args.command == "article-publish" else "help_article_withdraw"
    return await _call(ops_dsn, f"SELECT {fn}($1, $2, $3)", args.id, operator, reason)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    s = settings()
    try:
        if getattr(args, "dry_run", False):
            result = asyncio.run(run("", args))
        else:
            if s.ops_database_url is None:
                raise Refused("ops_database_url (the abacus_ops role) is not set")
            result = asyncio.run(run(s.ops_database_url.get_secret_value(), args))
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(f"{args.command}: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
