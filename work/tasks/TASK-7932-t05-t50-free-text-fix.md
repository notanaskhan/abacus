---
id: TASK-7932
title: T-05-T50 rest: free-text workbook fix instructions (model judges cells, code checks and computes)
plan_key: T-05-T50
spec: SPEC-652
acceptance_criteria: [AC-3]
risk_zone: red
status: in-review
branch: t05-t50-free-text-fix
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Finish T-05-T50's model partial: free-text fix instructions outside the closed grammar get a model judgment of which cells they name, every answer checked by code, every value computed by code.

## Done
- Prompt `issues.fix_runner.workbook@v1` (a mode of `issues.fix_runner`, registered in `EXTRA_MODES` and `_eval_suites.EVAL_SUITE_MODES`: admitted only on its own passing evaluation).
- `workbook_fix.judge` (gateway, the spec's tier, budget and routes; instructions untrusted) and `kept`: a cell survives only on one of the form's sheets, as an address, with an amount the person wrote verbatim (cell refs, sheet keys and form designators are not amounts). Values from `new_value`, as for the grammar. Refused call or nothing kept: `no_cell_named`.
- The grammar runs first; the model is asked only when it names nothing.
- `evals/workbook_fix/` (frozen thresholds, five pass and four seeded cases) and `abacus_tools.evals.workbook_fix`; `python -m abacus_tools.evals --agent workbook_fix`.
- Tests: kept/dropped answers, the proposal's code-computed value, grammar first, refusal, the mode's registration, the frozen suite and a lowered threshold refused.

## Partial
- The real-model evaluation run (eligibility) is a deploy-time run on staging (`make evals`), not run here.

## Progress log
- 2026-11-13: built in the S42 partials round; tests written, run at the partials end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4927 Free-text fixes: a mode of issues.fix_runner, the answer checked by code | The model names cells only; number provenance and computation stay in code (ADR-050) | no |
