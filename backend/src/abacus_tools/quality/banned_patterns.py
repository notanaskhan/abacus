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


_TENANT_SETTINGS = ("app.tenant_id", "app.actor_")


def _check_tenant_setting(src: SourceFile) -> Iterator[Finding]:
    for node in ast.walk(src.tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and any(setting in node.value for setting in _TENANT_SETTINGS)
        ):
            yield Finding(
                node.lineno, "tenant and actor settings are written only by abacus.kernel.db"
            )


# The unit of work's own connection, and the relay's BYPASSRLS engine.
_UOW_ONLY = frozenset({"tenant_connection", "relay_engine", "configure_relay_engine"})


def _check_tenant_connection(src: SourceFile) -> Iterator[Finding]:
    for node in ast.walk(src.tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in _UOW_ONLY:
                    yield Finding(node.lineno, f"{alias.name} is for abacus.kernel.uow only")
        elif isinstance(node, ast.Attribute) and node.attr in _UOW_ONLY:
            yield Finding(node.lineno, f"{node.attr} is for abacus.kernel.uow only")


def _names_used(src: SourceFile) -> Iterator[tuple[int, str]]:
    """Every identifier the file mentions: imported names, names, attributes, parameters."""
    for node in ast.walk(src.tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.Name):
            yield node.lineno, node.id
        elif isinstance(node, ast.Attribute):
            yield node.lineno, node.attr
        elif isinstance(node, ast.arg):
            yield node.lineno, node.arg


def _imported_modules(src: SourceFile) -> Iterator[tuple[int, str]]:
    for node in ast.walk(src.tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            yield node.lineno, node.module or ""
        elif (
            isinstance(node, ast.Call)
            and _terminal_name(node.func) in {"import_module", "__import__"}
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            yield node.lineno, node.args[0].value


def _string_constants(src: SourceFile) -> Iterator[tuple[int, str]]:
    for node in ast.walk(src.tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


# The sign-in engine (abacus_identity, BYPASSRLS) and its URL: only the identity repository.
_IDENTITY_ENGINE = frozenset(
    {"identity_engine", "configure_identity_engine", "identity_database_url"}
)


def _check_identity_engine(src: SourceFile) -> Iterator[Finding]:
    for line, name in _names_used(src):
        if name in _IDENTITY_ENGINE:
            yield Finding(line, f"{name} is for the identity repository only")
    for node in ast.walk(src.tree):
        if (
            isinstance(node, ast.ImportFrom)
            and (node.module or "").startswith("abacus.kernel.db")
            and any(alias.name == "*" for alias in node.names)
        ):
            yield Finding(node.lineno, "star import from abacus.kernel.db")


_TOKEN_LIBRARIES = ("jwt", "jose", "josepy", "jwcrypto", "authlib", "python_jose")


def _check_token_library(src: SourceFile) -> Iterator[Finding]:
    for line, module in _imported_modules(src):
        if any(module == lib or module.startswith(f"{lib}.") for lib in _TOKEN_LIBRARIES):
            yield Finding(
                line, "tokens are read only in identity.tokens; never take roles from them"
            )


def _check_authorization_header(src: SourceFile) -> Iterator[Finding]:
    message = "the Authorization header is read only when building the request context"
    for line, value in _string_constants(src):
        if value.strip().lower() == "authorization":
            yield Finding(line, message)
    for node in ast.walk(src.tree):
        if isinstance(node, ast.arg) and node.arg == "authorization":  # a FastAPI header param
            yield Finding(node.lineno, message)
    for line, module in _imported_modules(src):
        if module == "fastapi.security" or module.startswith("fastapi.security."):
            yield Finding(line, message)


# Firm and engagement roles from the permission matrix. Actor kinds (`agent`, `system`) and client
# roles are left out: their names are ordinary words compared for other reasons.
_ROLE_NAMES = frozenset(
    {"firm_admin", "practice_leader", "quality_partner", "engagement_partner", "manager"}
    | {"senior", "staff", "reviewer"}
)
_ROLE_ATTRIBUTES = frozenset({"role", "firm_role", "roles"})


def _is_role_shaped(node: ast.expr) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr in _ROLE_ATTRIBUTES) or (
        isinstance(node, ast.Name) and node.id in _ROLE_ATTRIBUTES
    )


def _is_role_value(node: ast.expr) -> bool:
    if isinstance(node, ast.Tuple | ast.List | ast.Set):
        return any(_is_role_value(element) for element in node.elts)
    return isinstance(node, ast.Constant) and node.value in _ROLE_NAMES


def _check_role_comparison(src: SourceFile) -> Iterator[Finding]:
    """A role-shaped operand compared with a role name: `x.role == "manager"`,
    `role in ("senior", "staff")`. `role is None` or `message.role == "assistant"` are fine."""
    message = "role checks belong in identity.authz; call authorise()"
    for node in ast.walk(src.tree):
        if isinstance(node, ast.Compare):
            operands = (node.left, *node.comparators)
            if any(_is_role_shaped(o) for o in operands) and any(
                _is_role_value(o) for o in operands
            ):
                yield Finding(node.lineno, message)
        elif isinstance(node, ast.Match) and _is_role_shaped(node.subject):
            yield Finding(node.lineno, message)


def _check_firm_role_read(src: SourceFile) -> Iterator[Finding]:
    for node in ast.walk(src.tree):
        if isinstance(node, ast.Attribute) and node.attr == "firm_role":
            yield Finding(node.lineno, "firm roles are read only by identity; call authorise()")


_TENANT_HEADER_NAMES = frozenset({"x_abacus_tenant", "TENANT_HEADER"})


def _check_tenant_header(src: SourceFile) -> Iterator[Finding]:
    message = "the tenant header is read only when building the request context"
    for line, value in _string_constants(src):
        if "x-abacus-tenant" in value.lower():
            yield Finding(line, message)
    for line, name in _names_used(src):
        if name in _TENANT_HEADER_NAMES:
            yield Finding(line, message)


# Ways to serve HTTP without AbacusRouter's authentication and action check.
_WEB_CLASSES = frozenset(
    {"APIRouter", "APIRoute", "APIWebSocketRoute", "FastAPI", "Starlette", "Mount", "Route"}
    | {"Router", "WebSocketRoute", "BaseHTTPMiddleware", "StaticFiles"}
)
_WEB_METHODS = frozenset(
    {"add_api_route", "add_route", "add_websocket_route", "add_api_websocket_route", "websocket"}
    | {"mount", "include_router", "add_middleware"}
)


def _check_route_bypass(src: SourceFile) -> Iterator[Finding]:
    def finding(line: int, name: str) -> Finding:
        return Finding(line, f"{name}: serve routes only through identity's AbacusRouter")

    for node in ast.walk(src.tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in {
            "fastapi",
            "starlette",
        }:
            for alias in node.names:
                if alias.name in _WEB_CLASSES:
                    yield finding(node.lineno, alias.name)
        elif isinstance(node, ast.Attribute) and (
            node.attr == "dependency_overrides"
            or (
                node.attr in _WEB_CLASSES
                and _terminal_name(node.value)
                in {"fastapi", "starlette", "routing", "applications"}
            )
        ):
            yield finding(node.lineno, node.attr)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _WEB_METHODS
        ):
            yield finding(node.lineno, node.func.attr)


def _check_self_action(src: SourceFile) -> Iterator[Finding]:
    for line, name in _names_used(src):
        if name == "SELF":
            yield Finding(line, "the SELF action is for /v1/me only")


def _check_context_construction(src: SourceFile) -> Iterator[Finding]:
    """Human request contexts come from a validated membership (ADR-002), never built or copied by
    hand. (Agent and system `TenantContext`s are built by their own tasks' context builders.)"""
    for node in ast.walk(src.tree):
        if not isinstance(node, ast.Call):
            continue
        name = _terminal_name(node.func)
        if name == "AuthContext":
            yield Finding(node.lineno, "contexts are built only from a validated membership")
        elif name in {"replace", "copy", "deepcopy", "__replace__"} and any(
            "ctx" in (_terminal_name(arg) or "").lower()
            or "context" in (_terminal_name(arg) or "")
            for arg in node.args
        ):
            yield Finding(node.lineno, "contexts are never copied with changes")


def _check_resource_archived(src: SourceFile) -> Iterator[Finding]:
    """`archived` comes from the engagement row, never a literal (TASK-008 loads it)."""
    for node in ast.walk(src.tree):
        if isinstance(node, ast.Call) and _terminal_name(node.func) in {"engagement", "Resource"}:
            for keyword in node.keywords:
                if keyword.arg == "archived" and isinstance(keyword.value, ast.Constant):
                    yield Finding(node.lineno, "archived must come from the engagement row")
            if (
                _terminal_name(node.func) == "Resource"
                and len(node.args) >= 3
                and isinstance(node.args[2], ast.Constant)
            ):
                yield Finding(node.lineno, "archived must come from the engagement row")


_LIST_PREFIXES = ("list_", "all_", "search_")
# Repository functions that return many rows without `visible()`, each reviewed: they serve
# lookups for rows the caller has already authorised, or sign-in before a tenant exists.
LIST_EXEMPT = frozenset(
    {
        ("src/abacus/modules/identity/repository.py", "active_memberships"),
        ("src/abacus/modules/identity/repository.py", "engagement_members_of"),
        ("src/abacus/modules/identity/repository.py", "display_names"),
        ("src/abacus/modules/organisations/repository.py", "names_of"),
    }
)


def _read_actions() -> frozenset[str]:
    from abacus.modules.identity.authz.matrix import RULES  # tooling may import product

    return frozenset(action for action, rule in RULES.items() if rule.reads)


def _visible_in_where(function: ast.AST) -> list[ast.Call]:
    """`visible(...)` calls passed (directly or nested) to a `.where(...)`."""
    found: list[ast.Call] = []
    for call in ast.walk(function):
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "where"
        ):
            for arg in call.args:
                found += [
                    inner
                    for inner in ast.walk(arg)
                    if isinstance(inner, ast.Call) and _terminal_name(inner.func) == "visible"
                ]
    return found


def _returns_many(function: ast.AST) -> bool:
    return any(
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "all"
        for call in ast.walk(function)
    )


def _check_list_visible(src: SourceFile) -> Iterator[Finding]:
    """ADR-027, ADR-102: repository functions that list rows filter them with `visible(ctx,
    "<read action>", <column>)` inside `.where(...)`."""
    reads = _read_actions()
    for node in ast.walk(src.tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        listing = node.name.startswith(_LIST_PREFIXES) or _returns_many(node)
        if not listing or (src.rel, node.name) in LIST_EXEMPT:
            continue
        applied = _visible_in_where(node)
        if not applied:
            yield Finding(node.lineno, f"{node.name}() must filter with visible() in .where()")
            continue
        for call in applied:
            action = call.args[1] if len(call.args) > 1 else None
            if not (isinstance(action, ast.Constant) and action.value in reads):
                yield Finding(call.lineno, "visible() needs a literal read action from the matrix")


# Which other modules each module may import (ADR-008: one-way dependencies). Modules not listed
# may use identity only. Identity and organisations depend on no module.
MODULE_DEPENDENCIES: dict[str, frozenset[str]] = {
    "identity": frozenset(),
    "organisations": frozenset(),
    "engagements": frozenset({"identity", "organisations"}),
    "requests": frozenset({"identity", "engagements"}),
    "evidence": frozenset({"identity", "engagements"}),
}


def _own_module(src: SourceFile) -> str | None:
    if src.module and src.module.startswith("abacus.modules."):
        parts = src.module.split(".")
        return parts[2] if len(parts) > 2 else None
    return None


def _check_module_direction(src: SourceFile) -> Iterator[Finding]:
    own = _own_module(src)
    if own is None:
        return
    allowed = MODULE_DEPENDENCIES.get(own, frozenset({"identity"}))
    for node in ast.walk(src.tree):
        if isinstance(node, ast.Import):
            targets = [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_from(src, node)
            targets = [(node.lineno, base)] if base else []
        else:
            continue
        for line, target in targets:
            parts = target.split(".")
            if (
                len(parts) > 2
                and parts[:2] == ["abacus", "modules"]
                and parts[2] != own
                and parts[2] not in allowed
            ):
                yield Finding(line, f"{own} may not depend on {parts[2]} (ADR-008)")


# SQL in string constants: statements start with an upper-case verb (the codebase's SQL style).
_SQL_STATEMENT = re.compile(r"^\s*(?:SELECT|INSERT|UPDATE|DELETE|WITH)\b")
_SQL_TABLE = re.compile(r"\b(?:FROM|JOIN|INTO|UPDATE)\s+([a-z_][a-z0-9_]*)")


def _table_owners() -> dict[str, str]:
    from abacus_tools.quality.schema_check import TABLE_OWNERS

    return TABLE_OWNERS


def _check_table_ownership(src: SourceFile) -> Iterator[Finding]:
    """ADR-008, ADR-103: a module names only tables it owns (models, Core tables, raw SQL)."""
    own = _own_module(src)
    if own is None:
        return
    owners = _table_owners()

    def check(table: str, line: int) -> Iterator[Finding]:
        owner = owners.get(table)
        if owner != own:
            whose = f"owned by {owner}" if owner else "not in TABLE_OWNERS"
            yield Finding(line, f"table {table} is {whose}; {own} may use only its own tables")

    for node in ast.walk(src.tree):
        if (
            isinstance(node, ast.Assign | ast.AnnAssign)
            and any(
                isinstance(t, ast.Name) and t.id == "__tablename__"
                for t in (node.targets if isinstance(node, ast.Assign) else [node.target])
            )
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            yield from check(node.value.value, node.lineno)
        elif (
            isinstance(node, ast.Call)
            and _terminal_name(node.func) == "Table"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            yield from check(node.args[0].value, node.lineno)
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _SQL_STATEMENT.match(node.value)
        ):
            for match in _SQL_TABLE.finditer(node.value):
                yield from check(match.group(1), node.lineno)


# Libraries that only one kernel package may use (ADR-016, ADR-104).
def _check_confined(
    prefixes: tuple[str, ...], where: str
) -> Callable[[SourceFile], Iterator[Finding]]:
    def check(src: SourceFile) -> Iterator[Finding]:
        for line, module in _imported_modules(src):
            if any(module == p or module.startswith(f"{p}.") for p in prefixes):
                yield Finding(line, f"{module.split('.')[0]} is used only in {where}")

    return check


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
        # test_tenancy proves session.commit() is inert inside tenant_session (TASK-005).
        exclude=(
            "src/abacus/kernel/uow/*",
            "tests/integration/test_tenancy.py",
            "tests/integration/test_uow_session_rollback.py",
        ),
    ),
    Rule(
        id="DB-001",
        description="No engines or raw connections; use tenant_session(ctx)",
        adr="ADR-014",
        check=_check_raw_connection,
        # Only code whose job is the database itself: the kernel; schema_check (catalog and roles);
        # the local-stack smoke tests; the tenancy and schema tests (owner, app and admin roles).
        exclude=(
            "src/abacus/kernel/db/*",
            "src/abacus_tools/quality/schema_check.py",
            "tests/integration/conftest.py",
            "tests/integration/test_local_stack.py",
            "tests/integration/test_tenancy.py",
            "tests/integration/test_schema_check_db.py",
            "tests/integration/test_migrations_env.py",
            "tests/integration/test_unit_of_work.py",
            "tests/integration/test_outbox_relay.py",
            "tests/integration/test_identity.py",
            "tests/integration/test_engagements.py",
            "tests/integration/test_engagements_schema.py",
            "tests/integration/test_evidence.py",
        ),
    ),
    Rule(
        id="SQL-001",
        description="No SQL built from f-strings, %, + or .format()",
        adr="ADR-014",
        check=_check_built_sql,
        # DDL can't bind identifiers; migration helpers validate table names first.
        exclude=("src/abacus/kernel/db/migration.py",),
    ),
    Rule(
        id="BOUND-001",
        description="Other modules are imported only through their api",
        adr="ADR-008, ADR-101",
        check=_check_module_boundary,
        exclude=("tests/*", "src/abacus_tools/quality/banned_patterns.py"),
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
        id="UOW-002",
        description="Only the unit of work uses tenant_connection and the relay engine",
        adr="ADR-018",
        check=_check_tenant_connection,
        exclude=(
            "src/abacus/kernel/db/*",
            "src/abacus/kernel/uow/*",
            "tests/integration/*",
        ),
    ),
    Rule(
        id="TENANT-001",
        description="Only abacus.kernel.db touches the app.tenant_id and app.actor_* settings",
        adr="ADR-014",
        check=_check_tenant_setting,
        exclude=(
            "src/abacus/kernel/db/*",
            "src/abacus_tools/quality/schema_check.py",
            "src/abacus_tools/quality/banned_patterns.py",
            "tests/integration/test_tenancy.py",
            "tests/integration/test_schema_check_db.py",
            "tests/unit/kernel/test_migration_helpers.py",
            "tests/unit/quality/test_banned_patterns.py",
        ),
    ),
    Rule(
        id="UOW-003",
        description="Only the identity repository uses the identity engine",
        adr="ADR-002, ADR-014",
        check=_check_identity_engine,
        exclude=(
            "src/abacus/kernel/db/*",
            "src/abacus/kernel/config.py",
            "src/abacus/modules/identity/repository.py",
            "tests/integration/conftest.py",
            "tests/unit/kernel/test_config.py",
            "tests/integration/test_identity.py",
        ),
    ),
    Rule(
        id="AUTH-001",
        description="Only identity.tokens reads bearer tokens; roles never come from them",
        adr="ADR-029",
        check=_check_token_library,
        exclude=(
            "src/abacus/modules/identity/tokens.py",
            "src/abacus_tools/fakes/identity.py",
        ),
    ),
    Rule(
        id="AUTH-002",
        description="Only the request context reads the Authorization header",
        adr="ADR-020, ADR-029",
        check=_check_authorization_header,
        include=("src/abacus/*",),
        exclude=(
            "src/abacus/modules/identity/routing.py",
            "src/abacus/modules/identity/service.py",
        ),
    ),
    Rule(
        id="AUTHZ-001",
        description="No role comparisons outside identity.authz",
        adr="ADR-020",
        check=_check_role_comparison,
        include=("src/abacus/*",),
        exclude=("src/abacus/modules/identity/authz/*",),
    ),
    Rule(
        id="AUTHZ-002",
        description="Firm roles are read only inside identity",
        adr="ADR-020",
        check=_check_firm_role_read,
        include=("src/abacus/*",),
        exclude=("src/abacus/modules/identity/*",),
    ),
    Rule(
        id="TENANT-002",
        description="Only the request context reads the tenant header",
        adr="ADR-002",
        check=_check_tenant_header,
        include=("src/abacus/*",),
        exclude=(
            "src/abacus/modules/identity/service.py",
            "src/abacus/modules/identity/routing.py",
        ),
    ),
    Rule(
        id="ROUTE-001",
        description="HTTP routes are served only through AbacusRouter",
        adr="ADR-012, ADR-027",
        check=_check_route_bypass,
        include=("src/abacus/*",),
        exclude=("src/abacus/modules/identity/routing.py", "src/abacus/api/app.py"),
    ),
    Rule(
        id="ROUTE-002",
        description="The SELF action is for /v1/me only",
        adr="ADR-027",
        check=_check_self_action,
        include=("src/abacus/*",),
        exclude=(
            "src/abacus/modules/identity/routing.py",
            "src/abacus/modules/identity/routes.py",
            "src/abacus/modules/identity/api.py",
        ),
    ),
    Rule(
        id="CTX-001",
        description="Request contexts are built only from a validated membership",
        adr="ADR-002, ADR-014",
        check=_check_context_construction,
        include=("src/abacus/*",),
        exclude=("src/abacus/modules/identity/service.py",),
    ),
    Rule(
        id="AUTHZ-003",
        description="An engagement's archived state is never a literal",
        adr="ADR-023",
        check=_check_resource_archived,
        include=("src/abacus/*",),
        exclude=("src/abacus/modules/identity/authz/*",),
    ),
    Rule(
        id="LIST-001",
        description="Every repository list method applies visible()",
        adr="ADR-027, ADR-102",
        check=_check_list_visible,
        include=("src/abacus/modules/*/repository.py", "src/abacus/modules/*/repository/*.py"),
    ),
    Rule(
        id="BOUND-002",
        description="Modules depend on each other in one direction only",
        adr="ADR-008",
        check=_check_module_direction,
        include=("src/abacus/modules/*",),
    ),
    Rule(
        id="OWN-001",
        description="A module names only the tables it owns",
        adr="ADR-008, ADR-103",
        check=_check_table_ownership,
        include=("src/abacus/modules/*",),
    ),
    Rule(
        id="STORE-001",
        description="Only kernel.storage uses the AWS SDK and other S3 clients",
        adr="ADR-016, ADR-104",
        check=_check_confined(
            ("boto3", "botocore", "aioboto3", "aiobotocore", "s3fs"), "abacus.kernel.storage"
        ),
        include=("src/abacus/*",),
        exclude=("src/abacus/kernel/storage.py",),
    ),
    Rule(
        id="CRYPTO-001",
        description="Only kernel.crypto uses the cryptography library",
        adr="ADR-035, ADR-104",
        check=_check_confined(
            ("cryptography", "Crypto", "Cryptodome", "nacl"), "abacus.kernel.crypto"
        ),
        include=("src/abacus/*",),
        exclude=("src/abacus/kernel/crypto/*", "src/abacus/modules/identity/tokens.py"),
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
