"""Banned-pattern checker for rules ruff cannot express (ADR-083). PROTECTED.

Run: python -m abacus_tools.quality.banned_patterns

There are no inline suppressions. An exception is an `exclude` glob on the rule in this file,
which is a protected path, so every exception gets founder review. Globs use fnmatch semantics
relative to `backend/`: `*` also matches `/`.
"""

from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3]
SCAN_ROOTS = ("src", "tests")
TOP_LEVEL_PACKAGES = frozenset({"abacus", "abacus_tools"})
LAYOUT_IGNORED = ("__pycache__", ".DS_Store", "*.egg-info")


@dataclass(frozen=True)
class SourceFile:
    rel: str
    module: str | None
    tree: ast.Module
    comments: dict[int, str]


@dataclass(frozen=True)
class Finding:
    line: int
    message: str


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    rule_id: str
    message: str
    adr: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule_id} {self.message} ({self.adr})"


@dataclass(frozen=True)
class Rule:
    """A check run on every Python file under SCAN_ROOTS that matches include and not exclude."""

    id: str
    description: str
    adr: str
    check: Callable[[SourceFile], Iterator[Finding]]
    include: tuple[str, ...] = ("*.py",)
    exclude: tuple[str, ...] = ()

    def applies_to(self, rel: str) -> bool:
        return any(fnmatch(rel, g) for g in self.include) and not any(
            fnmatch(rel, g) for g in self.exclude
        )


@dataclass(frozen=True)
class TreeRule:
    """A check run once over the backend directory tree."""

    id: str
    description: str
    adr: str
    check: Callable[[Path], Iterator[tuple[str, Finding]]]


# --- helpers ----------------------------------------------------------------------------------


def _terminal_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _calls(tree: ast.Module) -> Iterator[ast.Call]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node


def _module_name(rel: str) -> str | None:
    """Dotted module name for files under src/, else None."""
    parts = Path(rel).with_suffix("").parts
    if not parts or parts[0] != "src":
        return None
    names = list(parts[1:])
    if names and names[-1] == "__init__":
        names.pop()
    return ".".join(names) or None


def _resolve_from(src: SourceFile, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module
    if src.module is None:
        return None
    package = src.module.split(".")
    if not src.rel.endswith("__init__.py"):
        package = package[:-1]
    if node.level > 1:
        package = package[: len(package) - (node.level - 1)]
    base = ".".join(package)
    return f"{base}.{node.module}" if node.module else base


# --- file rules -------------------------------------------------------------------------------


def _check_session_transaction(src: SourceFile) -> Iterator[Finding]:
    for call in _calls(src.tree):
        func = call.func
        if isinstance(func, ast.Attribute) and func.attr in {"commit", "flush", "rollback"}:
            receiver = _terminal_name(func.value)
            if receiver is not None and "session" in receiver.lower():
                yield Finding(call.lineno, f"{receiver}.{func.attr}() outside the unit of work")


def _check_raw_connection(src: SourceFile) -> Iterator[Finding]:
    for call in _calls(src.tree):
        func = call.func
        name = _terminal_name(func)
        if name in {"create_engine", "create_async_engine"}:
            yield Finding(call.lineno, f"{name}() outside abacus.kernel.db")
        elif (
            isinstance(func, ast.Attribute)
            and func.attr == "connect"
            and _terminal_name(func.value) == "asyncpg"
        ):
            yield Finding(call.lineno, "asyncpg.connect() outside abacus.kernel.db")


def _is_built_string(node: ast.expr) -> bool:
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add | ast.Mod):
        return True
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
    )


def _check_built_sql(src: SourceFile) -> Iterator[Finding]:
    for call in _calls(src.tree):
        name = _terminal_name(call.func)
        if (
            name in {"text", "execute", "exec_driver_sql"}
            and call.args
            and _is_built_string(call.args[0])
        ):
            yield Finding(call.lineno, f"{name}() with a built string; use bound parameters")


