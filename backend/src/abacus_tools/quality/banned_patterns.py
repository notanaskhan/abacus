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
        if not isinstance(func, ast.Attribute):
            continue
        receiver = _terminal_name(func.value) or "<expr>"
        # commit/rollback on any receiver; flush only on sessions (files and loggers flush too).
        if func.attr in {"commit", "rollback"} or (
            func.attr == "flush" and "session" in receiver.lower()
        ):
            yield Finding(call.lineno, f"{receiver}.{func.attr}() outside the unit of work")


def _check_raw_connection(src: SourceFile) -> Iterator[Finding]:
    for call in _calls(src.tree):
        func = call.func
        name = _terminal_name(func)
        if name in {"create_engine", "create_async_engine"}:
            yield Finding(call.lineno, f"{name}() outside abacus.kernel.db")
        elif isinstance(func, ast.Attribute) and (func.attr, _terminal_name(func.value)) in {
            ("connect", "asyncpg"),
            ("create_pool", "asyncpg"),
            ("connect", "psycopg"),
            ("connect", "psycopg2"),
        }:
            yield Finding(
                call.lineno, f"{_terminal_name(func.value)}.{func.attr}() outside abacus.kernel.db"
            )


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
        if target == "abacus.modules":
            yield Finding(
                line, "import of the abacus.modules package; import <module>.api instead"
            )
            return
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
            if base in {"abacus", "abacus.modules"} or (
                base.count(".") == 2 and base.startswith("abacus.modules.")
            ):
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


_NOQA = re.compile(r"#\s*noqa\s*:\s*(?P<codes>[A-Z0-9, ]+)", re.IGNORECASE)
_GATE_CODES = re.compile(r"^(?:TID|S)\d", re.IGNORECASE)


def _check_gate_suppression(src: SourceFile) -> Iterator[Finding]:
    for line, comment in src.comments.items():
        if re.search(r"\bnosec\b", comment):
            yield Finding(line, "# nosec silences a security gate")
        match = _NOQA.search(comment)
        if match:
            codes = [c.strip() for c in match.group("codes").split(",")]
            silenced = [c for c in codes if _GATE_CODES.match(c)]
            if silenced:
                yield Finding(line, f"# noqa silences a gate rule ({', '.join(silenced)})")


PROVIDER_HOSTS = (
    "api.anthropic.com",
    "api.openai.com",
    "generativelanguage.googleapis.com",
    "aiplatform.googleapis.com",
    "api.mistral.ai",
    "api.cohere.com",
    "api.cohere.ai",
    "api.groq.com",
    "api.together.xyz",
    "bedrock-runtime",
    "bedrock-agent-runtime",
)


def _check_provider_host(src: SourceFile) -> Iterator[Finding]:
    for node in ast.walk(src.tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            hit = next((h for h in PROVIDER_HOSTS if h in node.value), None)
            if hit is not None:
                yield Finding(node.lineno, f"model provider endpoint '{hit}' outside ai_gateway")


_ISSUE_REF = re.compile(r"#\d+|github\.com/[^/\s]+/[^/\s]+/issues/\d+")
_SKIP_MARKS = frozenset({"skip", "skipif", "xfail"})
_SKIP_CALLS = frozenset({"skip", "xfail", "importorskip"})


def _skip_kind(node: ast.expr) -> str | None:
    """`mark.skip`-style name for pytest.mark.<x>, `call.<x>` for pytest.<x>(), else None."""
    if not isinstance(node, ast.Attribute):
        return None
    value = node.value
    if (
        node.attr in _SKIP_MARKS
        and isinstance(value, ast.Attribute)
        and value.attr == "mark"
        and isinstance(value.value, ast.Name)
        and value.value.id == "pytest"
    ):
        return f"mark.{node.attr}"
    if node.attr in _SKIP_CALLS and isinstance(value, ast.Name) and value.id == "pytest":
        return f"call.{node.attr}"
    return None


def _skip_reason(call: ast.Call, kind: str) -> str:
    for kw in call.keywords:
        if kw.arg in {"reason", "msg"} and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    positional_reason = kind in {"mark.skip", "mark.xfail", "call.skip", "call.xfail"}
    first = call.args[0] if call.args else None
    if positional_reason and isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return ""


_ALIASED = "pytest aliased; use pytest.mark/pytest.skip directly so skips stay checkable"


def _is_pytest_mark(node: ast.expr | None) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "mark"
        and isinstance(node.value, ast.Name)
        and node.value.id == "pytest"
    )


