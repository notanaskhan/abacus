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


_CONTEXT_CLASSES = frozenset({"AuthContext", "SystemContext", "AgentContext"})
_CONTEXT_NAMES = ("ctx", "context", "sys", "system", "agent")


def _context_aliases(src: SourceFile) -> set[str]:
    """Names a context class is reachable by in this file, including `import ... as` aliases."""
    names = set(_CONTEXT_CLASSES)
    for node in ast.walk(src.tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in _CONTEXT_CLASSES and alias.asname:
                    names.add(alias.asname)
    return names


def _check_context_construction(src: SourceFile) -> Iterator[Finding]:
    """Actor contexts come from a validated membership or a proven run (ADR-002, ADR-023), never
    built, copied or re-typed by hand. Import aliases count."""
    aliases = _context_aliases(src)
    for node in ast.walk(src.tree):
        if not isinstance(node, ast.Call):
            continue
        name = _terminal_name(node.func)
        if name in aliases or (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "__new__"
            and _terminal_name(node.func.value) in aliases
        ):
            yield Finding(node.lineno, "contexts are built only from a validated membership")
        elif name in {"replace", "copy", "deepcopy", "__replace__"} and any(
            any(n in (_terminal_name(arg) or "").lower() for n in _CONTEXT_NAMES)
            for arg in node.args
        ):
            yield Finding(node.lineno, "contexts are never copied with changes")
        elif isinstance(node.func, ast.Call) and _terminal_name(node.func.func) == "type":
            yield Finding(node.lineno, "contexts are never built through type()")


# Which issuing function each issuer may call (SYS-001). Anywhere else, none.
_ISSUERS: dict[str, frozenset[str]] = {
    "src/abacus/modules/connections/service.py": frozenset({"system_context_for_run", "_ISSUER"}),
    "src/abacus/modules/agents/service.py": frozenset({"agent_context_for_run"}),
}


def _check_system_issue(src: SourceFile) -> Iterator[Finding]:
    allowed = _ISSUERS.get(src.rel, frozenset())
    for line, name in _names_used(src):
        if name in ("system_context_for_run", "agent_context_for_run", "_ISSUER") and (
            name not in allowed
        ):
            yield Finding(line, "system contexts are issued from a proven run only")


# Everything that starts a workflow, a child workflow or a scheduled workflow (ADR-071).
_STARTS_WORKFLOW = frozenset(
    {
        "start_workflow",
        "execute_workflow",
        "signal_with_start_workflow",
        "start_update_with_start_workflow",
        "start_child_workflow",
        "execute_child_workflow",
        "create_schedule",
        "ScheduleActionStartWorkflow",
        "temporal_client",
    }
)


def _check_dispatch(src: SourceFile) -> Iterator[Finding]:
    """Workflows start only through `kernel.dispatch`, which routes by work class (ADR-071).
    Any reference counts, not only a call: an alias, `getattr` or `partial` is still a start."""
    for node in ast.walk(src.tree):
        name = None
        if isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.alias):
            name = node.asname or node.name.rsplit(".", 1)[-1]
            if node.name in _STARTS_WORKFLOW:
                name = node.name
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "temporalio.client"
        ):
            yield Finding(node.lineno, "the Temporal client is the kernel's (kernel.dispatch)")
            continue
        elif isinstance(node, ast.Constant) and node.value in _STARTS_WORKFLOW:
            yield Finding(node.lineno, "start workflows with kernel.dispatch.dispatch")
            continue
        elif isinstance(node, ast.Call) and any(
            keyword.arg == "task_queue" for keyword in node.keywords
        ):
            yield Finding(node.lineno, "task queues come from the work class (kernel.dispatch)")
            continue
        if name in _STARTS_WORKFLOW:
            yield Finding(
                getattr(node, "lineno", 1), "start workflows with kernel.dispatch.dispatch"
            )


