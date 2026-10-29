"""The expand-only migration guard (Q-03-T081; DEC-06, ADR P-38 end, ADR-091 strict; DEC-1052).

From Tue Jun 1, 2027 (real data), a migration may only expand the schema. This is the one
implementation of the rule; stage 1 and Q-04-T003's release gate both call it.

    python -m abacus_tools.quality.expand_only check --base origin/main [--label contract-step]
        [--today 2027-06-02]
    python -m abacus_tools.quality.expand_only window --base origin/main
        --at 2027-09-01T20:00-05:00 [--label contract-step]

A contract operation, in a new migration's `upgrade()`:

- **drop**: `DROP TABLE`, `DROP COLUMN`, `DROP TYPE`, `DROP SCHEMA`, `DROP VIEW`, `DROP
  MATERIALIZED VIEW`, `TRUNCATE`, and `op.drop_table`, `op.drop_column`;
- **rename**: `RENAME TO`, `RENAME COLUMN`, `op.rename_table`, `op.alter_column(new_column_name=)`;
- **type change**: `ALTER COLUMN ... TYPE` and `op.alter_column(type_=)` (narrowing can't be told
  from text, so every type change is a contract step: the label says a person checked it);
- **not null**: `SET NOT NULL`, `ADD COLUMN ... NOT NULL` without `DEFAULT`, `op.alter_column(
  nullable=False)`, `op.add_column` of a `nullable=False` column without `server_default`;
- **value removal**: a CHECK `IN (...)` list re-added with fewer values than the one the same
  migration's `downgrade()` restores (this repo's enums are CHECK lists).

Before Jun 1, 2027 (`ACTIVE_FROM`) the check reports and passes (ADR-135's pre-launch policy).
From then a contract operation fails unless the PR is labelled `contract-step` (the solo edition
needs no second approval: AMENDMENT-solo item 2). **Window mode** refuses every contract operation
while any live firm is in a release window (`deploy/windows.yaml`, Q-04-T002), labelled or not.
"""

from __future__ import annotations

import argparse
import ast
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final, Literal

from abacus_tools import release_windows

BACKEND: Final = Path(__file__).resolve().parents[3]
REPO: Final = BACKEND.parent
VERSIONS: Final = BACKEND / "migrations" / "versions"
ACTIVE_FROM: Final = date(2027, 6, 1)
LABEL: Final = "contract-step"
GIT: Final = shutil.which("git") or "/usr/bin/git"

Kind = Literal["drop", "rename", "type_change", "not_null", "value_removal"]

_SQL_RULES: Final[tuple[tuple[Kind, re.Pattern[str]], ...]] = (
    (
        "drop",
        re.compile(
            r"\bDROP\s+(TABLE|COLUMN|TYPE|SCHEMA|MATERIALIZED\s+VIEW|VIEW)\b"
            r"|\bTRUNCATE\s+(?!ON\b)(TABLE\s+)?\w+",
            re.IGNORECASE,
        ),
    ),
    ("rename", re.compile(r"\bRENAME\s+(TO|COLUMN)\b", re.IGNORECASE)),
    ("type_change", re.compile(r"\bALTER\s+COLUMN\s+\w+\s+(SET\s+DATA\s+)?TYPE\b", re.IGNORECASE)),
    ("not_null", re.compile(r"\bSET\s+NOT\s+NULL\b", re.IGNORECASE)),
)
# `ADD COLUMN x type NOT NULL` without a DEFAULT before the next comma or the statement's end.
_ADD_NOT_NULL: Final = re.compile(
    r"\bADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?\w+\s+(?P<rest>[^,;]*?\bNOT\s+NULL\b[^,;]*)",
    re.IGNORECASE,
)
_CHECK_IN: Final = re.compile(
    r"ADD\s+CONSTRAINT\s+(?P<name>\w+)\s+CHECK\s*\(\s*\w+\s+IN\s*\((?P<values>[^)]*)\)",
    re.IGNORECASE,
)
_OP_DROPS: Final = frozenset({"drop_table", "drop_column"})


@dataclass(frozen=True)
class Operation:
    path: str
    line: int
    kind: Kind
    text: str


# --- Detection ---------------------------------------------------------------------------------


def _function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    return next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name), None)


def _strings(node: ast.AST) -> Iterator[tuple[int, str]]:
    """Every string a function builds: constants, and f-strings' literal parts joined."""
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            yield n.lineno, n.value
        elif isinstance(n, ast.JoinedStr):
            parts = [v.value for v in n.values if isinstance(v, ast.Constant)]
            yield n.lineno, "".join(str(p) for p in parts)


def _kw(call: ast.Call, name: str) -> ast.expr | None:
    return next((k.value for k in call.keywords if k.arg == name), None)