def _check_module_boundary(src: SourceFile) -> Iterator[Finding]:
    own = (
        src.module.split(".")[2]
        if src.module and src.module.startswith("abacus.modules.")
        else None
    )

    def check(target: str, line: int) -> Iterator[Finding]:
        parts = target.split(".")
        if len(parts) < 3 or parts[:2] != ["abacus", "modules"] or parts[2] == own:
            return
        if len(parts) == 3 or parts[3] != "api":
            yield Finding(line, f"import of {target}; other modules are reachable only via api")

    for node in ast.walk(src.tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield from check(alias.name, node.lineno)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_from(src, node)
            if base is None:
                continue
            if base.count(".") == 2 and base.startswith("abacus.modules."):
                for alias in node.names:
                    yield from check(f"{base}.{alias.name}", node.lineno)
            else:
                yield from check(base, node.lineno)


_IGNORE_COMMENT = re.compile(r"#\s*(?:type|pyright):\s*ignore(?:\[[^\]]*\])?(?P<rest>.*)$")


def _check_unexplained_ignore(src: SourceFile) -> Iterator[Finding]:
    for line, comment in src.comments.items():
        match = _IGNORE_COMMENT.search(comment)
        if match and not match.group("rest").strip(" #-:\t"):
            yield Finding(line, "type-checker ignore without a reason after it")


def _check_unexplained_any(src: SourceFile) -> Iterator[Finding]:
    import_lines: set[int] = set()
    any_lines: set[int] = set()
    for node in ast.walk(src.tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            import_lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
        elif (isinstance(node, ast.Name) and node.id == "Any") or (
            isinstance(node, ast.Attribute) and node.attr == "Any"
        ):
            any_lines.add(node.lineno)
    for line in sorted(any_lines - import_lines):
        comment = src.comments.get(line, "")
        if not comment or _IGNORE_COMMENT.search(comment):
            yield Finding(line, "Any without an explanatory comment on the same line")


# --- tree rules -------------------------------------------------------------------------------


def _check_layout(backend: Path) -> Iterator[tuple[str, Finding]]:
    src = backend / "src"
    if not src.is_dir():
        return
    for entry in sorted(src.iterdir()):
        if entry.name in TOP_LEVEL_PACKAGES or any(fnmatch(entry.name, g) for g in LAYOUT_IGNORED):
            continue
        yield (
            f"src/{entry.name}",
            Finding(1, "only abacus/ and abacus_tools/ may live under backend/src/"),
        )


RULES: list[Rule | TreeRule] = [
    Rule(
        id="UOW-001",
        description="No direct session commit, flush or rollback",
        adr="ADR-007, ADR-018",
        check=_check_session_transaction,
        exclude=("src/abacus/kernel/uow/*",),
    ),
    Rule(
        id="DB-001",
        description="No engines or raw connections; use tenant_session(ctx)",
        adr="ADR-014",
        check=_check_raw_connection,
        exclude=("src/abacus/kernel/db/*",),
    ),
    Rule(
        id="SQL-001",
        description="No SQL built from f-strings, %, + or .format()",
        adr="ADR-014",
        check=_check_built_sql,
    ),
    Rule(
        id="BOUND-001",
        description="Other modules are imported only through their api",
        adr="ADR-008, ADR-101",
        check=_check_module_boundary,
        exclude=("tests/*",),
    ),
    TreeRule(
        id="LAYOUT-001",
        description="Only abacus/ and abacus_tools/ under backend/src/",
        adr="ADR-101",
        check=_check_layout,
    ),
    Rule(
        id="TYPE-001",
        description="Type-checker ignores carry a reason",
        adr="ADR-009",
        check=_check_unexplained_ignore,
    ),
    Rule(
        id="ANY-001",
        description="Any is explained by a comment on the same line",
        adr="ADR-009",
        check=_check_unexplained_any,
    ),
]


# --- runner -----------------------------------------------------------------------------------


def _comments(text: str) -> dict[int, str]:
    found: dict[int, str] = {}
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT:
            found[tok.start[0]] = tok.string
    return found


def _python_files(backend: Path) -> Iterator[Path]:
    for root in SCAN_ROOTS:
        base = backend / root
        if base.is_dir():
            yield from (p for p in sorted(base.rglob("*.py")) if "__pycache__" not in p.parts)


def scan(backend: Path = BACKEND) -> list[Violation]:
    violations: list[Violation] = []
    for rule in RULES:
        if isinstance(rule, TreeRule):
            for rel, f in rule.check(backend):
                violations.append(Violation(rel, f.line, rule.id, f.message, rule.adr))
    file_rules = [r for r in RULES if isinstance(r, Rule)]
    for path in _python_files(backend):
        rel = path.relative_to(backend).as_posix()
        text = path.read_text(encoding="utf-8")
        try:
            src = SourceFile(rel, _module_name(rel), ast.parse(text, rel), _comments(text))
        except (SyntaxError, tokenize.TokenError) as exc:
            violations.append(Violation(rel, 1, "PARSE-001", f"cannot parse: {exc}", "ADR-083"))
            continue
        for rule in file_rules:
            if rule.applies_to(rel):
                for f in rule.check(src):
                    violations.append(Violation(rel, f.line, rule.id, f.message, rule.adr))
    return sorted(violations, key=lambda v: (v.path, v.line, v.rule_id))


def main() -> int:
    violations = scan()
    for v in violations:
        print(v)
    if violations:
        print(f"{len(violations)} banned-pattern violation(s).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