def _check_review_decide(src: SourceFile) -> Iterator[Finding]:
    """ADR-005: agents propose, humans decide. Nothing but the evidence routes reaches the review
    decision (`decide`), whatever it is called through (TASK-019 D4, security review H2)."""
    for node in ast.walk(src.tree):
        name = None
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, ast.alias):
            name = node.name.rsplit(".", 1)[-1]
        elif isinstance(node, ast.Constant) and node.value == "decide":
            name = "decide"
        if name == "decide":
            yield Finding(getattr(node, "lineno", 1), "only a person decides (ADR-005)")


def _check_evaluation_mode(src: SourceFile) -> Iterator[Finding]:
    """Only the evaluation runner pins a tier (`ai_gateway.evaluation`, SPEC-005; TASK-020):
    product code never switches the gateway into evaluation mode."""
    for node in ast.walk(src.tree):
        if isinstance(node, ast.Call) and _terminal_name(node.func) == "evaluation":
            yield Finding(node.lineno, "evaluation mode is the evaluation runner's only")
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "abacus.ai_gateway"
        ):
            for alias in node.names:
                if alias.name == "evaluation":
                    yield Finding(node.lineno, "evaluation mode is the evaluation runner's only")


_MESSAGING = frozenset(
    {"smtplib", "email.mime", "sendgrid", "twilio", "postmarker", "mailgun", "aiosmtplib"}
)


def _check_messaging(src: SourceFile) -> Iterator[Finding]:
    """ADR-065: a message leaves only through `communications.send`, after its scope check.
    Nothing else imports a mail or messaging library or emits `message.ready`."""
    for node in ast.walk(src.tree):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules = [node.module]
        for module in modules:
            if any(module == m or module.startswith(m + ".") for m in _MESSAGING):
                yield Finding(getattr(node, "lineno", 1), "messages leave only through send")
        if isinstance(node, ast.Constant) and node.value == "message.ready":
            yield Finding(getattr(node, "lineno", 1), "only communications emits message.ready")


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
        # Methodology templates are firm-wide (SPEC-008): read after `authorise` on the firm
        # (`methodology.read`) or by a caller authorised on the engagement; no engagement rows.
        ("src/abacus/modules/engagements/repository.py", "list_templates"),
        ("src/abacus/modules/engagements/repository.py", "version_rows"),
        # Knowledge is firm-wide (SPEC-009 §9: `visible()` reduces to the tenant): listed and
        # searched after `authorise` on the firm, embedded by the platform's own workflow.
        ("src/abacus/modules/agents/repository.py", "list_documents"),
        ("src/abacus/modules/agents/repository.py", "chunks_without_vectors"),
        ("src/abacus/modules/agents/repository.py", "nearest_chunks"),
        # The outbound scope checker (SPEC-006): after `authorise(message.send)`, it must see the
        # firm's other clients, entities and accounts to catch them in a draft; never returned.
        ("src/abacus/modules/organisations/repository.py", "names_in_firm"),
        ("src/abacus/modules/ledger/repository.py", "accounts_in_firm"),
        ("src/abacus/modules/ledger/repository.py", "lines_of_snapshots"),
        ("src/abacus/modules/ledger/repository.py", "totals_of_snapshots"),
        ("src/abacus/modules/evidence/repository.py", "snapshots_of_engagement"),
        # The platform reason-code catalogue: no tenant rows, nothing to filter (SPEC-004 Q1).
        ("src/abacus/modules/evidence/repository.py", "reason_codes"),
        ("src/abacus/modules/identity/repository.py", "active_memberships"),
        ("src/abacus/modules/identity/repository.py", "engagement_members_of"),
        ("src/abacus/modules/identity/repository.py", "display_names"),
        ("src/abacus/modules/organisations/repository.py", "names_of"),
        ("src/abacus/modules/ledger/repository.py", "lines_of"),
        ("src/abacus/modules/requests/repository.py", "items_fulfilled_by"),
        # Ethical walls are firm-level, not engagement-scoped (SPEC-002): authz reads a person's
        # own walls; listing every wall needs `wall.list`, authorised by the service first.
        ("src/abacus/modules/identity/repository.py", "walled_clients"),
        ("src/abacus/modules/identity/repository.py", "all_walls"),
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
    # evidence reads which versions fulfil which items, and moves items after a review decision
    # (SPEC-004 Q4, TASK-019); requests never imports evidence.
    "evidence": frozenset({"identity", "engagements", "requests"}),
    "ledger": frozenset(),
    "connections": frozenset(
        {"identity", "engagements", "organisations", "ledger", "evidence", "requests"}
    ),
    # The engagement graph reads the latest snapshot's accounts (SPEC-008, TASK-023 D1).
    "agents": frozenset(
        {"identity", "engagements", "organisations", "evidence", "requests", "ledger"}
    ),
    # The outbound scope checker reads each owner's facts through its API (SPEC-006, TASK-021 D2).
    "communications": frozenset(
        {"identity", "engagements", "organisations", "ledger", "evidence"}
    ),
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


