"""The reference-set operator CLI (K-02-T06; K-02 §4.3, §4.5; ADR-300, P-62; SPEC-500 AC-35 to
AC-40).

    python -m abacus_tools.refdata draft --key us-federal-due-dates-ty2026 --kind due_date_rules \
        --title "..." --jurisdiction US --owner "..." --effective-from 2026-01-01 \
        --file rules.xlsx --drafted-by <handle> --reason "..." [--tax-year 2026] [--citations c.json]
    python -m abacus_tools.refdata diff --key <key> --file rules.xlsx
    python -m abacus_tools.refdata publish --version <uuid> --approver <handle> --reason "..."
    python -m abacus_tools.refdata withdraw --version <uuid> --operator <h> --approver <h> \
        --reason "..."

`make refdata-draft|refdata-diff|refdata-publish|refdata-withdraw ARGS="..."` runs it locally;
on staging and production it runs as the `ops-task.yml` one-off ECS task, the same command.

- **Hostile files** (ADR-052; the `methodology/workbook.py` pattern): a JSON payload as is; a CSV
  or XLSX's first sheet as rows whose header names the kind's row fields. XLSX opens read-only
  with cached values only (a formula is never evaluated; its last saved value is read, or none),
  bounded by rows and columns; every problem is `sheet, row, column, code`, never a cell's text.
  The rows then parse as the kind's payload model (`platform.reference_sets.check_draft`).
- **Diff**: row by row against the version in effect on the draft's effective date: added,
  removed and changed rows by each kind's identity fields, every changed row listed.
- **Two people**: the database refuses an approver who drafted the version (and a withdrawal by
  one person); the CLI refuses it first with the same words.
- **Never beside a hosted deploy**: with `ABACUS_DEPLOY_LOCK_ENV` set, nothing runs while that
  environment's deploy lock is held, and no database setting may point at a hosted host unless
  the run is the ops task itself (`ABACUS_OPS_TASK=1`).
- Every write goes through the owner-only definers of migration 0400; this module holds no rule's
  value (AGENTS 16).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import io
import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final, cast

from openpyxl import load_workbook

from abacus.kernel.config import settings
from abacus_tools.db_connect import connect
from abacus_tools.local import db_guard

MAX_ROWS: Final = 2_000
MAX_COLUMNS: Final = 30
MAX_BYTES: Final = 5 * 1024 * 1024
# The fields that identify a row within its kind, for the diff.
IDENTITY: Final[dict[str, tuple[str, ...]]] = {
    "due_date_rules": ("form", "fye_rule"),
    "legal_holidays": ("date", "jurisdiction"),
    "disaster_postponements": ("notice_id",),
    "form_8879_set": ("return_type", "tax_year", "jurisdiction"),
    "information_return_thresholds": ("form", "payment_year"),
    "retention_minimums": ("record_type", "service_line"),
    "standards_sets": ("code",),
}


class Refused(Exception):
    """The CLI will not run, or the input is not a valid draft; the message names why."""


@dataclass(frozen=True)
class Problem:
    sheet: str
    row: int
    column: str
    code: str

    def __str__(self) -> str:
        return f"{self.sheet}!{self.column}{self.row}: {self.code}"


def _cell(value: object) -> object:
    """A cell's value as data: strings stripped; nothing is ever evaluated."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if hasattr(value, "date") and callable(getattr(value, "date", None)):
        return value.date().isoformat()  # type: ignore[union-attr]  # datetime from openpyxl
    if isinstance(value, date):
        return value.isoformat()
    return value


def _letter(n: int) -> str:
    out = ""
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def _rows(
    sheet: str, table: Sequence[Sequence[object]]
) -> tuple[list[dict[str, object]], list[Problem]]:
    problems: list[Problem] = []
    if not table:
        return [], [Problem(sheet, 1, "A", "empty")]
    header = [str(h).strip() if h is not None else "" for h in table[0]]
    if len(header) > MAX_COLUMNS:
        problems.append(Problem(sheet, 1, _letter(MAX_COLUMNS + 1), "too_many_columns"))
    for i, name in enumerate(header, start=1):
        if not name:
            problems.append(Problem(sheet, 1, _letter(i), "header_missing"))
    if len(header) != len(set(header)):
        problems.append(Problem(sheet, 1, "A", "header_duplicate"))
    out: list[dict[str, object]] = []
    for r, line in enumerate(table[1:], start=2):
        if r > MAX_ROWS + 1:
            problems.append(Problem(sheet, r, "A", "too_many_rows"))
            break
        values = [_cell(v) for v in line]
        if all(v in (None, "") for v in values):
            continue
        row: dict[str, object] = {}
        for c, name in enumerate(header):
            value = values[c] if c < len(values) else None
            if value in (None, ""):
                continue
            if "." in name:  # a nested field, written `parent.child`
                parent, child = name.split(".", 1)
                nested = cast(dict[str, object], row.setdefault(parent, {}))
                nested[child] = value
            else:
                row[name] = value
        out.append(row)
    return out, problems


