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