def _false(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def _op_calls(fn: ast.FunctionDef) -> Iterator[tuple[int, Kind, str]]:
    for n in ast.walk(fn):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
            continue
        name = n.func.attr
        if name in _OP_DROPS:
            yield n.lineno, "drop", f"op.{name}"
        elif name == "rename_table":
            yield n.lineno, "rename", "op.rename_table"
        elif name == "alter_column":
            if _kw(n, "new_column_name") is not None:
                yield n.lineno, "rename", "op.alter_column(new_column_name=)"
            if _kw(n, "type_") is not None:
                yield n.lineno, "type_change", "op.alter_column(type_=)"
            if _false(_kw(n, "nullable")):
                yield n.lineno, "not_null", "op.alter_column(nullable=False)"
        elif name == "add_column":
            for col in (a for a in n.args if isinstance(a, ast.Call)):
                if _false(_kw(col, "nullable")) and _kw(col, "server_default") is None:
                    yield n.lineno, "not_null", "op.add_column(nullable=False, no default)"


def _values(text: str) -> dict[str, set[str]]:
    return {
        m.group("name"): {
            v.strip().strip("'\"") for v in m.group("values").split(",") if v.strip()
        }
        for m in _CHECK_IN.finditer(text)
    }


def operations(path: Path) -> list[Operation]:
    """The contract operations in one migration's `upgrade()`."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    up = _function(tree, "upgrade")
    if up is None:
        return []
    rel = str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path)
    found: list[Operation] = []
    upgrade_text: list[str] = []
    for line, text in _strings(up):
        upgrade_text.append(text)
        for kind, pattern in _SQL_RULES:
            m = pattern.search(text)
            if m:
                found.append(Operation(rel, line, kind, m.group(0)))
        for m in _ADD_NOT_NULL.finditer(text):
            if not re.search(r"\bDEFAULT\b", m.group("rest"), re.IGNORECASE):
                found.append(Operation(rel, line, "not_null", m.group(0).strip()[:80]))
    found += [Operation(rel, line, kind, text) for line, kind, text in _op_calls(up)]
    down = _function(tree, "downgrade")
    if down is not None:
        restored = _values(" ".join(t for _l, t in _strings(down)))
        for name, now in _values(" ".join(upgrade_text)).items():
            removed = restored.get(name, set()) - now
            if removed:
                found.append(
                    Operation(
                        rel,
                        up.lineno,
                        "value_removal",
                        f"{name} drops {', '.join(sorted(removed))}",
                    )
                )
    return sorted(found, key=lambda o: (o.line, o.kind))


# --- Which migrations, and the verdict --------------------------------------------------------


def new_migrations(base: str) -> list[Path]:
    """Migration files this branch adds or changes against `base` (`git diff base...HEAD`)."""
    out = subprocess.run(
        [
            GIT,
            "-C",
            str(REPO),
            "diff",
            "--name-only",
            "--diff-filter=AM",
            f"{base}...HEAD",
            "--",
            str(VERSIONS),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sorted(REPO / p for p in out.split() if p.endswith(".py"))


@dataclass(frozen=True)
class Verdict:
    operations: tuple[Operation, ...]
    refused: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.refused


def judge(
    paths: Iterable[Path],
    *,
    labels: Sequence[str] = (),
    today: date,
    window: str | None = None,
) -> Verdict:
    """The guard's decision. Inactive before `ACTIVE_FROM`; from then a contract operation needs
    the `contract-step` label; inside a window (`window` names it) it is refused regardless."""
    ops = tuple(o for p in paths for o in operations(p))
    if not ops or today < ACTIVE_FROM:
        return Verdict(ops, ())
    if window is not None:
        return Verdict(ops, tuple(f"contract_operation_in_window:{window}" for _ in ops[:1]))
    if LABEL in labels:
        return Verdict(ops, ())
    return Verdict(ops, ("contract_step_label_missing",))


def window_of(at: datetime, path: Path = release_windows.WINDOWS_FILE) -> str | None:
    """The release window any live firm is in at `at` (platform rule), or None."""
    return release_windows.platform_window(release_windows.load(path), at)


# --- CLI -----------------------------------------------------------------------------------------


def _report(verdict: Verdict) -> None:
    for o in verdict.operations:
        print(f"{o.path}:{o.line}: {o.kind}: {o.text}")
    for why in verdict.refused:
        print(f"refused: {why}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="expand_only", description=(__doc__ or "").split("\n")[0]
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "window"):
        p = sub.add_parser(name)
        p.add_argument("--base", default="origin/main")
        p.add_argument("--label", action="append", default=[])
        p.add_argument("--file", action="append", default=[], type=Path)
        if name == "check":
            p.add_argument("--today", type=date.fromisoformat, default=None)
        else:
            p.add_argument("--at", type=datetime.fromisoformat, required=True)
            p.add_argument("--windows", type=Path, default=release_windows.WINDOWS_FILE)
    args = parser.parse_args(argv)
    if args.command == "check":
        today = args.today or release_windows.local_day(datetime.now(release_windows.CT))
        if today < ACTIVE_FROM and not args.file:
            print(f"expand-only guard inactive until {ACTIVE_FROM.isoformat()}")
            return 0
        paths = [Path(f) for f in args.file] or new_migrations(args.base)
        verdict = judge(paths, labels=args.label, today=today)
    else:
        paths = [Path(f) for f in args.file] or new_migrations(args.base)
        at: datetime = args.at
        verdict = judge(
            paths,
            labels=args.label,
            today=release_windows.local_day(at),
            window=window_of(at, args.windows),
        )
    _report(verdict)
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    sys.exit(main())