def read_table(path: Path) -> tuple[str, list[list[object]]]:
    """The first sheet of an XLSX (cached values only) or the rows of a CSV."""
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise Refused(f"{path.name}: larger than {MAX_BYTES} bytes")
    if path.suffix.lower() == ".csv":
        text = data.decode("utf-8-sig")
        return "csv", [list(r) for r in csv.reader(io.StringIO(text))]
    if path.suffix.lower() == ".xlsx":
        workbook = load_workbook(
            io.BytesIO(data), read_only=True, data_only=True, keep_links=False
        )
        try:
            sheet = workbook.worksheets[0]
            table = [
                list(r)
                for r in sheet.iter_rows(
                    max_row=MAX_ROWS + 2, max_col=MAX_COLUMNS + 1, values_only=True
                )
            ]
            return sheet.title, table
        finally:
            workbook.close()
    raise Refused(f"{path.name}: a draft is JSON, CSV or XLSX")


def payload_from(kind: str, path: Path) -> tuple[dict[str, object], list[Problem]]:
    """The kind's payload from a file: JSON as is, a table as `{kind, rows}`."""
    if path.suffix.lower() == ".json":
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            return {}, [Problem("json", 1, "A", "not_an_object")]
        return cast(dict[str, object], loaded), []
    sheet, table = read_table(path)
    rows, problems = _rows(sheet, table)
    return {"kind": kind, "rows": rows}, problems


