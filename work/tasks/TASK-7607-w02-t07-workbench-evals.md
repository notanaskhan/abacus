---
id: TASK-7607
title: W-02-T07 evals/workbench_assistant cases and frozen thresholds
plan_key: W-02-T07
spec: SPEC-653
acceptance_criteria: [AC-A1, AC-A3, AC-A6, AC-Q1, AC-P1, AC-V1, AC-V2, AC-D2]  # and INV-1, INV-2, INV-3
risk_zone: red
status: in-review
branch: w02-t07-evals
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
`workbench.assistant`'s eval suite, frozen before prompt work (chapter 10 §10.8.3): at least 60
cases on the J11 and WB-02 seed in W-02 §6's five groups, key cases repeated three times, W-02's
thresholds, and each grader proven by a seeded failing FakeModel trajectory.

## Plan
- `backend/src/abacus_tools/evals/workbench_assistant.py` (new): session-turn cases over P-10's
  trajectory models; P-10's twelve graders plus seven W-02 graders (`nothing_was_written`,
  `asks_when_ambiguous`, `one_question_per_turn`, `no_internal_ids_asked`, `plan_valid`,
  `tri_reads_zero`, `injection_contained`); `FROZEN` thresholds per group; per-group rates;
  `repeat` (3 of 3 on DE cases); suite-level `defaults` for tool argument specs.
- `evals/workbench_assistant/suite.yaml` (new, protected): 61 pass cases (read-only 20, ambiguity
  8, plans 15, scope 8, adversarial 10) and 21 seeded cases (every grader).
- `abacus_tools/evals/__main__.py`: `--agent workbench_assistant` (fake route only until T12/T25).
- Test `backend/tests/unit/evals/test_w02t07_workbench_assistant_suite.py`.
- Rollback: delete the suite and the module; nothing else reads them until W-02-T12.

## Deviations (DEC-4606)
- Real-route runs and the cost baseline row are W-02-T25's; the suite records the rule
  (baseline + 10 %) and the CLI refuses a real route until the capability exists (W-02-T12).
- "Stein and Ferris consent cases" and the walled and locked clients grade as scope cases with a
  designed notice and zero reads; the DF-04 copy is W-02-T22's.
- The suite is generated once from a script and committed as the record; edits are reviewed
  changes to the YAML.

## Progress log
- `2026-11-12` — Suite and graders built (DEC-4606). Run at the S40 end pass.
