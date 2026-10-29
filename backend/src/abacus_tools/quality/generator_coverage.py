"""The generator-coverage sweep (Q-03-T095; ADR-080): does every table and matrix kind the code
uses have its generated tests?

    python -m abacus_tools.quality.generator_coverage [--report PATH]

ADR-080 asks for an isolation test for every repository method. Isolation is proven per table:
forced row-level security keyed to the tenant, and the generated suite
(`tests/security/test_tenant_isolation.py`) checking that nothing of firm B reads under firm A for
every tenant table the module registries name. So a repository method is covered when every table
its SQL names is registered and, if tenant-scoped, in the generated list. The sweep checks:

1. tables: every table a module's SQL names is in `schema_check.TABLE_OWNERS`;
2. isolation: every tenant table is in the generated isolation suite;
3. conditions: every matrix condition key has an allow and a deny case
   (`tests/unit/identity/test_matrix_conditions.py`);
4. decisions: every cell decision the matrix uses names the tests that allow and deny it.

Exit 1 on any gap; `--report` writes the findings as Markdown for the sweep record.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections.abc import Iterable
from pathlib import Path

from abacus.modules.identity.api import CONDITION_KEYS, RULES
from abacus_tools.codegen.security_tests import ISOLATION, tenant_tables
from abacus_tools.quality.schema_check import TABLE_OWNERS

ROOT = Path(__file__).resolve().parents[3]
MODULES = ROOT / "src" / "abacus" / "modules"
CONDITION_TESTS = ROOT / "tests" / "unit" / "identity" / "test_matrix_conditions.py"

# Each cell decision the matrix may use, and the tests that prove it allows and denies. A decision
# the matrix uses with no entry here, or whose tests no longer name it, is a gap.
DECISION_COVERAGE: dict[str, tuple[str, ...]] = {
    "allow": ("tests/security/test_permission_matrix_generated.py",),
    "deny": ("tests/security/test_permission_matrix_generated.py",),
    "assigned_only": (
        "tests/unit/identity/test_permission_matrix.py",
        "tests/unit/identity/test_policy_overrides.py",
    ),
    "client_visible_only": (
        "tests/unit/identity/test_permission_matrix.py",
        "tests/unit/identity/test_policy_overrides.py",
    ),
    "delegated_only": (
        "tests/unit/identity/test_permission_matrix.py",
        "tests/unit/portal/test_room_rules.py",
    ),
    "in_scope": ("tests/unit/identity/test_matrix_conditions.py",),
    "task_scope": (
        "tests/security/test_agent_principal.py",
        "tests/unit/identity/test_autonomy_condition.py",
    ),
    "firm_setting": ("tests/security/test_walls_and_need_to_know.py",),
}

# SQL table positions: FROM, JOIN, INTO, UPDATE (and DELETE FROM), keywords in upper case as the
# code writes SQL, so prose ("every row from …") never matches. CTEs and functions are dropped.
_SQL_TABLE = re.compile(r"\b(?:FROM|JOIN|INTO|UPDATE)\s+([a-z_][a-z0-9_]*)\b(?!\s*\()")
_CTE = re.compile(r"\b([a-z_][a-z0-9_]*)\s+AS\s*\(")
_NOT_TABLES = frozenset(
    {"select", "unnest", "lateral", "values", "jsonb_to_recordset", "set", "only", "the", "a"}
)


def _module_files() -> list[Path]:
    """Every module file: SQL belongs in repositories, but a table named anywhere is checked."""
    return sorted(MODULES.rglob("*.py"))


def _sql(source: str) -> list[str]:
    """The source's SQL: each implicitly joined string (f-string parts included) as one text."""
    out: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.JoinedStr):
            out.append(
                "".join(
                    v.value
                    for v in node.values
                    if isinstance(v, ast.Constant) and isinstance(v.value, str)
                )
            )
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
    return out


def tables_named(source: str) -> set[str]:
    """The tables a source file's SQL strings name (lower case), less its CTEs."""
    texts = _sql(source)
    ctes = {m.group(1).lower() for t in texts for m in _CTE.finditer(t)}
    named = {m.group(1).lower() for t in texts for m in _SQL_TABLE.finditer(t)}
    return {t for t in named - ctes - _NOT_TABLES if "_" in t or t in TABLE_OWNERS}


def table_gaps(files: Iterable[Path] | None = None) -> list[str]:
    gaps: list[str] = []
    for path in files if files is not None else _module_files():
        for table in sorted(tables_named(path.read_text(encoding="utf-8")) - set(TABLE_OWNERS)):
            gaps.append(f"{path.relative_to(ROOT)}: `{table}` is not in TABLE_OWNERS")
    return gaps


def isolation_gaps() -> list[str]:
    generated = ISOLATION.read_text(encoding="utf-8") if ISOLATION.exists() else ""
    return [
        f"`{t}` is a tenant table missing from {ISOLATION.name}"
        for t in tenant_tables()
        if f'"{t}",' not in generated
    ]


def condition_gaps() -> list[str]:
    text = CONDITION_TESTS.read_text(encoding="utf-8")
    return [
        f"condition `{k}` has no allow/deny case in {CONDITION_TESTS.name}"
        for k in sorted(CONDITION_KEYS)
        if f'"{k}",' not in text
    ]


def decisions_in_use() -> set[str]:
    used: set[str] = set()
    for rule in RULES.values():
        for decision in rule.decisions.values():
            used.add("firm_setting" if decision.startswith("firm_setting") else decision)
    return used


def decision_gaps() -> list[str]:
    gaps: list[str] = []
    for decision in sorted(decisions_in_use()):
        tests = DECISION_COVERAGE.get(decision)
        if tests is None:
            gaps.append(f"decision `{decision}` has no tests listed")
            continue
        for test in tests:
            path = ROOT / test
            if not path.exists():
                gaps.append(f"decision `{decision}`: {test} does not exist")
            elif decision not in {"allow", "deny"} and decision not in path.read_text(
                encoding="utf-8"
            ):
                gaps.append(f"decision `{decision}`: {test} no longer names it")
    return gaps


def sweep() -> dict[str, list[str]]:
    return {
        "tables": table_gaps(),
        "isolation": isolation_gaps(),
        "conditions": condition_gaps(),
        "decisions": decision_gaps(),
    }


def render(found: dict[str, list[str]]) -> str:
    lines = ["| Check | Gaps |", "|---|---|"]
    for check, gaps in found.items():
        lines.append(f"| {check} | {len(gaps)} |")
    for check, gaps in found.items():
        if gaps:
            lines += ["", f"### {check}", "", *(f"- {g}" for g in gaps)]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args(argv)
    found = sweep()
    text = render(found)
    if args.report is not None:
        args.report.write_text(text, encoding="utf-8")
    print(text)
    return 1 if any(found.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