_NETWORK_ROOTS = frozenset(
    {"httpx", "requests", "aiohttp", "urllib", "urllib3", "http", "socket", "ssl", "smtplib"}
    | {"ftplib", "subprocess", "websockets", "grpc", "asyncssh", "paramiko"}
)
_CONNECTOR_METHODS = frozenset(
    {"capabilities", "authorise_url", "exchange_code", "refresh", "pull", "changes_since"}
    | {"fetch_attachment", "health"}
)
_WRITE_VERBS = ("create", "update", "delete", "write", "post", "put", "patch", "upload", "send")


def _check_connector_read_only(src: SourceFile) -> Iterator[Finding]:
    """ADR-040: connectors only read. No write-shaped operations, and no HTTP client until a real
    connector arrives with its own read-only client and egress allowlist."""
    for line, module in _imported_modules(src):
        if module.split(".")[0] in _NETWORK_ROOTS:
            yield Finding(line, f"{module}: connectors get network access only through a client")
    for node in ast.walk(src.tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.lstrip(
            "_"
        ).lower().startswith(_WRITE_VERBS):
            yield Finding(node.lineno, f"{node.name}(): connectors expose read operations only")
        if isinstance(node, ast.ClassDef) and any(
            _terminal_name(base) == "Connector" for base in node.bases
        ):
            for item in node.body:
                if (
                    isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
                    and not item.name.startswith("_")
                    and item.name not in _CONNECTOR_METHODS
                ):
                    yield Finding(
                        item.lineno, f"{item.name}(): a connector offers only the contract's reads"
                    )


_WORKFLOW_IMPORTS = frozenset(
    {"__future__", "asyncio", "collections.abc", "dataclasses", "datetime", "enum", "typing"}
    | {"temporalio", "temporalio.workflow", "temporalio.common", "temporalio.exceptions"}
)
_WORKFLOW_BANNED_NAMES = frozenset(
    {"sandbox_unrestricted", "eval", "exec", "__import__", "import_module", "compile"}
)


def _check_workflow_imports(src: SourceFile) -> Iterator[Finding]:
    """ADR-017: workflows orchestrate only. They import Temporal's workflow-safe API, plain
    standard-library types and their own module's `workflow_types`; never clients, workers,
    repositories, sessions, clocks or anything with I/O, and never step out of the sandbox."""
    own = _own_module(src)
    allowed_own = f"abacus.modules.{own}.workflow_types" if own else None
    for line, module in _imported_modules(src):
        if module in _WORKFLOW_IMPORTS or module == allowed_own:
            continue
        yield Finding(line, f"{module}: workflows import only Temporal and their workflow types")
    for line, name in _names_used(src):
        if name in _WORKFLOW_BANNED_NAMES:
            yield Finding(line, f"{name}: workflows never step outside the sandbox")


# --- tree rules -------------------------------------------------------------------------------


_PROMPT_REF = re.compile(r"[a-z][a-z0-9_.]*@v[0-9]+")


def _aliases_of(src: SourceFile, name: str) -> set[str]:
    """`name` plus every local name it is imported as."""
    names = {name}
    for node in ast.walk(src.tree):
        if isinstance(node, ast.ImportFrom):
            names |= {a.asname for a in node.names if a.name == name and a.asname}
    return names


def _argument(call: ast.Call, position: int, keyword: str) -> ast.expr | None:
    if len(call.args) > position and not any(
        isinstance(a, ast.Starred) for a in call.args[: position + 1]
    ):
        return call.args[position]
    return next((k.value for k in call.keywords if k.arg == keyword), None)


def _check_inline_prompt(src: SourceFile) -> Iterator[Finding]:
    """ADR-019, ADR-057: prompts live in the registry. Outside the gateway, nothing builds a model
    request, writes the instructions layer (the gateway refuses it too), or names a prompt by a
    literal that isn't a registry reference. Import aliases and keyword forms count."""
    requests = _aliases_of(src, "ModelRequest")
    calls = _aliases_of(src, "GatewayCall")
    for call in _calls(src.tree):
        name = _terminal_name(call.func)
        if name in requests:
            yield Finding(call.lineno, "model requests are built only inside ai_gateway")
        elif isinstance(call.func, ast.Attribute) and call.func.attr == "text":
            layer = _argument(call, 0, "layer")
            if isinstance(layer, ast.Constant) and layer.value == "instructions":
                yield Finding(call.lineno, "instructions come from the prompt registry")
        elif name in calls:
            value = _argument(call, 1, "prompt")
            if isinstance(value, (ast.JoinedStr, ast.BinOp)) or (
                isinstance(value, ast.Constant)
                and not (isinstance(value.value, str) and _PROMPT_REF.fullmatch(value.value))
            ):
                yield Finding(call.lineno, "prompt must be a registry reference (id@vN)")


def _agent_denied_actions() -> frozenset[str]:
    """Actions an agent can never be given: anything the matrix doesn't grant agents."""
    from abacus.modules.identity.authz.matrix import RULES  # tooling may import product

    return frozenset(
        a for a, rule in RULES.items() if rule.decisions.get("agent") in (None, "deny")
    )


_NON_AGENT_CONTEXTS = frozenset({"AuthContext", "SystemContext"})


def _check_human_decision(src: SourceFile) -> Iterator[Finding]:
    """ADR-005: a function that authorises an action agents may never take (no `agent` grant in
    the matrix) types its actor `AuthContext` or `SystemContext`, so no agent context reaches it.
    Import aliases and keyword arguments count."""
    denied = _agent_denied_actions()
    names = _aliases_of(src, "authorise")
    for function in ast.walk(src.tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = {
            a.arg: a.annotation
            for a in (*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs)
        }
        for call in ast.walk(function):
            if not (isinstance(call, ast.Call) and _terminal_name(call.func) in names):
                continue
            action = _argument(call, 1, "action")
            if not (isinstance(action, ast.Constant) and action.value in denied):
                continue
            actor = _argument(call, 0, "ctx")
            annotation = params.get(actor.id) if isinstance(actor, ast.Name) else None
            if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
                annotation = ast.parse(annotation.value, mode="eval").body  # "AuthContext"
            if annotation is None or _terminal_name(annotation) not in _NON_AGENT_CONTEXTS:
                yield Finding(
                    call.lineno,
                    f"'{action.value}' is never an agent's: its actor must be a parameter typed "
                    "AuthContext or SystemContext",
                )


_LOG_METHODS = frozenset({"debug", "info", "warning", "error"})
_LOGGERS = frozenset({"_log", "log", "logger"})
_LOGGING_MODULES = ("logging", "structlog")


def _is_log_call(node: ast.AST) -> bool:
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _LOG_METHODS
    ):
        return False
    receiver = node.func.value
    name = (
        receiver.id
        if isinstance(receiver, ast.Name)
        else receiver.attr
        if isinstance(receiver, ast.Attribute)
        else None
    )
    return name in _LOGGERS


def _uses_as_text(value: ast.expr, name: str) -> bool:
    """`value` turns the exception `name` into text or data: anything mentioning it except the
    bare name (the helper logs its class) and `type(name)`."""
    if isinstance(value, ast.Name):
        return False
    if (isinstance(value, ast.Call) and _terminal_name(value.func) == "type") or (
        isinstance(value, ast.Attribute)
        and isinstance(value.value, ast.Call)
        and _terminal_name(value.value.func) == "type"
    ):
        return False
    return any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(value))


