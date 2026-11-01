---
id: TASK-2802
title: A-04-T09 eval suite evals/decision_recommendation
spec: SPEC-620
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-04
plan_key: A-04-T09
branch: s23-a04-t09 (stacked on s23-a04-t08)
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "The suite runs in CI on the fake model, a recommendation outside 1.0%-2.0% fails the
  build, and N merges the protected suite.yaml before the prompt." (Solo edition: the builder
  merges it; the suite lands before A-04-T15's prompt.)

## Plan (red)
- Files: `evals/decision_recommendation/suite.yaml` (protected, new), runner
  `abacus_tools/evals/decision_recommendation.py`, CLI dispatch in `abacus_tools/evals/__main__.py`,
  `make evals-recommend-fast` in `check` and CI stage 3, `assurance/compute/**` in the stage-3
  path filter. No migration, matrix, flag or registry edit; no model call.
- Tests: `tests/unit/tools/test_a04t09_decision_recommendation.py` — the fake answers pass every
  threshold; negative controls (out of range, custom, stray number, unknown fact, echoed injection,
  exfil link) fail the gate; suite validation.
- Rollback: revert; nothing reads the suite but the runner.

## Progress log
- `2026-11-01` — built, ruff clean. Tests and `make evals-recommend-fast` run at the S23 end
  review. Stacked on A-04-T08 (the engine).

## Decisions made during this task
DEC-1852.
