"""Independent AC tests for A-05's red work so far (A-05-T29; ADR-078): T12 and T13 (the EBP modes
on the one section drafter), T15 (migration 0642), T18 (census sealing and field reveal) and T21
(`ebp_attribute`).

Written apart from those tasks: the capability never adopts, signs or raises (no tools, and the
deciding actions are human-only), its inputs and prompts never carry an SSN or a date of birth,
the testing tables are tenant-scoped with insert-only results, and a reveal is a person's,
onshore, with a fresh second factor. The database behaviour itself is T15's and T18's suites;
these hold the declarations to it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import pytest
import yaml

BACKEND = Path(__file__).resolve().parents[3]
ROOT = BACKEND.parent
SPEC = cast(
    dict[str, object],
    yaml.safe_load(
        (BACKEND / "src/abacus/modules/agents/specs/workpapers.section_drafter.yaml").read_text()
    ),
)
PROMPTS = BACKEND / "src/abacus/ai_gateway/prompts"
MIGRATION = next((BACKEND / "migrations/versions").glob("0642_*.py")).read_text()
HUMAN_ONLY = (ROOT / "docs/architecture/human-only-actions.yaml").read_text()
EVIDENCE = cast(
    dict[str, dict[str, dict[str, str]]],
    yaml.safe_load((ROOT / "docs/architecture/permission-matrix/evidence.yaml").read_text()),
)["actions"]
ASSURANCE = cast(
    dict[str, dict[str, dict[str, str]]],
    yaml.safe_load((ROOT / "docs/architecture/permission-matrix/assurance.yaml").read_text()),
)["actions"]
PII = re.compile(r"\b(ssn|social security|date[_ ]of[_ ]birth|dob|birth_?date)\b", re.IGNORECASE)
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def test_the_capability_has_no_tools() -> None:
    """It writes suggestions only: no tool that adopts, signs or raises."""
    assert SPEC["tools"] == []


def test_every_ebp_mode_is_on_the_one_spec() -> None:
    modes = cast(dict[str, object], SPEC["modes"])
    assert {"ebp_provisions", "ebp_attribute", "ebp_reconcile"} <= set(modes)


@pytest.mark.parametrize(
    "prompt",
    sorted(p for p in PROMPTS.glob("workpapers.section_draft*ebp*/*.txt")),
    ids=lambda p: f"{p.parent.name}/{p.name}",
)
def test_no_ebp_prompt_asks_for_an_ssn_or_birth_date(prompt: Path) -> None:
    text = prompt.read_text()
    assert SSN.search(text) is None
    for line in text.splitlines():
        if PII.search(line):
            # A prompt may only forbid or mask them ("never an SSN", "are masked"), never ask
            # for or carry one.
            assert re.search(r"\b(never|not|no|masked)\b", line, re.IGNORECASE), line


def test_ebp_prompts_exist() -> None:
    assert list(PROMPTS.glob("workpapers.section_draft*ebp*/*.txt"))


@pytest.mark.parametrize(
    "table",
    [
        "ebp_population_queries",
        "test_attribute_results",
        "attribute_tests",
        "ebp_participants",
        "ebp_source_imports",
    ],
)
def test_the_testing_tables_are_tenant_scoped(table: str) -> None:
    assert f'"{table}"' in MIGRATION
    assert "tenant_table(op, table)" in MIGRATION
    assert "REVOKE DELETE, TRUNCATE" in MIGRATION


def test_results_and_population_queries_are_insert_only() -> None:
    assert '_INSERT_ONLY = ("test_attribute_results", "ebp_population_queries")' in MIGRATION
    assert "insert_only(op, table)" in MIGRATION


def test_marking_an_attribute_result_is_human_only() -> None:
    assert "action: attribute_result.marked" in HUMAN_ONLY


def test_a_reveal_is_a_persons_onshore_with_a_fresh_factor() -> None:
    row = EVIDENCE["pii.reveal"]
    assert row["agent"] == "deny"
    assert row["system"] == "deny"
    assert row["client_admin"] == "deny"
    assert row.get("not_offshore") == "required"
    assert row.get("mfa_recent") == "required"


@pytest.mark.parametrize("action", [a for a in ASSURANCE if a.startswith("ebp_")])
def test_every_ebp_write_refuses_the_system_principal(action: str) -> None:
    row = ASSURANCE[action]
    if action.endswith((".read", ".render")):
        return
    assert row.get("system") == "deny", action
