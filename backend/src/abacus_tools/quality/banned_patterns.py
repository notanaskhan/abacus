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
from dataclasses import dataclass, replace
from fnmatch import fnmatch
from pathlib import Path
from typing import Final

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


_FLAG_READERS = frozenset({"flag", "flag_enabled", "flag_variant"})


def _check_flags(src: SourceFile) -> Iterator[Finding]:
    """SPEC-011 AC-5: flags are declared only in the registry (constructed in the generated
    `kernel/_flags.py`) and read by their generated constant, never by a computed name."""
    for call in _calls(src.tree):
        name = _terminal_name(call.func)
        if name == "Flag":
            yield Finding(call.lineno, "Flag(...) outside the generated kernel/_flags.py")
        # A generated constant, or a registry entry (`FLAGS.get(...)`, already a `Flag`); never a
        # name written in the call (a string or an f-string).
        elif (
            name in _FLAG_READERS
            and len(call.args) >= 2
            and isinstance(call.args[1], (ast.Constant, ast.JoinedStr))
        ):
            yield Finding(call.lineno, f"{name}() reads a flag object, not a name")


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


def _check_tool_connection_tls(src: SourceFile) -> Iterator[Finding]:
    """TLS-001 (G-09; P-08-T21 security review): a tooling connection names its TLS decision."""
    for call in _calls(src.tree):
        func = call.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in {"connect", "create_pool"}
            and _terminal_name(func.value) == "asyncpg"
            and not any(k.arg == "ssl" for k in call.keywords)
        ):
            yield Finding(
                call.lineno,
                f"asyncpg.{func.attr}() without ssl=; use abacus_tools.db_connect.connect",
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
        if target == "abacus.modules.MODULES":  # P-39 (F-03-T07): the list of module names
            return
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


_FLAG_KEYS = frozenset({"x-tri", "x-phi", "x-pii-kind"})


def _check_classification_flag_keys(src: SourceFile) -> Iterator[Finding]:
    """CLS-001 (ADR-167): the flag keys are written by `classified()` and read by the path
    helpers in `kernel/classification.py`; anywhere else they mean a hand-set or hand-read flag."""
    for node in ast.walk(src.tree):
        if isinstance(node, ast.Constant) and node.value in _FLAG_KEYS:
            yield Finding(
                node.lineno,
                f"{node.value!r}: set flags with classified(tri=, phi=, pii_kind=) and read them "
                "with tri_paths, phi_paths or pii_paths",
            )


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
# A strict xfail may cite the task that holds the defect instead (AGENTS rule 13): it fails the
# suite the moment the defect is fixed, so the task cannot go stale silently. Skips and the
# imperative `pytest.xfail()` (never strict) still need an issue.
_TASK_REF = re.compile(r"\bTASK-\d{3,}\b")
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


def _strict_xfail(call: ast.Call, kind: str) -> bool:
    """A `pytest.mark.xfail(...)` that stays strict (`xfail_strict = true` in pyproject, unless the
    mark says `strict=False`)."""
    if kind != "mark.xfail":
        return False
    for kw in call.keywords:
        if kw.arg == "strict":
            return not (isinstance(kw.value, ast.Constant) and kw.value.value is False)
    return True


def _linked(call: ast.Call, kind: str) -> bool:
    reason = _skip_reason(call, kind)
    if _ISSUE_REF.search(reason):
        return True
    return _strict_xfail(call, kind) and bool(_TASK_REF.search(reason))


def _check_unlinked_skip(src: SourceFile) -> Iterator[Finding]:
    yield from _pytest_aliases(src)
    called: set[int] = set()
    for call in _calls(src.tree):
        kind = _skip_kind(call.func)
        if kind is None:
            continue
        called.add(id(call.func))
        if not _linked(call, kind):
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


# F-04-T17 (CLOCK-001): the wall clock is read only by kernel.clock, so a demo clock, a frozen
# replay and the tests can fix business time, and security windows use `system_now` (F-04.4).
_CLOCK_CALLS = frozenset(
    {("datetime", "now"), ("datetime", "utcnow"), ("datetime", "today"), ("date", "today")}
    | {("time", "time")}
)


def _check_clock(src: SourceFile) -> Iterator[Finding]:
    for node in ast.walk(src.tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        owner = node.func.value
        name = owner.attr if isinstance(owner, ast.Attribute) else getattr(owner, "id", None)
        if (name, node.func.attr) in _CLOCK_CALLS:
            yield Finding(
                node.lineno,
                "read the time through abacus.kernel.clock (now, today or system_now)",
            )


def _check_policy_context(src: SourceFile) -> Iterator[Finding]:
    """Q-02 AC-16: the dormant policy actor is the kernel's alone. A `TenantContext` whose actor
    kind is "policy" (the second argument, or `actor_kind=`) anywhere else is refused."""
    for node in ast.walk(src.tree):
        if not isinstance(node, ast.Call) or _terminal_name(node.func) != "TenantContext":
            continue
        kinds = [node.args[1]] if len(node.args) > 1 else []
        kinds += [k.value for k in node.keywords if k.arg == "actor_kind"]
        if any(isinstance(k, ast.Constant) and k.value == "policy" for k in kinds):
            yield Finding(node.lineno, "only abacus.kernel acts as the policy actor (Q-02 AC-16)")


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


# The protected exception list (ADR-152, P-45): the only unauthenticated paths. `create_app()`
# registers exactly `public_routes.PUBLIC_ROUTES`, and every path there must be listed here, so a
# new public route is a deliberate edit to this protected file, with an ADR behind it. P-08 adds
# `/v1/portal/branding` through its own ADR. ADR-165 adds the staff session BFF's three
# pre-session routes, which stay inside `AbacusRouter` under the `PRE_SESSION` marker.
PUBLIC_ROUTE_EXCEPTIONS = frozenset(
    {"/healthz", "/readyz", "/v1/auth/sign-in", "/v1/auth/callback", "/v1/auth/refresh"}
    # P-08-T05 (ADR-163 §6): portal branding, Public fields only, inside `AbacusRouter` under the
    # `PORTAL_PUBLIC` marker.
    | {"/v1/portal/branding", "/v1/portal/branding/logo"}
    # P-08-T10 (ADR-168): the portal's sign-in by emailed code, under `PRE_SESSION`.
    | {"/v1/portal/auth/start", "/v1/portal/auth/verify", "/v1/portal/auth/resend"}
    | {"/v1/portal/auth/refresh"}
    # P-08-T17 (ADR-168): the second step and its first-time setup, under `PRE_SESSION`.
    | {"/v1/portal/auth/mfa", "/v1/portal/auth/mfa/setup", "/v1/portal/auth/mfa/setup/verify"}
    # P-08-T18 (DEC-139): the invitation preview, under `PRE_SESSION`.
    | {"/v1/invitations/preview"}
    # P-08-T21 (DEC-139): a recipient's link renewal, always 202, under `PRE_SESSION`.
    | {"/v1/portal/links/renew"}
)
_PUBLIC_ROUTES_FILE = "src/abacus/api/public_routes.py"
_APP_FILE = "src/abacus/api/app.py"
_APP_ADD_METHODS = frozenset(
    {"add_api_route", "add_route", "add_websocket_route", "add_api_websocket_route", "websocket"}
    | {"mount"}
)
_APP_VERB_METHODS = frozenset(
    {"get", "post", "put", "patch", "delete", "head", "options", "route", "api_route"}
)


def _check_public_route_list(src: SourceFile) -> Iterator[Finding]:
    """`PUBLIC_ROUTES` is a literal dict whose keys are all on the protected exception list."""
    for node in src.tree.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        if not any(isinstance(t, ast.Name) and t.id == "PUBLIC_ROUTES" for t in targets):
            continue
        if not isinstance(value, ast.Dict):
            yield Finding(node.lineno, "PUBLIC_ROUTES must be a literal dict of path to handler")
            return
        for key in value.keys:
            if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                yield Finding(node.lineno, "PUBLIC_ROUTES keys must be string literals")
            elif key.value not in PUBLIC_ROUTE_EXCEPTIONS:
                yield Finding(
                    key.lineno,
                    f"{key.value!r} is not on the public-route exception list (ADR-152): "
                    "propose an ADR and extend PUBLIC_ROUTE_EXCEPTIONS",
                )
        return
    yield Finding(1, "public_routes.py must define PUBLIC_ROUTES")


def _check_app_registers_no_path(src: SourceFile) -> Iterator[Finding]:
    """app.py may build the app, include routers and add middleware, but never register a path
    of its own: unauthenticated routes come only from PUBLIC_ROUTES."""
    for node in ast.walk(src.tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and (
                node.func.attr in _APP_ADD_METHODS
                or (
                    node.func.attr
                    in _APP_VERB_METHODS  # `app.get("/x")`, not `scope.get("route")`
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "app"
                )
            )
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            yield Finding(
                node.lineno,
                f"{node.func.attr}: register a path only through public_routes.PUBLIC_ROUTES",
            )


def _check_route_bypass(src: SourceFile) -> Iterator[Finding]:
    if src.rel == _PUBLIC_ROUTES_FILE:
        yield from _check_public_route_list(src)
    elif src.rel == _APP_FILE:
        yield from _check_app_registers_no_path(src)
        return  # app.py builds the app, so the class and method bans below do not apply to it

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
    # R-01-T09 (DEC-323): the portal drop sort acts for the dropper on one drop, proven by the
    # drop's own inbox row read under the tenant's row-level security.
    "src/abacus/modules/evidence/drops.py": frozenset({"system_context_for_run"}),
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


# P-04-T25 (DEC-604, narrowed by the security review, DEC-609): outside the evidence service and
# routes, only these top-level scopes may name `decide`: the module's imports (`<import>`), its
# `__all__`, or the named functions; anywhere else in the same file still fails.
REVIEW_DECIDE_EXEMPT: dict[str, frozenset[str]] = {
    "src/abacus/modules/evidence/api.py": frozenset({"<import>", "__all__"}),
    "src/abacus/modules/agents/proposal_adapters.py": frozenset(
        {"<import>", "approve_typed", "reject_typed"}
    ),
}


def _top_scope(node: ast.stmt) -> str | None:
    if isinstance(node, ast.Import | ast.ImportFrom):
        return "<import>"
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return node.name
    if isinstance(node, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
    ):
        return "__all__"
    return None


def _check_review_decide(src: SourceFile) -> Iterator[Finding]:
    """ADR-005: agents propose, humans decide. Nothing but the evidence routes reaches the review
    decision (`decide`), whatever it is called through (TASK-019 D4, security review H2)."""
    allowed = REVIEW_DECIDE_EXEMPT.get(src.rel, frozenset[str]())
    for top in src.tree.body:
        if _top_scope(top) in allowed:
            continue
        yield from _decide_named(top)


def _decide_named(tree: ast.AST) -> Iterator[Finding]:
    for node in ast.walk(tree):
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


def _check_named(name: str, message: str) -> Callable[[SourceFile], Iterator[Finding]]:
    """A call-site allowlist (ADR-005, INV-1): any file naming `name` (a name, an attribute, an
    import or the string itself) fails, except the files excluded on the rule."""

    def check(src: SourceFile) -> Iterator[Finding]:
        for node in ast.walk(src.tree):
            found = None
            if isinstance(node, ast.Name):
                found = node.id
            elif isinstance(node, ast.Attribute):
                found = node.attr
            elif isinstance(node, ast.alias):
                found = (node.asname or node.name).rsplit(".", 1)[-1]
                if node.name.rsplit(".", 1)[-1] == name:
                    found = name
            elif isinstance(node, ast.Constant) and node.value == name:
                found = name
            if found == name:
                yield Finding(getattr(node, "lineno", 1), message)

    return check


# PROPOSAL-001 (P-04-T24, T25; re-review L4): the top-level scopes that may name a proposal's
# decision functions, file by file, as `REVIEW_DECIDE_EXEMPT` does for REVIEW-001.
PROPOSAL_EXEMPT: dict[str, frozenset[str]] = {
    "src/abacus/modules/agents/proposals.py": frozenset({"__all__"}),
    "src/abacus/modules/agents/proposal_adapters.py": frozenset({"__all__"}),
    "src/abacus/modules/agents/contract.py": frozenset(
        {
            "<import>",
            "proposal_approve_route",
            "proposal_reject_route",
            "proposal_route_to_route",
            "suggestion_adopt_route",
            "suggestion_dismiss_route",
        }
    ),
}


def _check_named_scoped(
    names: tuple[str, ...], message: str, exempt: dict[str, frozenset[str]]
) -> Callable[[SourceFile], Iterator[Finding]]:
    """`_check_named_any`, except in the named top-level scopes of the named files."""
    inner = _check_named_any(names, message)

    def check(src: SourceFile) -> Iterator[Finding]:
        allowed = exempt.get(src.rel, frozenset[str]())
        for top in src.tree.body:
            if _top_scope(top) in allowed:
                continue
            yield from inner(replace(src, tree=ast.Module(body=[top], type_ignores=[])))

    return check


def _check_named_any(
    names: tuple[str, ...], message: str
) -> Callable[[SourceFile], Iterator[Finding]]:
    """`_check_named` for several names under one rule (SIGNOFF-001)."""
    checks = [_check_named(name, message) for name in names]

    def check(src: SourceFile) -> Iterator[Finding]:
        for one in checks:
            yield from one(src)

    return check


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


def _check_system_send(src: SourceFile) -> Iterator[Finding]:
    """R-01-T24 security review M2, L-b (DEC-568, DEC-588): the system's scheduled Reminder is
    built only by communications' scheduled-reminder service, which checks the policy, the flag,
    the key and the cadence itself. Outside communications the name `SystemSendContext` appears
    nowhere: not as a name or an attribute (an alias or `module.SystemSendContext`), not as a
    string (`getattr(module, "SystemSendContext")`), not imported."""
    name = "SystemSendContext"
    for node in ast.walk(src.tree):
        named = (isinstance(node, ast.Name) and node.id == name) or (
            isinstance(node, ast.Attribute) and node.attr == name
        )
        if named:
            yield Finding(getattr(node, "lineno", 1), "only communications uses the context")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and name in node.value:
            yield Finding(node.lineno, "only communications names the scheduled send context")
        elif isinstance(node, ast.ImportFrom) and any(a.name == name for a in node.names):
            yield Finding(node.lineno, "only communications imports the scheduled send context")


_DYNAMIC_IMPORTS: Final = frozenset({"import_module", "__import__"})


def _check_dynamic_module_import(src: SourceFile) -> Iterator[Finding]:
    """R-01-T24 security review L-b (DEC-588): a module never reaches another module's internals
    by a dynamic import (`importlib.import_module("abacus.modules.x.y")`, `__import__`), which
    the import contracts cannot see. The app and the worker load each module's `api` this way and
    sit outside `modules/`."""
    for node in ast.walk(src.tree):
        if not isinstance(node, ast.Call) or _terminal_name(node.func) not in _DYNAMIC_IMPORTS:
            continue
        first = node.args[0] if node.args else None
        if first is None:
            continue
        text = ""
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            text = first.value
        elif isinstance(first, ast.JoinedStr):
            text = "".join(
                v.value
                for v in first.values
                if isinstance(v, ast.Constant) and isinstance(v.value, str)
            )
        else:
            yield Finding(node.lineno, "a dynamic import names its module literally")
            continue
        if text.startswith("abacus"):
            yield Finding(node.lineno, "no dynamic import of an abacus module inside modules/")


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
# ADR-145's scope kinds (identity.authz.SCOPE_KINDS).
_SCOPE_KINDS = frozenset({"engagement", "work_item", "client", "client_entity", "portal_scope"})
# Repository functions that return many rows without `visible()`, each reviewed: they serve
# lookups for rows the caller has already authorised, or sign-in before a tenant exists.
LIST_EXEMPT = frozenset(
    {
        # R-01-T07 (DEC-333): the portal read model's lookups by id for rows the caller already
        # read through `visible_items` and authorised `portal_documents.read` on: a binder's
        # requests' live fulfilments, the contacts its requests are delegated to (only their
        # organisations are named), and those versions' accept history and latest checks.
        ("src/abacus/modules/requests/repository.py", "live_links"),
        ("src/abacus/modules/requests/repository.py", "binder_delegated_contacts"),
        # R-01-T13 (DEC-387): the room's requests, keyed by the caller's own `request_item`
        # grants and each authorised through `delegated_only` before anything of it is read.
        ("src/abacus/modules/requests/repository.py", "delegated_rows"),
        # R-01-T13 (DEC-387): one request's open delegations' grants and their active holders,
        # the facts `delegated_only` is judged on (keyed by one request and its grant ids).
        ("src/abacus/modules/requests/repository.py", "open_delegation_grants"),
        ("src/abacus/modules/requests/repository.py", "live_item_engagements"),
        ("src/abacus/modules/identity/repository.py", "delegate_grant_holders"),
        ("src/abacus/modules/identity/repository.py", "delegate_holders"),
        # A-02-T23: an entity's Owner grants, for the firm's reconnect request email (recipients
        # are then held to `recipient_relations`; the asker authorised on the engagement first).
        ("src/abacus/modules/identity/repository.py", "owner_holders"),
        ("src/abacus/modules/evidence/repository.py", "ever_accepted"),
        ("src/abacus/modules/evidence/repository.py", "client_problem_codes"),
        # P-07-T25 (DEC-302): one contact's delegations, read for CLI-04 after the contact's
        # client passed `visible_clients(contact.read)`, and ended in the revoking unit of work
        # after `authorise(client_access.revoke)`; keyed by contact or grant, not listed.
        ("src/abacus/modules/requests/repository.py", "open_delegations"),
        ("src/abacus/modules/requests/repository.py", "end_delegations"),
        # P-07-T25: the roles of contacts already read through `visible_clients(contact.read)`.
        ("src/abacus/modules/organisations/repository.py", "contact_roles_of"),
        # P-07-T25 (DEC-300): one contact's grants and invitations, or an invitation's own
        # grants, read after the contact's client passed `visible_clients(contact.read)` or in
        # the acceptance that holds the invitation's row; the addresses a CLI-04 page shows that
        # are locked; one person's sessions ended in the revoking unit of work.
        ("src/abacus/modules/identity/repository.py", "contact_grants"),
        ("src/abacus/modules/identity/repository.py", "grants_by_id"),
        ("src/abacus/modules/identity/repository.py", "contact_invitations"),
        ("src/abacus/modules/identity/repository.py", "locked_emails"),
        ("src/abacus/modules/identity/repository.py", "end_portal_access"),
        # SPEC-318 (TASK-461): one run's results and their decisions, read after
        # `authorise(agent_run.read)` on the run's engagement.
        ("src/abacus/modules/agents/repository.py", "screening_results_of_run"),
        ("src/abacus/modules/agents/repository.py", "run_writes"),  # TASK-5000
        ("src/abacus/modules/agents/repository.py", "run_activity"),  # TASK-5001
        ("src/abacus/modules/agents/repository.py", "run_outputs"),  # Q-02-T41 (TASK-1287)
        # P-06-T20 (DEC-324): the screening aggregate's inputs, keyed by one request item's live
        # versions, read by the system composer or after `authorise(upload_review.read)` on the
        # item's engagement; the citations its flags carry, keyed by those reviews.
        ("src/abacus/modules/agents/repository.py", "review_runs_of_versions"),
        ("src/abacus/modules/agents/repository.py", "shown_flags_of_reviews"),
        ("src/abacus/modules/agents/repository.py", "version_results_of"),
        ("src/abacus/modules/agents/repository.py", "items_screened_with"),
        ("src/abacus/modules/evidence/repository.py", "verified_citations_of"),
        # P-04-T24 (C4, INV-2): citations by id, for a caller authorised on the citing
        # engagement (a proposal's rows, re-verified at approval; SHL-10's evidence list).
        ("src/abacus/modules/evidence/repository.py", "supported_citations_among"),
        ("src/abacus/modules/evidence/repository.py", "citation_versions_among"),
        ("src/abacus/modules/evidence/repository.py", "decisions_for_screenings"),
        # SPEC-035 Q3 (TASK-074): a template version's drafts are firm-wide, read after
        # `authorise(template_guidance.read)` on the firm; no engagement rows.
        ("src/abacus/modules/agents/repository.py", "template_drafts"),
        # SPEC-037 (TASK-083): one selection's entries, after `authorise(procedure.read)` on its
        # engagement.
        ("src/abacus/modules/fieldwork/repository.py", "selected_items"),
        ("src/abacus/modules/fieldwork/repository.py", "rule_counts"),
        # SPEC-037 (TASK-084): one procedure's results, support requests, versions and
        # signatures, after `authorise` on its engagement.
        ("src/abacus/modules/fieldwork/repository.py", "all_items"),
        ("src/abacus/modules/fieldwork/repository.py", "newest_results"),
        ("src/abacus/modules/fieldwork/repository.py", "results_by_id"),
        ("src/abacus/modules/fieldwork/repository.py", "support_requested"),
        ("src/abacus/modules/fieldwork/repository.py", "signoffs_of"),  # SPEC-040 (TASK-100)
        # SPEC-043 (TASK-107): misstatements of findings already read through `visible()`.
        ("src/abacus/modules/fieldwork/repository.py", "newest_misstatements"),
        # SPEC-300 (TASK-301): materiality versions and decisions after `authorise`; versions
        # and approvals of risks already read through `visible()`.
        ("src/abacus/modules/fieldwork/repository.py", "materiality_versions"),
        ("src/abacus/modules/fieldwork/repository.py", "materiality_decisions"),
        ("src/abacus/modules/fieldwork/repository.py", "newest_risk_versions"),
        ("src/abacus/modules/fieldwork/repository.py", "risk_approvals"),
        # SPEC-301 (TASK-302): records of findings and entries already read through `visible()`.
        ("src/abacus/modules/fieldwork/repository.py", "severities_of"),
        ("src/abacus/modules/fieldwork/repository.py", "communications_of"),
        ("src/abacus/modules/fieldwork/repository.py", "adjustment_lines_of"),
        ("src/abacus/modules/fieldwork/repository.py", "adjustment_events_of"),
        # SPEC-041 (TASK-103): one procedure's review notes and their events, after `authorise`.
        ("src/abacus/modules/fieldwork/repository.py", "notes_of"),
        ("src/abacus/modules/fieldwork/repository.py", "note_events_of"),
        # TASK-104: one engagement's waiting follow-ups, for the agent's drafting.
        ("src/abacus/modules/agents/repository.py", "drafted_item_ids"),
        # TASK-102: the person's own engagement memberships ("waiting on you"), own rows only.
        ("src/abacus/modules/identity/repository.py", "my_engagement_roles"),
        # F-03-T24: the firm's policy overrides and settings, read by `authorise` itself (the
        # rules visible() would apply), firm-wide, no engagement rows.
        ("src/abacus/modules/identity/repository.py", "firm_policy"),
        # F-03-T26: the person's own client access grants, read by `portal_scopes` and the
        # `scope_only` condition (the rules visible() would apply); own rows only.
        ("src/abacus/modules/identity/repository.py", "active_grants"),
        # SPEC-040: an insert that returns the new rows' ids, not a list read.
        ("src/abacus/modules/fieldwork/repository.py", "insert_signoffs"),
        ("src/abacus/modules/fieldwork/repository.py", "workpaper_versions"),
        ("src/abacus/modules/fieldwork/repository.py", "signatures_of"),
        ("src/abacus/modules/fieldwork/repository.py", "support_request_ids"),  # TASK-085
        # Methodology templates are firm-wide (SPEC-008): read after `authorise` on the firm
        # (`methodology.read`) or by a caller authorised on the engagement; no engagement rows.
        ("src/abacus/modules/methodology/repository.py", "list_templates"),  # K-01-T02: moved
        # K-01-T05: the previous version's step keys, inside an authorised import's own unit of
        # work (`methodology.manage` on the firm); firm-wide rows, no engagement.
        ("src/abacus/modules/methodology/repository.py", "_prior_keys"),
        # SPEC-025 (TASK-043): the client picker, firm-level after `authorise(client.read)`; the
        # service drops clients the person is walled off from.
        ("src/abacus/modules/organisations/repository.py", "clients_matching"),
        # F-03-T25: one client's contacts, inside `client_record` for a caller that authorised
        # reading that client; no engagement rows.
        ("src/abacus/modules/organisations/repository.py", "contacts_of"),
        # SPEC-025 (TASK-044): one engagement's confirmations after `authorise(setup.read)`.
        ("src/abacus/modules/engagements/repository.py", "confirmations_of"),
        # SPEC-027 (TASK-050): the engagement agent's own reads, for the engagement it serves (its
        # pause replays), and the firm's open engagements when the firm resumes every agent.
        ("src/abacus/modules/agents/repository.py", "screenings_skipped_while_paused"),
        ("src/abacus/modules/engagements/repository.py", "open_engagement_ids"),
        # SPEC-027 (TASK-051): the items the engagement agent reminds about, and its own
        # reminder records (caps and drafts).
        ("src/abacus/modules/requests/repository.py", "overdue_items"),
        ("src/abacus/modules/agents/repository.py", "follow_up_history"),
        # SPEC-033 (TASK-066 D1): the matcher's shown picks for inbox files evidence's listing
        # already authorised (request IDs only); client roles can't read matches themselves.
        ("src/abacus/modules/agents/repository.py", "shown_picks"),
        ("src/abacus/modules/agents/repository.py", "drafted_follow_ups"),
        # P-06-T14: follow-ups v2's own records, read for requests the caller just read through
        # `visible()` (identifiers only), and those binders' recipient histories.
        ("src/abacus/modules/agents/repository.py", "waiting_pairs"),
        ("src/abacus/modules/agents/repository.py", "follow_up_item_rows"),
        # TASK-1252: one screening return's files, for a caller that authorised the follow-up.
        ("src/abacus/modules/agents/repository.py", "follow_up_return_rows"),
        ("src/abacus/modules/requests/repository.py", "binders_recipient_rows"),
        # Recipients' addresses and the engagement's client admins (one engagement, read for a
        # reminder after `follow_up.send` or by the agent); the items whose due date was set.
        ("src/abacus/modules/identity/repository.py", "emails_of"),
        ("src/abacus/modules/identity/repository.py", "client_admin_ids"),
        ("src/abacus/modules/requests/repository.py", "set_due_dates"),
        # P-08-T17: identifiers for the MFA floor and for who a new designation affects, read by
        # the system in the tenant's session; never listed to anyone.
        ("src/abacus/modules/identity/repository.py", "grant_contact_ids"),
        ("src/abacus/modules/identity/repository.py", "contact_user_ids"),
        # SPEC-019 Q4: the firm's staff for the wall picker, after `authorise(wall.create)`.
        ("src/abacus/modules/identity/repository.py", "active_staff_ids"),
        # SPEC-017: team candidates (after `authorise(engagement.member_add)`; walls applied in the
        # query) and the removed member's assignments, released inside the removal.
        ("src/abacus/modules/identity/repository.py", "team_candidate_ids"),
        ("src/abacus/modules/evidence/repository.py", "release_assignments_of"),
        # SPEC-015: one engagement's contacts, read after `authorise(client_contact.read)` on it.
        ("src/abacus/modules/identity/repository.py", "client_contacts"),
        # SPEC-024 (TASK-041): the firm's staff and pending staff invitations, firm-level, read
        # after `authorise(firm.manage_users)`.
        ("src/abacus/modules/identity/repository.py", "staff_memberships"),
        ("src/abacus/modules/identity/repository.py", "pending_staff_invitations"),
        # SPEC-014: authorisation's own lookup (the caller's roles; visible() can't apply to it).
        ("src/abacus/modules/identity/repository.py", "engagement_roles_in_firm"),
        # SPEC-013: notification recipients (the platform resolving who to tell, never returned
        # to a caller) and the idempotent insert's RETURNING.
        ("src/abacus/modules/identity/repository.py", "active_firm_admins"),
        # Q-02-T33: the incident register's recipients (QI and partners), same footing.
        ("src/abacus/modules/identity/repository.py", "active_security_admins"),
        ("src/abacus/modules/identity/repository.py", "active_partner_members"),
        # P-07-T47 (DEC-544): the quality owners an EQR gate is assigned to (system, firm-wide).
        ("src/abacus/modules/identity/repository.py", "active_quality_partners"),
        ("src/abacus/modules/notifications/repository.py", "insert_notifications"),
        # Support sessions are firm-level records, listed after `authorise(support_session.read)`.
        ("src/abacus/modules/identity/repository.py", "list_support_sessions"),
        ("src/abacus/modules/methodology/repository.py", "version_rows"),  # K-01-T02: moved
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
        # P-07-T30: the same team with ENG-05's extras, for a caller that authorised the read.
        ("src/abacus/modules/identity/repository.py", "member_details_of"),
        # P-07-T30 security review: one person's roles ever held, for EQR cooling-off.
        ("src/abacus/modules/identity/repository.py", "roles_ever_held"),
        ("src/abacus/modules/identity/repository.py", "display_names"),
        # SPEC-024 (TASK-041): names and emails for staff the caller already read under RLS.
        ("src/abacus/modules/identity/repository.py", "user_contacts"),
        ("src/abacus/modules/organisations/repository.py", "names_of"),
        ("src/abacus/modules/ledger/repository.py", "lines_of"),
        # SPEC-034 (TASK-069): a GL snapshot's reconciliation and entries, read for a caller
        # authorised on its engagement (as a trial balance snapshot's lines are).
        ("src/abacus/modules/ledger/repository.py", "gl_balances_of"),
        ("src/abacus/modules/ledger/repository.py", "gl_entries_of"),
        ("src/abacus/modules/connections/repository.py", "waiting_gl_imports"),
        # A-02-T16 (DEC-514): facts about connections the caller already authorised
        # `connection.read` or `.retry` on (an engagement of their entity), keyed by those ids.
        ("src/abacus/modules/connections/repository.py", "live_connections_of"),
        ("src/abacus/modules/connections/repository.py", "last_failures"),
        ("src/abacus/modules/connections/repository.py", "recent_runs"),
        ("src/abacus/modules/connections/repository.py", "open_reconnect_requests"),
        ("src/abacus/modules/connections/repository.py", "fulfil_reconnect_requests"),
        # A-02-T16 (DEC-514): an entity's engagements as candidates `authorise` judges one by one
        # (`connections.authorised_engagement`); never returned as a list.
        ("src/abacus/modules/engagements/repository.py", "entity_engagement_ids"),
        ("src/abacus/modules/requests/repository.py", "items_fulfilled_by"),
        # P-06-T07: one binder's sections, requests and recipient history, read after
        # `authorise(binder.*)` on that binder; and the platform's close rule on a C1 fact.
        ("src/abacus/modules/requests/repository.py", "binder_categories"),
        ("src/abacus/modules/requests/repository.py", "binder_items"),
        ("src/abacus/modules/requests/repository.py", "recipient_rows"),
        ("src/abacus/modules/requests/repository.py", "open_binders"),
        # SPEC-020: one request item's versions and its uploads, read after `authorise` on that
        # item with its client facts (`evidence.upload` / `evidence.read`).
        ("src/abacus/modules/requests/repository.py", "fulfilling_versions"),
        # P-06-T19: one withdrawn version's own fulfilments, voided after `authorise` of
        # `evidence.withdraw` on its request item.
        ("src/abacus/modules/requests/repository.py", "void_fulfilments"),
        # P-06-T10: live upload hints for a binder's requests, after `check_action` on it.
        ("src/abacus/modules/requests/repository.py", "live_upload_intents"),
        ("src/abacus/modules/evidence/repository.py", "uploaded_versions"),
        # SPEC-021: one item's versions with their decisions, after `authorise(evidence.read)`.
        ("src/abacus/modules/evidence/repository.py", "item_versions_with_decisions"),
        # SPEC-023: an engagement's waiting inbox files, after authorising on the engagement; the
        # service narrows them by role (staff, client admin, the contributor's own).
        ("src/abacus/modules/evidence/repository.py", "waiting_inbox"),
        # SPEC-029 (TASK-055): one evidence version's checks, written by the system's own
        # processing, and read after `authorise` on that version's item (client audience only
        # for client roles, in the service).
        ("src/abacus/modules/evidence/repository.py", "insert_checks"),
        ("src/abacus/modules/evidence/repository.py", "latest_checks"),
        # Ethical walls are firm-level, not engagement-scoped (SPEC-002): authz reads a person's
        # own walls; listing every wall needs `wall.list`, authorised by the service first.
        ("src/abacus/modules/identity/repository.py", "walled_clients"),
        ("src/abacus/modules/identity/repository.py", "all_walls"),
        # SPEC-308 (TASK-319): one paper's cells, citations and versions, and a target's
        # sign-offs, after `authorise(workpaper.read)` (or the sign-off action) on its engagement.
        ("src/abacus/modules/workpapers/repository.py", "newest_cells"),
        ("src/abacus/modules/workpapers/repository.py", "citations_of"),
        ("src/abacus/modules/workpapers/repository.py", "versions_of"),
        # P-04-T15: who set a paper's cells (its preparers), after the same check.
        ("src/abacus/modules/workpapers/repository.py", "cell_setters"),
        ("src/abacus/modules/review/repository.py", "sign_offs_of"),
        # P-04-T14: the computed staleness query over the same targets, after the same check.
        ("src/abacus/modules/review/repository.py", "stale_sign_offs"),
        # SPEC-309 (TASK-320): ledger stays dependency-free (no visible()); the assurance read
        # model authorises `trial_balance.read` on the engagement before any of these run.
        ("src/abacus/modules/ledger/tb_repository.py", "snapshots_of_entity"),
        ("src/abacus/modules/ledger/tb_repository.py", "trial_balances_of"),
        ("src/abacus/modules/ledger/tb_repository.py", "versions_of"),
        ("src/abacus/modules/ledger/tb_repository.py", "newest_annotations"),
        # SPEC-310 (TASK-321): a trial balance's checks and their current definitions, after
        # `authorise(trial_balance.read)` on its engagement.
        ("src/abacus/modules/workpapers/tie_repository.py", "checks_of"),
        ("src/abacus/modules/workpapers/tie_repository.py", "current_versions"),
        # SPEC-311 (TASK-322): an engagement's entries for the trial balance's layers (the
        # caller authorised `trial_balance.read`) and the SUM (`procedure.read`).
        ("src/abacus/modules/fieldwork/repository.py", "engagement_adjustments"),
        # SPEC-312 (TASK-324): one approved statement's lines, after `evidence.read` on its item.
        ("src/abacus/modules/evidence/statement_repository.py", "transactions_of"),
        # SPEC-313 (TASK-331): an engagement's notes and events, a target's notes inside its
        # sign-off, and its papers for the matrix and G5, each after authorising on it.
        ("src/abacus/modules/review/repository.py", "notes_of"),
        ("src/abacus/modules/review/repository.py", "note_events_of"),
        ("src/abacus/modules/review/repository.py", "notes_of_target"),
        # P-04-T23: a decision card's own chain, its successors and its history, read after
        # `authorise(decision.read)` on the card's engagement (or for rows a `visible()` list
        # already returned).
        ("src/abacus/modules/review/repository.py", "cards_by_id"),
        ("src/abacus/modules/review/repository.py", "successors_of"),
        ("src/abacus/modules/review/repository.py", "versions_of"),
        ("src/abacus/modules/workpapers/repository.py", "engagement_papers"),
        # SPEC-314 (TASK-332): an engagement's risks for the EQR digest, after authorising on it.
        ("src/abacus/modules/fieldwork/repository.py", "engagement_risks"),
        # SPEC-314 (TASK-332): an engagement's completion records, after authorising on it.
        ("src/abacus/modules/assurance/completion_repository.py", "records_of"),
        # TASK-344: PDFs the current extractor hasn't read, for the system re-read tool.
        ("src/abacus/modules/evidence/repository.py", "stale_pdf_uploads"),
        # P-03-T05, T06: one source's word-layer pages, read by the system (upload processing,
        # the backfill) or by a citation verifier only after `authorise(evidence.read)` on the
        # anchor's engagement and a check that the version is in it; the pages just written;
        # and the backfill's next batch (the system only).
        ("src/abacus/modules/evidence/repository.py", "pages_of"),
        ("src/abacus/modules/evidence/repository.py", "insert_pages"),
        ("src/abacus/modules/evidence/repository.py", "sources_without_words"),
        # P-03-T15: the masking backfill's batch, as the system on the firm's own uploads.
        ("src/abacus/modules/evidence/repository.py", "sources_without_masks"),
        # P-03-T08, T09: the events of citations already read through `visible()` or authorised
        # on; one source's PII regions and one preview's page rows, after the viewer or the
        # citation reader authorised `evidence.read` / `citation.read` on that source.
        ("src/abacus/modules/evidence/repository.py", "events_of"),
        ("src/abacus/modules/evidence/repository.py", "pii_regions_of"),
        # P-03-T15 review N1: one source's not-scannable pages, beside `scanned_pages`.
        ("src/abacus/modules/evidence/repository.py", "unscannable_pages"),
        ("src/abacus/modules/evidence/repository.py", "preview_pages_of"),
        # SPEC-316 (TASK-345): firm taxonomy content (after a firm-level check) and a mapping
        # set's edits (after authorising on its engagement).
        ("src/abacus/modules/ledger/mapping_repository.py", "grouping_sets"),
        ("src/abacus/modules/ledger/mapping_repository.py", "versions_of_sets"),
        ("src/abacus/modules/ledger/mapping_repository.py", "catalogue_rows"),
        ("src/abacus/modules/ledger/mapping_repository.py", "newest_edits"),
        # SPEC-317 (TASK-460): fieldwork's progress for the dashboard, after authorising on it.
        ("src/abacus/modules/fieldwork/repository.py", "engagement_progress_rows"),
        # P-03-T12: the moved and broken detector's reads (the system) and an owner's
        # `mark_sources_superseded` in its own unit of work; the events a run writes.
        ("src/abacus/modules/evidence/repository.py", "earlier_versions"),
        ("src/abacus/modules/evidence/repository.py", "citations_on"),
        ("src/abacus/modules/evidence/repository.py", "insert_citation_events"),
        # R-01-T09: the drop sort's candidates in one binder (each re-checked for the dropper
        # with `member_could`) and the dropper's own files in one batch.
        ("src/abacus/modules/requests/repository.py", "drop_item_rows"),
        ("src/abacus/modules/evidence/repository.py", "drops_of_batch"),
        # P-04-T16: the human-gate projector's reads (the system, per engagement or for the
        # rebuild); `GET /v1/human-gates` filters the projection through `visible()`.
        ("src/abacus/modules/agents/repository.py", "latest_screenings_for_gates"),
        ("src/abacus/modules/agents/repository.py", "latest_upload_reviews_for_gates"),
        ("src/abacus/modules/agents/repository.py", "latest_matches_for_gates"),
        ("src/abacus/modules/agents/repository.py", "undecided_drafts_for_gates"),
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
                    if isinstance(inner, ast.Call)
                    and _terminal_name(inner.func) in ("visible", "visible_items", "visible_scope")
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
    "<read action>", <column>)` (or, for request items, `visible_items`, SPEC-020) inside
    `.where(...)`."""
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
            # F-03-T27 (ADR-145): a scoped list declares its kind as a literal.
            if _terminal_name(call.func) == "visible_scope":
                kind = call.args[2] if len(call.args) > 2 else None
                if not (isinstance(kind, ast.Constant) and kind.value in _SCOPE_KINDS):
                    yield Finding(call.lineno, "visible_scope() needs a literal scope kind")


# Which other modules each module may import (ADR-008: one-way dependencies). Modules not listed
# may use identity only. Identity and organisations depend on no module.
# The module graph (F-03-T08; docs/plan/03-backend-architecture.md section 2.3): a module imports
# only these modules' api.py. `identity` and `platform` are reachable from everything above them.
# Rules: nothing imports portal, notifications, practice, workbench or audit_trail; shared
# engines never import a service line (they learn of targets through registration slots); upward
# state changes travel as outbox events. Edges marked "today" predate the plan's split.
_BASE = frozenset({"identity", "platform"})
MODULE_DEPENDENCIES: dict[str, frozenset[str]] = {
    "identity": frozenset(),
    "platform": frozenset({"identity"}),
    # P-01-T12: the email channel renders and sends through communications (COMM-001).
    "notifications": _BASE | {"communications"},
    # SPEC-002 AC-5, DEC-121: the audit explorer hides events about engagements the reader may not
    # see; each owner registers which engagement its targets belong to (kernel.audit_owners),
    # so this reads the registry and depends only on identity and engagements; nothing imports it.
    # G-02-T02 (SPEC-349): + platform, whose labeler and value-resolver slots it reads (G-02-T09).
    "audit_trail": frozenset({"identity", "engagements", "platform"}),
    "organisations": _BASE,
    "ledger": frozenset(),
    "methodology": _BASE,
    "engagements": _BASE | {"organisations", "methodology"},
    "requests": _BASE | {"engagements"},
    # evidence reads which versions fulfil which items, and moves items after a review decision
    # (SPEC-004 Q4, TASK-019); requests never imports evidence. SPEC-029 (TASK-055 D2): upload
    # cross-checks read the year end's trial balance snapshot (ledger imports nothing).
    "evidence": _BASE | {"engagements", "requests", "ledger"},
    "review": _BASE | {"engagements"},
    "collaboration": _BASE | {"engagements"},
    "signatures": _BASE | {"engagements", "organisations", "evidence"},
    # SPEC-037 (TASK-083): populations and selection are pure functions over ledger snapshots.
    "sampling": _BASE | {"engagements", "ledger", "evidence"},
    "connections": _BASE | {"engagements", "organisations", "ledger", "evidence", "requests"},
    # The outbound scope checker reads each owner's facts through its API (SPEC-006, TASK-021 D2).
    # SPEC-032 (TASK-062 D1): it registers itself as the check on comments shared with a client.
    "communications": _BASE | {"engagements", "organisations", "ledger", "evidence", "requests"},
    # A-02 §4.1 (A-02-T16): POR-16's cards and start compose `connections` (which never imports
    # integrations, so the edge stays acyclic; W-01 relies on the same rule).
    # A-02-T23 (DEC-611): the reconnect request mails the owners through communications.
    "integrations": _BASE
    | {"organisations", "engagements", "evidence", "ledger", "connections", "communications"},
    # The engagement graph reads the latest snapshot's accounts (SPEC-008, TASK-023 D1).
    # SPEC-027 (TASK-051 D3): the engagement agent works out overdue reminders; communications
    # sends them (the only sender, COMM-001).
    "agents": _BASE
    | {"engagements", "organisations", "evidence", "requests", "ledger", "communications"}
    | {"methodology", "review"}
    | {"fieldwork"},  # today: SPEC-037 Q4 (TASK-085 D3), the entry assessor reads selected entries
    # Today's fieldwork (procedures, workpapers, findings) splits into workpapers and assurance.
    # TASK-084 adds evidence (support) and requests (asking the client for it).
    "fieldwork": _BASE | {"engagements", "ledger", "sampling", "evidence", "requests"},
    "workpapers": _BASE
    | {"engagements", "methodology", "evidence", "requests", "ledger", "sampling", "review"}
    | {"agents"},
    "adjustments": _BASE
    | {"engagements", "ledger", "methodology", "review", "agents", "integrations"},
    "reporting": _BASE
    | {"engagements", "methodology", "evidence", "ledger", "review", "adjustments"},
    "assurance": _BASE
    | {"organisations", "engagements", "methodology", "requests", "evidence", "ledger"}
    | {"sampling", "review", "collaboration", "workpapers", "adjustments", "reporting"}
    | {"signatures", "communications", "agents"},
    "attest": _BASE
    | {"organisations", "engagements", "methodology", "requests", "evidence", "sampling"}
    | {"review", "workpapers", "reporting", "signatures", "communications", "agents"}
    | {"integrations", "assurance"},
    "tax": _BASE
    | {"organisations", "engagements", "methodology", "requests", "evidence", "ledger"}
    | {"review", "workpapers", "adjustments", "reporting", "signatures", "communications"}
    | {"agents", "integrations"},
    "closes": _BASE
    | {"organisations", "engagements", "methodology", "requests", "evidence", "ledger"}
    | {"review", "workpapers", "adjustments", "reporting", "communications", "agents"}
    | {"integrations"},
    "notices": _BASE
    | {"organisations", "engagements", "requests", "evidence", "review", "signatures"}
    | {"communications", "agents", "tax"},
    "workbench": _BASE | {"organisations", "engagements", "methodology", "agents", "integrations"},
    "practice": _BASE | {"organisations", "engagements", "integrations"},
    # A-02-T23 (DEC-517, DEC-611): the home's reconnect to-do reads connections.
    "portal": _BASE
    | {"organisations", "engagements", "requests", "evidence", "signatures", "communications"}
    | {"collaboration", "review", "assurance", "attest", "tax", "closes", "notices"}
    | {"connections"},
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
# A name called after FROM (`SELECT * FROM auth_session_rotate(...)`) is a function, not a table:
# set-returning definer functions are reviewed in schema_check.DEFINER_FUNCTIONS (P-01-T09).
_SQL_TABLE = re.compile(
    r"\b(?:FROM|JOIN)\s+([a-z_][a-z0-9_]*)\b(?!\s*\()|\b(?:INTO|UPDATE)\s+([a-z_][a-z0-9_]*)"
)


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
                yield from check(match.group(1) or match.group(2), node.lineno)


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
    | {"revoke"}  # A-02-T16 review M1: the read-only grant's end, never a write to the books
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


# F-03-T15 (migration 0071): the retired request status codes (chapter 09 section 9.5.6).
_RETIRED_REQUEST_CODES = frozenset({"open", "ready_for_review", "needs_revision", "accepted"})


def _status_side(node: ast.AST) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "status") or (
        isinstance(node, ast.Name) and node.id == "status"
    )


def _retired_literals(node: ast.AST) -> list[str]:
    return [
        c.value
        for c in ast.walk(node)
        if isinstance(c, ast.Constant) and c.value in _RETIRED_REQUEST_CODES
    ]


def _check_retired_request_codes(src: SourceFile) -> Iterator[Finding]:
    """A request item's status compared with, filtered by or set to a retired code."""
    for node in ast.walk(src.tree):
        found: list[str] = []
        if isinstance(node, ast.Compare) and (
            _status_side(node.left) or any(_status_side(c) for c in node.comparators)
        ):
            found = _retired_literals(node)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "in_"
            and _status_side(node.func.value)
        ):
            found = [v for a in node.args for v in _retired_literals(a)]
        elif isinstance(node, ast.keyword) and node.arg == "status":
            found = _retired_literals(node.value)
        for value in found:
            yield Finding(
                getattr(node, "lineno", 0),
                f"request status {value!r} is retired (F-03-T15): use the registry's codes",
            )


# L12 (F-02-T07; glossary rule 3): identifiers the glossary's "Don't use" columns ban, generated
# from docs/product/glossary.md so the two can't drift. Checked on what names a concept in code:
# class names (as snake_case), top-level function names and table names (whole, singular or first
# word). Locals stay out: the bans name concepts, and words like `email` are fine as variables.
GLOSSARY = BACKEND.parent / "docs" / "product" / "glossary.md"
_BAN_CELL = re.compile(r"`([a-z_][a-z0-9_]*)`")


def glossary_bans(text: str | None = None) -> dict[str, str]:
    """Banned identifier -> the glossary's code name for the concept."""
    source = text if text is not None else GLOSSARY.read_text(encoding="utf-8")
    bans: dict[str, str] = {}
    for line in source.splitlines():
        if not line.startswith("| ") or line.startswith(("|---", "| Term ")):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        code = _BAN_CELL.findall(cells[2])
        for banned in _BAN_CELL.findall(cells[3]):
            bans.setdefault(banned, code[0] if code else cells[0])
    return bans


def glossary_compounds(text: str | None = None) -> frozenset[str]:
    """Identifiers a term table's "Code name" column names: compounds the glossary allows.

    A banned word may still open a compound the glossary itself names, as the Prompt row allows
    `email_template` (R-01-T04: `email_template_drafts`, `email_suppressions`). Only the term
    tables count, never the legacy-identifier table, so a rename never re-allows the old name.
    """
    source = text if text is not None else GLOSSARY.read_text(encoding="utf-8")
    names: set[str] = set()
    in_terms = False
    for line in source.splitlines():
        if line.startswith("| Term "):
            in_terms = True
            continue
        if not line.startswith("|"):
            in_terms = False
            continue
        if not in_terms or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4:
            names.update(_BAN_CELL.findall(cells[2]))
    return frozenset(names)


# Names in use before the glossary bound identifiers (2026-10-21), each with the task that renames
# it. A new use of a banned name fails; these may stay until their rename lands.
L12_LEGACY: dict[tuple[str, str], str] = {
    ("src/abacus/modules/communications/models.py", "Message"): "P-06 message threads",
    ("src/abacus/modules/communications/models.py", "messages"): "P-06 message threads",
    ("src/abacus/modules/engagements/setup_steps.py", "Member"): "P-07 engagement_member views",
    ("src/abacus/modules/engagements/roll_forward.py", "Proposal"): "P-07 roll-forward v2",
    ("src/abacus/modules/evidence/service.py", "Proposal"): "P-04 suggestions",
    ("src/abacus/modules/evidence/cross_checks.py", "Account"): "A-02 ledger accounts",
    ("src/abacus/modules/evidence/checks.py", "CheckResult"): "P-03 trust kit",
    ("src/abacus/modules/evidence/uploads.py", "upload"): "P-06 fulfilments",
    ("src/abacus/modules/identity/service.py", "TeamMember"): "G-01 teams",
    ("src/abacus/modules/agents/inbox_match.py", "match"): "N-01 inbox",
    ("src/abacus/modules/agents/entry_assess.py", "ask"): "A-08 entry assessor",
    ("src/abacus/modules/agents/knowledge.py", "document"): "K-01 knowledge items",
    ("src/abacus/modules/fieldwork/models.py", "SelectionRow"): "A-03 sample_sets",
    ("src/abacus/modules/fieldwork/models.py", "selections"): "A-03 sample_sets",
    ("src/abacus/modules/fieldwork/models.py", "selection_approvals"): "A-03 sample_sets",
    ("src/abacus/modules/fieldwork/models.py", "selection_rows"): "A-03 sample_sets",
    ("src/abacus/modules/evidence/models.py", "upload_checks"): "P-06 fulfilments",
    ("src/abacus/modules/evidence/models.py", "upload_extractions"): "P-06 fulfilments",
    ("src/abacus/modules/evidence/models.py", "upload_previews"): "P-06 fulfilments",
    ("src/abacus/modules/evidence/models.py", "upload_preview_pages"): "P-06 fulfilments",
    ("src/abacus/modules/agents/models.py", "upload_reviews"): "P-06 fulfilments",
    ("src/abacus/modules/agents/models.py", "upload_review_flags"): "P-06 fulfilments",
    ("src/abacus/modules/connections/models.py", "sync_runs"): "W-01 integrations",
}


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _l12_candidates(tree: ast.Module) -> Iterator[tuple[int, str, list[str]]]:
    """(line, name as written, the forms checked against the ban list)."""
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield node.lineno, node.name, [node.name]
        elif isinstance(node, ast.ClassDef):
            yield node.lineno, node.name, [_snake(node.name)]
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in node.targets)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            table = node.value.value
            first = table.split("_")[0]
            forms = [table, table.removesuffix("s"), first, first.removesuffix("s")]
            yield node.lineno, table, forms


def _check_glossary_identifiers(src: SourceFile) -> Iterator[Finding]:
    bans = glossary_bans()
    compounds = glossary_compounds()
    for line, name, forms in _l12_candidates(src.tree):
        hit = next((f for f in forms if f in bans), None)
        if hit is None or (src.rel, name) in L12_LEGACY or (hit != name and name in compounds):
            continue
        yield Finding(
            line, f"{name!r} uses the glossary's banned {hit!r}: the code name is {bans[hit]!r}"
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
            # G-02-T10 (DEC-436): the audit label index, a rebuildable projection of the audit
            # trail; auditing its own writes would feed itself, as the hash chain's would.
            "src/abacus/modules/audit_trail/labels.py",
            "tests/integration/test_tenancy.py",
            "tests/integration/test_uow_session_rollback.py",
            # Calls the slot ledger's functions as the app, one committed call at a time.
            "tests/integration/agent_tests/test_work_slots_db.py",
        ),
    ),
    Rule(
        id="TLS-001",
        description="A tooling database connection passes ssl= (verify-full whenever TLS is used)",
        adr="ADR-014",
        check=_check_tool_connection_tls,
        include=("src/abacus_tools/*",),
        # Local-only: the throwaway compose or test-container stack, never a hosted database.
        exclude=("src/abacus_tools/stack.py", "src/abacus_tools/local/seed_dev.py"),
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
            # G-09: the tools' one connection helper, with the app's TLS decision.
            "src/abacus_tools/db_connect.py",
            "src/abacus_tools/quality/schema_check.py",
            # SPEC-012: the access review runs as the owner role (the only one that may read it).
            "src/abacus_tools/access_review.py",
            # SPEC-024 (TASK-040): sign-up codes are the owner's; the app role can't reach them.
            "src/abacus_tools/signup_codes.py",
            # SPEC-036 (TASK-076 D1): agent stages are the owner's; the app role only reads them.
            "src/abacus_tools/agent_stage.py",
            # Q-01-T45 (ADR-156): provision_firm as abacus_ops; entitlements as the owner role.
            "src/abacus_tools/tenants.py",
            "tests/integration/conftest.py",
            "tests/integration/test_local_stack.py",
            "tests/integration/test_tenancy.py",
            "tests/integration/test_schema_check_db.py",
            "tests/integration/test_migrations_env.py",
            "tests/integration/test_unit_of_work.py",
            "tests/integration/test_outbox_relay.py",
            "tests/integration/test_identity.py",
            # R-01-T19: seeds as the superuser and proves the app role's grants.
            "tests/integration/test_r01t19_email_template_versions.py",
            "tests/integration/test_staff_session.py",  # P-01-T09: seeds as the superuser
            "tests/integration/test_telemetry_tunnel.py",  # Q-01-T48: seeds as the superuser
            "tests/integration/test_engagements.py",
            "tests/integration/test_engagements_schema.py",
            "tests/integration/test_work_items.py",  # F-03-T05: setup as the superuser
            "tests/integration/test_evidence.py",
            "tests/integration/test_retrieval.py",
            "tests/integration/test_ledger_schema.py",
            "tests/integration/test_retrieval_workflow.py",
            "tests/integration/test_retrieval_api.py",
            "tests/integration/agent_tests/support.py",
            "tests/integration/agent_tests/test_work_slots_db.py",  # the ledger, as the app
            "tests/integration/backfill/support.py",  # Q-03 acceptance tests seed as the superuser
            "tests/integration/trust_kit/support.py",  # P-03-T05, T06: seeds as the superuser
            "tests/security/support.py",  # the security suite seeds as the superuser
            "tests/contracts/undo/support.py",  # P-04-T13: the Undo suite seeds as the superuser
            # P-04-T13: the human-only CHECKs and insert-only rules, as the app role and the owner
            "tests/integration/test_p04t13_review_schema_independent.py",
            # S13 schema tests: the AI-policy guard (G-02-T23) and pilot grants (Q-04-T007).
            "tests/integration/test_g02t23_autonomy_policy_migration.py",
            "tests/integration/test_q04t007_pilot_enrolments.py",
            "tests/integration/test_seed_dev.py",
            # Q-03-T028: loads the plan tests' synthetic fixture as the superuser, rolled back.
            "tests/integration/test_q03t028_plan_tests.py",
            # A-02-T04: 0149's round trip on a private database; seeds as the superuser and
            # proves the app role's refusals with the tenant set, as tenant_session sets it.
            "tests/integration/test_tb_of_record_schema.py",
            # A-02-T11/T12/T13 (S10): 0193-0195's round trips on private databases; seed as the
            # superuser and prove the app role's refusals with the tenant set by hand.
            "tests/integration/test_tie_out_schema.py",
            "tests/integration/test_integrations_schema.py",
            "tests/integration/test_entity_connections_schema.py",
            # I-01-T04, K-01-T05 (S11): the human-only snooze and reassignment rows, the card's
            # reassign guard and the frozen methodology content, proved as the app role with the
            # tenant and actor set by hand, as tenant_session sets them.
            "tests/integration/backfill/test_i01t04_human_gate_home.py",
            "tests/integration/backfill/test_k01t05_methodology_programs.py",
            # Records replay fixtures against throwaway containers (seeds as the superuser).
            "src/abacus_tools/workflows/record_retrieval.py",
            "src/abacus_tools/stack.py",  # the recorders' and evals' stack (connect_db)
            # Seeds the local stack as its superuser (local only; TASK-012).
            "src/abacus_tools/local/seed_dev.py",
            # Bootstraps the scenario firm, offices and people as the owner (F-04-T13).
            "src/abacus_tools/synthetic/scenarios/brightwater_hale/loader.py",
        ),
    ),
    Rule(
        id="L12",
        description="Glossary-banned identifiers (the Don't use columns)",
        adr="DEC-14",
        check=_check_glossary_identifiers,
        include=("src/abacus/modules/*",),
    ),
    Rule(
        id="REQ-002",
        description="No retired request status codes (open, ready_for_review, ...)",
        adr="ADR-138",
        check=_check_retired_request_codes,
        include=(
            "src/abacus/modules/requests/*",
            "src/abacus/modules/evidence/*",
            "src/abacus/modules/connections/*",
            "src/abacus/modules/engagements/*",
        ),
    ),
    Rule(
        id="SQL-001",
        description="No SQL built from f-strings, %, + or .format()",
        adr="ADR-014",
        check=_check_built_sql,
        # DDL can't bind identifiers; migration helpers validate table names first. The plan tests
        # (Q-03-T028) build the fixture's INSERT and EXPLAIN from catalog names and fixed probes.
        exclude=(
            "src/abacus/kernel/db/migration.py",
            "tests/integration/test_q03t028_plan_tests.py",
        ),
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
        description="skip and xfail carry an issue reference (a strict xfail may cite a TASK)",
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
            "src/abacus/modules/audit_trail/labels.py",  # see UOW-001 (DEC-436)
            "tests/integration/*",
            "tests/security/conftest.py",  # the suite's database (as integration's conftest)
            "tests/contracts/undo/conftest.py",  # P-04-T13: the Undo suite's own database
        ),
    ),
    Rule(
        id="CLOCK-001",
        description="Only abacus.kernel.clock reads the wall clock",
        adr="ADR-143 (F-04-T17)",
        check=_check_clock,
        include=("src/*",),
        exclude=(
            "src/abacus/kernel/clock.py",
            # kernel.clock imports config, so config's provider-terms check can't import it back.
            "src/abacus/kernel/config.py",
            "src/abacus_tools/quality/banned_patterns.py",
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
            # SPEC-036 (TASK-076 D1): writes a stage and its audit event as the platform.
            "src/abacus_tools/agent_stage.py",
            # Q-01-T45: writes an entitlement and its audit event as the operator.
            "src/abacus_tools/tenants.py",
            # F-04-T13: bootstrap writes carry the event's tenant, actor and business time.
            "src/abacus_tools/synthetic/scenarios/brightwater_hale/loader.py",
            "tests/integration/test_tenancy.py",
            # P-04-T05: `Seeder.as_actor` drives the database's own actor and clock checks.
            "tests/integration/agent_tests/support.py",
            "tests/integration/test_schema_check_db.py",
            # P-04-T13: the actor GUCs the human-only CHECKs bind, set as a unit of work sets them
            "tests/integration/test_p04t13_review_schema_independent.py",
            # S13 schema tests: the AI-policy guard (G-02-T23) and pilot grants (Q-04-T007).
            "tests/integration/test_g02t23_autonomy_policy_migration.py",
            "tests/integration/test_q04t007_pilot_enrolments.py",
            "tests/integration/agent_tests/test_work_slots_db.py",  # calls the ledger functions
            # A-02-T04: the app role's refusals on 0149's tables, with the tenant set by hand.
            "tests/integration/test_tb_of_record_schema.py",
            # A-02-T11/T12/T13 (S10): the app role's refusals on 0193-0195's tables.
            "tests/integration/test_tie_out_schema.py",
            "tests/integration/test_integrations_schema.py",
            "tests/integration/test_entity_connections_schema.py",
            # I-01-T04, K-01-T05 (S11): the human-only snooze and reassignment rows, the card's
            # reassign guard and the frozen methodology content, proved as the app role with the
            # tenant and actor set by hand, as tenant_session sets them.
            "tests/integration/backfill/test_i01t04_human_gate_home.py",
            "tests/integration/backfill/test_k01t05_methodology_programs.py",
            # Q-03-T028: plans each list as the app role with the firm's tenant set by hand, as
            # tenant_session sets it, so row-level security adds the tenant predicate.
            "tests/integration/test_q03t028_plan_tests.py",
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
            "tests/integration/backfill/conftest.py",
            "tests/security/conftest.py",
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
            # SPEC-012: the staff token, verified by the staff issuer (break-glass).
            "src/abacus/modules/identity/support.py",
            # A-02-T26 (DEC-709): a live connector sets the provider's Authorization on its own
            # outbound reads through `kernel.egress`; it never reads an inbound request.
            "src/abacus/modules/connections/connectors/quickbooks_online.py",
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
        description="HTTP routes are served only through AbacusRouter, or are on the public list",
        adr="ADR-012, ADR-027, ADR-152",
        check=_check_route_bypass,
        include=("src/abacus/*",),
        exclude=("src/abacus/modules/identity/routing.py",),
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
        id="POLICY-001",
        description="Only the kernel constructs a policy-actor context",
        adr="ADR-005, ADR-161",
        check=_check_policy_context,
        include=("src/abacus/*",),
        exclude=("src/abacus/kernel/*",),
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
            # SPEC-012: a support context, built only from a validated, active support session.
            "src/abacus/modules/identity/support.py",
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
        # P-04-T25 (DEC-604, DEC-609; ADR-161 clause 3): the typed adapters approve through the
        # same call the AUD-03 routes make; `REVIEW_DECIDE_EXEMPT` names the scopes that may.
        include=("src/abacus/*",),
        exclude=(
            "src/abacus/modules/evidence/service.py",
            "src/abacus/modules/evidence/routes.py",
        ),
    ),
    Rule(
        id="SIGNOFF-001",
        description="Only the review service and the owners' sign routes reach a sign-off",
        adr="ADR-160",
        check=_check_named_any(
            ("record_sign_off", "sign_target"),
            "only a person signs off, through the review service (INV-1, ADR-160 clause 12)",
        ),
        # P-04-T18: the definitions, review's public interface and its route, and the owners'
        # sign routes that call `record_sign_off` (SPEC-308, SPEC-333); any other file fails.
        include=("src/abacus/*",),
        exclude=(
            "src/abacus/modules/review/service.py",
            "src/abacus/modules/review/sign_offs.py",
            "src/abacus/modules/review/bulk.py",  # P-04-T22: each bulk item signs through it
            "src/abacus/modules/review/contract.py",
            "src/abacus/modules/review/api.py",
            "src/abacus/modules/workpapers/service.py",
            "src/abacus/modules/assurance/mapping.py",
            "src/abacus/modules/assurance/trial_balance.py",
        ),
    ),
    Rule(
        id="DECISION-001",
        description="Only the decision card service and its route reach a card's decision",
        adr="ADR-160",
        check=_check_named(
            "decide_card",
            "only the card's reserved person decides, through the review service (INV-1, "
            "ADR-160 clause 8)",
        ),
        # P-04-T23: the definition and its route; any other file naming it fails.
        include=("src/abacus/*",),
        exclude=(
            "src/abacus/modules/review/decisions.py",
            "src/abacus/modules/review/contract.py",
        ),
    ),
    Rule(
        id="PROPOSAL-001",
        description="Only the proposal service, its adapters and its routes reach a proposal's "
        "decision",
        adr="ADR-161",
        check=_check_named_scoped(
            (
                "approve_proposal",
                "reject_proposal",
                "route_proposal",
                "adopt_suggestion",
                "dismiss_suggestion",
                "approve_typed",
                "reject_typed",
            ),
            "only a person approves, rejects, adopts or dismisses the agent's proposal, through "
            "the agents service (INV-1, ADR-160 clause 12, ADR-161)",
            PROPOSAL_EXEMPT,
        ),
        # P-04-T24, T25: only the scopes in `PROPOSAL_EXEMPT` (the definitions' `__all__`, the
        # routes and their imports); anything else naming one fails.
        include=("src/abacus/*",),
    ),
    Rule(
        id="ACCEPT-001",
        description="Only the acceptance service and its route reach the acceptance decision",
        adr="ADR-005",
        check=_check_named(
            "decide_acceptance", "only the engagement partner decides acceptance (INV-1)"
        ),
        # P-07-T35 (SPEC-332 AC-10): the definition, its route, and the module's public
        # interface that re-exports it; any other file naming it fails.
        include=("src/abacus/*",),
        exclude=(
            "src/abacus/modules/engagements/acceptance.py",
            "src/abacus/modules/engagements/acceptance_contract.py",
            "src/abacus/modules/engagements/api.py",
        ),
    ),
    Rule(
        id="CONFLICT-001",
        description="Only the conflict service and its route reach the conflict clearance",
        adr="ADR-005",
        check=_check_named(
            "clear_conflict_result", "only a partner or manager clears a conflict hit (INV-1)"
        ),
        # P-07-T36 (SPEC-332 AC-25): the definition, its route and the module's interface.
        include=("src/abacus/*",),
        exclude=(
            "src/abacus/modules/organisations/conflicts.py",
            "src/abacus/modules/organisations/conflicts_contract.py",
            "src/abacus/modules/organisations/api.py",
        ),
    ),
    Rule(
        id="INDEP-001",
        description="Only the independence service and its route reach the conclusion",
        adr="ADR-005",
        check=_check_named(
            "conclude_independence", "only the engagement partner concludes independence (INV-1)"
        ),
        # P-07-T41 (SPEC-332 AC-20): the definition, its route, and the module's interface.
        include=("src/abacus/*",),
        exclude=(
            "src/abacus/modules/engagements/independence.py",
            "src/abacus/modules/engagements/acceptance_contract.py",
            "src/abacus/modules/engagements/api.py",
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
        id="COMM-002",
        description="Only communications' scheduled-reminder service builds a system send",
        adr="ADR-005, DEC-74",
        check=_check_system_send,
        include=("src/abacus/*",),
        exclude=("src/abacus/modules/communications/*",),
    ),
    Rule(
        id="BOUND-004",
        description="No dynamic import of an abacus module inside modules/",
        adr="ADR-008, DEC-588",
        check=_check_dynamic_module_import,
        include=("src/abacus/modules/*",),
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
        description="Only kernel.storage (and the Bedrock route, SPEC-010) uses the AWS SDK",
        adr="ADR-016, ADR-104, ADR-073",
        check=_check_confined(
            ("boto3", "botocore", "aioboto3", "aiobotocore", "s3fs"), "abacus.kernel.storage"
        ),
        include=("src/abacus/*",),
        exclude=(
            "src/abacus/kernel/storage.py",
            # Bedrock runtime (Titan embeddings) and the parity check's Bedrock API probe.
            "src/abacus/ai_gateway/routes/bedrock.py",
            "src/abacus/ai_gateway/routes/parity.py",
        ),
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
        # A-02-T16 review round 2 L5: the integrations adapters and the Writer port too.
        include=(
            "src/abacus/modules/connections/*",
            "src/abacus/modules/integrations/adapters.py",
            "src/abacus/modules/integrations/writers/*",
        ),
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
        id="FLAG-001",
        description="Flags come from the registry and are read by their generated constant",
        adr="ADR-089",
        check=_check_flags,
        include=("src/abacus/*",),
        exclude=("src/abacus/kernel/_flags.py", "src/abacus/kernel/flags.py"),
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
        id="CLS-001",
        description="Classification flags only through classified() and the path helpers",
        adr="ADR-167, ADR-031",
        check=_check_classification_flag_keys,
        include=("src/abacus/*",),
        exclude=("src/abacus/kernel/classification.py",),
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