def _pytest_aliases(src: SourceFile) -> Iterator[Finding]:
    for node in ast.walk(src.tree):
        if isinstance(node, ast.ImportFrom) and node.module == "pytest":
            if any(a.name in {"mark", *_SKIP_CALLS} for a in node.names):
                yield Finding(node.lineno, _ALIASED)
        elif isinstance(node, ast.Import):
            if any(a.name == "pytest" and a.asname not in {None, "pytest"} for a in node.names):
                yield Finding(node.lineno, _ALIASED)
        elif isinstance(node, ast.Assign | ast.AnnAssign) and _is_pytest_mark(node.value):
            yield Finding(node.lineno, _ALIASED)


def _check_unlinked_skip(src: SourceFile) -> Iterator[Finding]:
    yield from _pytest_aliases(src)
    called: set[int] = set()
    for call in _calls(src.tree):
        kind = _skip_kind(call.func)
        if kind is None:
            continue
        called.add(id(call.func))
        if not _ISSUE_REF.search(_skip_reason(call, kind)):
            yield Finding(call.lineno, f"pytest {kind.split('.')[1]} without an issue reference")
    for node in ast.walk(src.tree):
        if not isinstance(node, ast.Attribute) or id(node) in called:
            continue
        kind = _skip_kind(node)
        if kind is not None and kind.startswith("mark."):
            yield Finding(node.lineno, f"pytest {kind[5:]} without an issue reference")


_SIDESTEPS = {
    "create_subprocess_exec": "use subprocess.run (ruff S603 covers it)",
    "create_subprocess_shell": "use subprocess.run (ruff S602/S603 cover it)",
    "XMLPullParser": "use xml.etree.ElementTree.fromstring (ruff S314 covers it)",
    "subprocess_exec": "use subprocess.run (ruff S603 covers it)",
    "subprocess_shell": "use subprocess.run (ruff S602/S603 cover it)",
    "popen": "use subprocess.run (ruff S603 covers it)",
    "posix_spawn": "use subprocess.run (ruff S603 covers it)",
    "posix_spawnp": "use subprocess.run (ruff S603 covers it)",
}


def _check_lint_sidestep(src: SourceFile) -> Iterator[Finding]:
    """APIs equivalent to ones ruff's S rules check, but which those rules miss."""
    for node in ast.walk(src.tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in _SIDESTEPS:
                    yield Finding(node.lineno, f"{alias.name}: {_SIDESTEPS[alias.name]}")
        elif isinstance(node, ast.Attribute) and node.attr in _SIDESTEPS:
            yield Finding(node.lineno, f"{node.attr}: {_SIDESTEPS[node.attr]}")


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
        # The local-stack smoke tests check the database container itself; nothing else may.
        exclude=(
            "src/abacus/kernel/db/*",
            "tests/integration/conftest.py",
            "tests/integration/test_local_stack.py",
        ),
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
        id="SUPPRESS-001",
        description="No noqa for TID/S rules and no nosec; gate exceptions live in config",
        adr="ADR-009, ADR-019, ADR-083",
        check=_check_gate_suppression,
    ),
    Rule(
        id="PROVIDER-001",
        description="Model provider endpoints are referenced only in ai_gateway",
        adr="ADR-019",
        check=_check_provider_host,
        exclude=(
            "src/abacus/ai_gateway/*",
            "src/abacus_tools/quality/banned_patterns.py",
            "tests/unit/quality/*",
        ),
    ),
    Rule(
        id="SKIP-001",
        description="skip and xfail carry an issue reference",
        adr="ADR-079",
        check=_check_unlinked_skip,
    ),
    Rule(
        id="SIDESTEP-001",
        description="No APIs that sidestep ruff's security rules; exempt in pyproject instead",
        adr="ADR-083",
        check=_check_lint_sidestep,
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