def payload_hash(payload: Mapping[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True)
class Diff:
    added: list[dict[str, object]]
    removed: list[dict[str, object]]
    changed: list[tuple[dict[str, object], dict[str, object]]]

    @property
    def empty(self) -> bool:
        return not (self.added or self.removed or self.changed)

    def lines(self) -> list[str]:
        out = [f"+ {json.dumps(r, sort_keys=True, default=str)}" for r in self.added]
        out += [f"- {json.dumps(r, sort_keys=True, default=str)}" for r in self.removed]
        for was, now in self.changed:
            out.append(f"~ {json.dumps(was, sort_keys=True, default=str)}")
            out.append(f"  {json.dumps(now, sort_keys=True, default=str)}")
        return out


def _identity(kind: str, row: Mapping[str, object]) -> str:
    fields = IDENTITY.get(kind) or tuple(sorted(row))[:1]
    return json.dumps([row.get(f) for f in fields], default=str)


def diff(
    kind: str, current: Sequence[Mapping[str, object]], draft: Sequence[Mapping[str, object]]
) -> Diff:
    """Every changed row, by the kind's identity fields (AC: the diff lists every changed row)."""
    before = {_identity(kind, r): dict(r) for r in current}
    after = {_identity(kind, r): dict(r) for r in draft}
    added = [after[k] for k in sorted(after.keys() - before.keys())]
    removed = [before[k] for k in sorted(before.keys() - after.keys())]
    changed = [
        (before[k], after[k])
        for k in sorted(before.keys() & after.keys())
        if payload_hash(before[k]) != payload_hash(after[k])
    ]
    return Diff(added, removed, changed)


def guard() -> None:
    """Never beside a hosted deploy, never a hosted database from a laptop."""
    holder = db_guard.lock_holder()
    if holder is not None:
        raise Refused(f"deploy lock {holder}: wait for the deploy to finish")
    if os.environ.get("ABACUS_OPS_TASK") != "1":
        found = db_guard.violations()
        if found:
            raise Refused(
                f"{', '.join(found)} points at a hosted database (run it as the ops task)"
            )


def _owner_dsn() -> str:
    url = settings().migrations_database_url
    if url is None:
        raise Refused("migrations_database_url is not set (the owner role runs reference data)")
    return url.get_secret_value()


async def _current_rows(key: str, as_of: date) -> list[dict[str, object]]:
    conn = await connect(_owner_dsn())
    try:
        row = await conn.fetchrow("SELECT payload FROM reference_set_resolve($1, $2)", key, as_of)
    finally:
        await conn.close()
    if row is None:
        return []
    payload = row["payload"]
    loaded = json.loads(payload) if isinstance(payload, str) else payload
    return cast(list[dict[str, object]], loaded.get("rows", []))


async def draft(args: argparse.Namespace) -> str:
    from abacus.modules.platform.api import check_draft

    payload, problems = payload_from(args.kind, Path(args.file))
    if problems:
        raise Refused("\n".join(str(p) for p in problems))
    checked = await check_draft(args.kind, payload)
    stored = cast(dict[str, object], checked.model_dump(mode="json"))
    citations = json.loads(Path(args.citations).read_text()) if args.citations else []
    conn = await connect(_owner_dsn())
    try:
        version_id = await conn.fetchval(
            "SELECT reference_set_draft($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10, "
            "$11::jsonb, $12, $13)",
            args.key,
            args.kind,
            args.title,
            args.jurisdiction,
            args.owner,
            args.description or "",
            args.tax_year,
            date.fromisoformat(args.effective_from),
            json.dumps(stored),
            payload_hash(stored),
            json.dumps(citations),
            args.drafted_by,
            args.reason,
        )
    finally:
        await conn.close()
    return f"drafted {version_id}"


async def show_diff(args: argparse.Namespace) -> str:
    payload, problems = payload_from(args.kind, Path(args.file))
    if problems:
        raise Refused("\n".join(str(p) for p in problems))
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    current = await _current_rows(args.key, as_of)
    found = diff(args.kind, current, cast(list[dict[str, object]], payload.get("rows", [])))
    return "no change" if found.empty else "\n".join(found.lines())


async def _versions_drafter(conn: object, version_id: str) -> str | None:
    return await conn.fetchval(  # type: ignore[attr-defined]  # an asyncpg connection
        "SELECT drafted_by FROM reference_set_versions WHERE id = $1", version_id
    )


async def publish(args: argparse.Namespace) -> str:
    conn = await connect(_owner_dsn())
    try:
        if await _versions_drafter(conn, args.version) == args.approver:
            raise Refused("approver_is_drafter: a second person publishes")
        await conn.execute(
            "SELECT reference_set_publish($1, $2, $3)", args.version, args.approver, args.reason
        )
    finally:
        await conn.close()
    return f"published {args.version}"


async def withdraw(args: argparse.Namespace) -> str:
    if args.operator == args.approver:
        raise Refused("approver_is_operator: two people withdraw a version")
    conn = await connect(_owner_dsn())
    try:
        await conn.execute(
            "SELECT reference_set_withdraw($1, $2, $3, $4)",
            args.version,
            args.operator,
            args.approver,
            args.reason,
        )
    finally:
        await conn.close()
    return f"withdrew {args.version}"


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="abacus_tools.refdata", description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    d = sub.add_parser("draft")
    for name in ("--key", "--kind", "--title", "--jurisdiction", "--owner", "--effective-from"):
        d.add_argument(name, required=True)
    d.add_argument("--file", required=True)
    d.add_argument("--drafted-by", required=True)
    d.add_argument("--reason", required=True)
    d.add_argument("--description", default="")
    d.add_argument("--tax-year", type=int, default=None)
    d.add_argument("--citations", default=None)
    f = sub.add_parser("diff")
    f.add_argument("--key", required=True)
    f.add_argument("--kind", required=True)
    f.add_argument("--file", required=True)
    f.add_argument("--as-of", default=None)
    p = sub.add_parser("publish")
    p.add_argument("--version", required=True)
    p.add_argument("--approver", required=True)
    p.add_argument("--reason", required=True)
    w = sub.add_parser("withdraw")
    w.add_argument("--version", required=True)
    w.add_argument("--operator", required=True)
    w.add_argument("--approver", required=True)
    w.add_argument("--reason", required=True)
    return root


def main(argv: Sequence[str]) -> int:
    args = parser().parse_args(list(argv))
    commands = {"draft": draft, "diff": show_diff, "publish": publish, "withdraw": withdraw}
    try:
        guard()
        print(asyncio.run(commands[args.command](args)))
    except Refused as exc:
        print(f"refdata refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
