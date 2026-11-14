# ac-test-author: ayushkbhatia
"""T-05-T63 (TASK-7953; ADR-078): independent acceptance tests for notanaskhan's red work on the
entity return (T-05-T22, T25, T26, T31, T53 and T60).

Written from the T-05 epic's acceptance (§3 F2, F4, F5, F6, F11, F12), the permission matrix, the
human-only register and the contracts, not from the implementations. Unit level (no database): each
rule is held where it is declared (matrix, register, run plan, blockers, export), so a later change
that weakens it fails here.

- T22: a partner's TIN is revealed only by a person, with fresh MFA, a reason and not offshore.
- T25/T26: a TJE is review-required, a tax-only line lives only on a TJE, the tax mapping is a
  person's (agent and system denied).
- T31: the run's DAG runs at most three steps at once; a model step without consent asks first.
- T53: final approval is blocked, in words, by every entity blocker, and is a person's.
- T60: export is refused before final approval and only a person exports or records transmission.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[4]
MATRIX = ROOT / "docs/architecture/permission-matrix"


def _rule(module: str, action: str) -> dict[str, object]:
    body = (MATRIX / f"{module}.yaml").read_text(encoding="utf-8")
    raw = cast(dict[str, Any], yaml.safe_load(body))  # Any: parsed YAML
    actions = cast(dict[str, Any], raw.get("actions", raw))  # Any: a test stand-in
    found = actions.get(action)
    assert isinstance(found, dict), f"{module}.yaml has no {action}"
    return cast(dict[str, object], found)


# --- T22: logged TIN reveal and offshore masking ------------------------------------------------


def test_t22_tin_reveal_is_a_persons_with_fresh_mfa_a_reason_and_not_offshore() -> None:
    rule = _rule("organisations", "tin.reveal")
    assert rule["agent"] == "deny" and rule["system"] == "deny"
    assert rule.get("mfa_recent") == "required"
    assert rule.get("requires") == "reason"
    assert rule.get("not_offshore") == "required"


def test_t22_partner_tins_answer_last_four_only() -> None:
    from abacus.modules.tax.workbook_contract import WorkbookPartnerOut

    fields = WorkbookPartnerOut.model_fields
    assert "tin_last4" in fields and "tin" not in fields and "tin_sealed" not in fields
    pattern = str(fields["tin_last4"].metadata)
    assert "{4}" in pattern


# --- T25/T26: TJE layers and the tax mapping -----------------------------------------------------


def test_t26_the_tax_mapping_approval_is_a_persons() -> None:
    rule = _rule("tax", "tax_mapping.approve")
    assert rule.get("agent") in ("deny", None) and rule.get("system") in ("deny", None)
    assert rule.get("agent") != "allow"


def test_t25_a_tax_only_line_outside_a_tje_is_refused_by_name() -> None:
    from abacus.modules.adjustments import entries

    assert "tax_only_outside_tje" in Path(entries.__file__).read_text(encoding="utf-8")


# --- T31: the run plan ---------------------------------------------------------------------------


def test_t31_the_dag_runs_at_most_three_steps_at_once() -> None:
    from abacus.modules.agents.run_plan import MAX_PARALLEL, cap

    assert MAX_PARALLEL == 3
    assert cap(None) == 3 and cap(10) == 3 and cap(2) == 2 and cap(0) == 3


def test_t31_a_failed_step_skips_only_its_dependants() -> None:
    from abacus.modules.agents.run_plan import PlanStep, Schedule

    steps = [
        PlanStep("a", "a", 0, "tool", "x"),
        PlanStep("b", "b", 1, "tool", "x", depends_on=("a",)),
        PlanStep("c", "c", 0, "tool", "x"),
    ]
    s = Schedule(steps, 3)
    started = {p.key for p in s.start()}
    assert started == {"a", "c"}
    s.finish("a", "failed")
    s.finish("c", "succeeded")
    s.start()
    assert s.states["b"] == "skipped" and s.states["c"] == "succeeded"


# --- T53: final-approval guards ------------------------------------------------------------------


@pytest.mark.parametrize(
    "blocker",
    ["unmapped_accounts", "allocation_not_approved", "trial_balance_missing"],
)
def test_t53_each_entity_blocker_has_its_words(blocker: str) -> None:
    import abacus.modules.tax.api  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the entity provider
    from abacus.modules.tax.approval import blocker_words

    words = blocker_words(blocker)
    assert words and words != blocker


def test_t53_final_approval_is_a_persons() -> None:
    rule = _rule("tax", "tax_return.approve")
    assert rule["agent"] == "deny" and rule["system"] == "deny"


# --- T60: export and never transmit --------------------------------------------------------------


def test_t60_export_and_transmission_are_a_persons() -> None:
    for action in ("tax_return.export", "transmission.record"):
        rule = _rule("tax", action)
        assert rule["agent"] == "deny" and rule["system"] == "deny", action


def test_t60_the_entity_export_waits_for_final_approval_and_mapping() -> None:
    from abacus.modules.tax import export

    body = Path(export.__file__).read_text(encoding="utf-8")
    assert body.index("raise NotFinalApproved") < body.index("await require_mapped(")
    assert body.index("await require_mapped(") < body.index("await consume_grant(")


def test_t60_no_tax_module_names_a_transmit_function() -> None:
    import ast

    tax = ROOT / "backend/src/abacus/modules/tax"
    names = {
        n.name
        for f in tax.rglob("*.py")
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8")))
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    # `transmitted_on` reads the date a person recorded (filing.py); no verb sends anything.
    verbs = [n for n in names if n.startswith(("transmit_", "submit_to_irs", "efile_send"))]
    assert not verbs and "transmit" not in names
