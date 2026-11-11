"""ADR-078 catch-up lane, 2028 Q1 part 1 (Q-03-T234, TASK-6882): independent declarations for
the S34 and S35 amber and red rows that reached the end of S35 without a suite of their own,
written apart from the rows, from the plan's words and the permission matrix.

Covered elsewhere already: P-05-T05, T06, T09 (P-05-T07's AC suites), P-05-T08 and T11
(`test_p05t11_engagement_activity.py`), P-09-T17, P-10-T28 (P-10-T31), R-02-T19 to T21
(R-02-T20), T-04-T23 and T-04-T24's own suites. Owed by their own rows, not here: A-07-T43
(goldens), A-07-T46 (the release and archive delta security test) and T-04-T42 (T-04-T14, T19
and T30). Here: the agent runtime's person commands (P-10-T29, T32, T33), the tax workbook's
protected bundle (T-05-T04, T06), the formula grammar (T-05-T07), the tax review registrations
and approvals (T-04-T15 to T17) and the A-07 post-release and archive acts (A-07-T36, T37, T42).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

import pytest
import yaml

BACKEND = Path(__file__).resolve().parents[3]
ROOT = BACKEND.parent
MOD = BACKEND / "src/abacus/modules"
CLIENTS = ("client_admin", "client_contributor")


def _matrix(module: str) -> dict[str, dict[str, str]]:
    doc = yaml.safe_load((ROOT / f"docs/architecture/permission-matrix/{module}.yaml").read_text())
    return cast(dict[str, dict[str, str]], doc["actions"])


def _refused_to_all_but_people(row: dict[str, str]) -> bool:
    return (
        row.get("agent", "deny") == "deny"
        and row.get("system", "deny") == "deny"
        and all(row.get(p, "deny") == "deny" for p in CLIENTS)
    )


# --- P-10-T29, T32, T33: a run's person commands -----------------------------------------------


@pytest.mark.parametrize(
    "action",
    [
        "agent_run.start",
        "agent_run.approve_plan",
        "agent_run.answer",
        "agent_run.control",
        "agent_run.sign_off",
    ],
)
def test_p10_the_runs_commands_are_people_only(action: str) -> None:
    assert _refused_to_all_but_people(_matrix("agents")[action])


def test_p10t33_every_command_requires_a_live_human_first() -> None:
    """Every public function taking a person's context reaches `require_live_human`, directly
    or through the module's own helpers (`_head`, `_decide`, `_live`)."""
    tree = ast.parse((MOD / "agents/commands.py").read_text())
    defs = {f.name: f for f in tree.body if isinstance(f, ast.FunctionDef | ast.AsyncFunctionDef)}

    def calls(f: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
        return {
            n.func.id
            for n in ast.walk(f)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }

    def reaches(name: str, seen: frozenset[str] = frozenset()) -> bool:
        if name == "require_live_human":
            return True
        if name in seen or name not in defs:
            return False
        return any(reaches(c, seen | {name}) for c in calls(defs[name]))

    # P-10-T33's commands (the reads, `plan_view` and `run_state`, are the routes' to authorise).
    commands = [
        "approve_plan", "edit_plan", "cancel_plan", "answer_question", "skip_question",
        "redirect", "retry", "stop", "sign_off", "create_feedback",
    ]  # fmt: skip
    assert set(commands) <= set(defs)
    assert [c for c in commands if not reaches(c)] == []


# --- T-05-T04, T06: the workbook's protected bundle --------------------------------------------


@pytest.mark.parametrize(
    "action",
    [
        "workbook.edit",
        "workbook.export",
        "workbook_import.create",
        "workbook_run.start",
        "tax_ownership.edit",
    ],
)
def test_t05_workbook_writes_are_people_only(action: str) -> None:
    assert _refused_to_all_but_people(_matrix("tax")[action])


def test_t05_the_agent_reads_the_workbook_only_in_its_task_scope() -> None:
    row = _matrix("tax")["workbook.read"]
    assert row.get("agent") == "task_scope"
    assert all(row.get(p, "deny") == "deny" for p in CLIENTS)


# --- T-05-T07: the formula grammar is closed ---------------------------------------------------


def test_t05t07_the_formula_module_never_evaluates_code_or_imports_a_module() -> None:
    source = (MOD / "workpapers/compute/formula.py").read_text()
    tree = ast.parse(source)
    imported = {
        (n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
    } | {
        a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    }
    assert imported <= {"__future__", "re", "dataclasses", "decimal", "enum", "typing", "abacus"}
    called = {
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert not called & {"eval", "exec", "compile", "__import__", "getattr", "float"}


# --- T-04-T15 to T17: review registrations, worksheets and document approvals -------------------


def test_t04t17_a_document_approval_is_a_persons_at_their_level() -> None:
    row = _matrix("tax")["document.approve"]
    assert _refused_to_all_but_people(row)
    levels = set(str(row["function_in"]).split(","))
    assert levels == {
        "preparer",
        "first_level_reviewer",
        "detail_reviewer",
        "manager_reviewer",
        "signer",
    }


def test_t04t16_the_agent_reads_worksheets_only_in_its_task_scope() -> None:
    row = _matrix("tax")["return_worksheet.read"]
    assert row.get("agent") == "task_scope"
    assert all(row.get(p, "deny") == "deny" for p in CLIENTS)


# --- A-07-T36, T37, T42: filings, the lock and post-lock additions -----------------------------


@pytest.mark.parametrize(
    "action",
    ["filing.update", "archive.lock", "archive_addition.create", "archive_addition.approve"],
)
def test_a07_post_release_and_archive_acts_are_people_only(action: str) -> None:
    assert _refused_to_all_but_people(_matrix("assurance")[action])


def test_a07t42_an_addition_refuses_the_agent_a_system_and_a_client_in_the_service() -> None:
    source = (MOD / "assurance/archive_additions.py").read_text()
    assert 'ctx.tenant.actor_kind != "human" or ctx.client' in source


def test_a07t37_the_lock_asks_a_fresh_second_factor_in_the_service() -> None:
    source = (MOD / "assurance/archive_lock.py").read_text()
    body = source[source.index("async def decide_lock") : source.index("async def start_lock")]
    assert "fresh_mfa_at(ctx)" in body
    assert "system_now()" not in body
