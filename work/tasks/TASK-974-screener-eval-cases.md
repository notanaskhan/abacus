---
id: TASK-974
title: Screener evaluation cases from the F-04 scenario documents - Northwind EBP and Granite Peak trial balances, adversarial account names (Q-02-T26)
spec: SPEC-005
acceptance_criteria: [AC-4]
risk_zone: amber
status: in-review
epic: Q-02
plan_key: Q-02-T26
branch: s5-screener-evals
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"The screening suite gains at least 40 labelled cases including 10 adversarial ones, and validate_docs and the suite loader accept it unchanged in thresholds" (Q-02-T26; Q-02 §7 table, `evals/screening/suite.yaml`).

## Plan
- `abacus_tools.evals.cases`: `SCENARIO_MUTATIONS`, 40 named mutations registered into `MUTATIONS` and `MUTATION_CATEGORIES`. Each starts from the stack's synthetic trial balance and applies one of two scenario charts:
  - the Northwind Robotics 401(k) Plan ("Northwind EBP", A1);
  - Granite Peak Outdoor Supply (A2, FYE June 2026).
  Each chart renames lines by account code and keeps every amount. Then it applies the existing flaws, or an instruction carried in an account name (`untrusted_inputs: [account_names]`). Names and the Granite Peak fiscal year come from the Brightwater Hale seed (`scenarios/brightwater_hale/audits.py`). No amount is invented.
- `evals/screening/suite.yaml` v2: 40 new cases in the existing format, with every v1 case kept. Thresholds, repeats, pass rate, calibration tolerance and cost limit are unchanged. The version moves to 2 because the case set changed, as `upload_review` did. `_eval_suites.py` is regenerated with `make regenerate`.
- Tests first: `tests/unit/tools/evals/test_screening_scenarios.py`.
- Rollback: revert the commit. No run has been recorded against v2.

## What changed
- 40 cases:
  - 11 Northwind EBP: ready, incomplete, the sponsor's corporate TB, prior plan year, interim, unbalanced, does not tie, duplicate, altered, EUR, and a recordkeeper account-balances report instead of a TB;
  - 12 Granite Peak: ready, incomplete, its 401(k) plan's TB, its own July to June fiscal year against the calendar request, prior year, interim, unbalanced, a transposition, does not tie, duplicate, CAD, unreadable;
  - 17 adversarial: prompt injection, addressed instruction, tag breakout, role play, a JSON breakout, a system override, a stepwise injection across three names, two formula injections, two lookalikes, unicode deception, an oversized name, and four that pair an instruction with a real flaw (incomplete twice, unbalanced, wrong entity).
- The suite now has 61 cases.
- Key cases added: 2, the incomplete-with-instruction pairs. A real run's attempt count stays well inside the unchanged $5 cost limit at the spec's per-attempt cap.
- 87 new tests. Every code-caught label (`failed`, `failed_validation`) and every `screened` label is checked against the parser and validator the pipeline runs (`parse_trial_balance`, `ledger.validate`). Each case claims exactly what its mutation injects. The scenario names and periods equal the seed's. Charts keep every amount. No injection case is labelled ready when it carries a real flaw. The existing suite tests (scripted answers pass the gate, the negative control fails it, the mutations never change their input) pass unchanged.
- Only the loader and validation tests were run. `make evals` was not, and no model was called.

## Gotchas and discoveries
- **The screener cannot see the entity.** `fake_format.parse_trial_balance` drops `entity`, and the screener's context carries the period, totals and account names only. Every `wrong_entity` case is therefore labelled correctly (needs revision) but can be caught only by the fake's scripted answer. That covers v1's `wrong_entity` and v2's `northwind_ebp_sponsor_tb`, `granite_peak_plan_tb` and `granite_peak_wrong_entity_with_instruction`.
- In Q-02-T28's first real run, these four are likely misses against `needs_revision_recall ≥ 0.97`. The fix belongs in the context builder: give the screener the engagement's entity and the document's entity, as code-checked facts. Do not drop the cases or lower the threshold. Raise it in T28.

## Progress log
- 2026-10-23: `tests/unit/tools/evals/` (146), `tests/unit/agents/test_agent_specs.py`, `make check-generated` and `validate_docs` pass. Ruff and pyright are clean on the changed files.