def _check_unstructured_logging(src: SourceFile) -> Iterator[Finding]:
    """ADR-022 (best effort, backed by the runtime guard in the helper): product code logs only
    through `abacus.kernel.logging`. No stdlib `logging` or structlog (imports, `__import__`,
    `importlib`); event names are string literals; inside `except ... as e`, a log field never
    turns `e` into text (`str(e)`, `e.args`, `format(e)`, f-strings): pass `e` itself, which is
    logged by class name only (messages can carry client data)."""
    for node in ast.walk(src.tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _LOGGING_MODULES:
                    yield Finding(node.lineno, f"use abacus.kernel.logging, not {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
            if node.module.split(".")[0] in _LOGGING_MODULES:
                yield Finding(node.lineno, f"use abacus.kernel.logging, not {node.module}")
        elif (
            isinstance(node, ast.Call)
            and _terminal_name(node.func) in ("__import__", "import_module")
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and str(node.args[0].value).split(".")[0] in _LOGGING_MODULES
        ):
            yield Finding(node.lineno, "use abacus.kernel.logging, not a dynamic import")
        elif (
            _is_log_call(node)
            and isinstance(node, ast.Call)
            and node.args
            and not (
                isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
            )
        ):
            yield Finding(node.lineno, "log event names are string literals")
    for handler in ast.walk(src.tree):
        if not (isinstance(handler, ast.ExceptHandler) and handler.name is not None):
            continue
        for stmt in handler.body:
            for node in ast.walk(stmt):
                if not (_is_log_call(node) and isinstance(node, ast.Call)):
                    continue
                for keyword in node.keywords:
                    if _uses_as_text(keyword.value, handler.name):
                        yield Finding(
                            node.lineno,
                            f"log field {keyword.arg!r} turns the exception into text; "
                            "pass the exception",
                        )


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
        # kernel/slots.py: the work slot ledger is operational, not domain state, and commits
        # without an audit event (SPEC-003 §14; founder decision 2026-10-07, TASK-018).
        exclude=(
            "src/abacus/kernel/uow/*",
            "src/abacus/kernel/slots.py",
            "src/abacus/ai_gateway/admission.py",  # the provider bucket: the same decision
            "tests/integration/test_tenancy.py",
            "tests/integration/test_uow_session_rollback.py",
            # Calls the slot ledger's functions as the app, one committed call at a time.
            "tests/integration/agent_tests/test_work_slots_db.py",
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
            "tests/integration/test_retrieval.py",
            "tests/integration/test_ledger_schema.py",
            "tests/integration/test_retrieval_workflow.py",
            "tests/integration/test_retrieval_api.py",
            "tests/integration/agent_tests/support.py",
            "tests/integration/agent_tests/test_work_slots_db.py",  # the ledger, as the app
            "tests/integration/test_seed_dev.py",
            # Records replay fixtures against throwaway containers (seeds as the superuser).
            "src/abacus_tools/workflows/record_retrieval.py",
            "src/abacus_tools/stack.py",  # the recorders' and evals' stack (connect_db)
            # Seeds the local stack as its superuser (local only; TASK-012).
            "src/abacus_tools/local/seed_dev.py",
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
        exclude=(
            "tests/*",
            "src/abacus_tools/quality/banned_patterns.py",
            "src/abacus_tools/workflows/record_retrieval.py",
            "src/abacus_tools/stack.py",  # the throwaway stack the recorders and evals share
        ),
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
            "src/abacus/kernel/slots.py",  # see UOW-001
            "src/abacus/ai_gateway/admission.py",  # see UOW-001
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
            "tests/integration/agent_tests/test_work_slots_db.py",  # calls the ledger functions
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
            "src/abacus_tools/workflows/record_retrieval.py",
            "src/abacus_tools/stack.py",  # the throwaway stack the recorders and evals share
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
        exclude=(
            "src/abacus/modules/identity/service.py",
            "src/abacus/modules/identity/context.py",
        ),
    ),
    Rule(
        id="SYS-001",
        description="Run contexts are issued only by their run loaders (connections, agents)",
        adr="ADR-023",
        check=_check_system_issue,
        include=("src/abacus/*",),
        exclude=(
            "src/abacus/modules/identity/context.py",
            "src/abacus/modules/identity/api.py",
        ),
    ),
    Rule(
        id="DISPATCH-001",
        description="Workflows start only through kernel.dispatch, on their work class's queue",
        adr="ADR-071",
        check=_check_dispatch,
        include=("src/abacus/*",),
        exclude=(
            "src/abacus/kernel/dispatch.py",
            "src/abacus/kernel/temporal.py",
            "src/abacus/worker/__main__.py",
        ),
    ),
    Rule(
        id="REVIEW-001",
        description="Only the evidence routes reach the review decision",
        adr="ADR-005",
        check=_check_review_decide,
        # An allowlist (TASK-019 security review H2): any other file naming `decide` fails.
        include=("src/abacus/*",),
        exclude=(
            "src/abacus/modules/evidence/service.py",
            "src/abacus/modules/evidence/routes.py",
        ),
    ),
    Rule(
        id="EVAL-001",
        description="Only the evaluation runner switches the gateway into evaluation mode",
        adr="ADR-019",
        check=_check_evaluation_mode,
        include=("src/abacus/*", "src/abacus_tools/*"),
        exclude=("src/abacus/ai_gateway/__init__.py", "src/abacus_tools/evals/*"),
    ),
    Rule(
        id="COMM-001",
        description="Messages leave only through communications.send, after the scope check",
        adr="ADR-065",
        check=_check_messaging,
        include=("src/abacus/*",),
        exclude=("src/abacus/modules/communications/*",),
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
        id="CONN-001",
        description="Connectors are read-only",
        adr="ADR-040",
        check=_check_connector_read_only,
        include=("src/abacus/modules/connections/*",),
    ),
    Rule(
        id="WF-001",
        description="Workflow modules import only Temporal and their workflow types",
        adr="ADR-017, ADR-090",
        check=_check_workflow_imports,
        include=("src/abacus/modules/*/workflows.py", "src/abacus/modules/*/workflows/*"),
    ),
    Rule(
        id="PROMPT-001",
        description="No inline prompts: model requests and instructions come from the registry",
        adr="ADR-019, ADR-057",
        check=_check_inline_prompt,
        include=("src/abacus/*",),
        exclude=("src/abacus/ai_gateway/*",),
    ),
    Rule(
        id="AGENT-001",
        description="Actions agents may never take are authorised for typed non-agent actors only",
        adr="ADR-005, ADR-025",
        check=_check_human_decision,
        include=("src/abacus/modules/*",),
    ),
    Rule(
        id="LOG-001",
        description="Log only through abacus.kernel.logging; exceptions as values, never as text",
        adr="ADR-022, ADR-031",
        check=_check_unstructured_logging,
        include=("src/abacus/*",),
        exclude=("src/abacus/kernel/logging.py",),
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
