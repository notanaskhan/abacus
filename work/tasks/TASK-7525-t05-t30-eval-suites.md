---
id: TASK-7525
title: T-05-T30 eval suites part 2 (tax.memo_drafter; recommender convention_706d and section_754)
plan_key: T-05-T30
spec: SPEC-651  # T-05 §6.4
acceptance_criteria: [AC-1]  # both suites have frozen thresholds and pass on the fake model before N starts the prompts
risk_zone: red
status: in-review
branch: t05-t30-eval-suites
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
`evals/tax_memo_drafter` (number provenance, citation verification and coverage, section
completeness, human-edited sections untouched, regenerate-affected-only, judge calibration) and
decisions.recommender cases for `convention_706d` and `section_754`, frozen before prompt work.

## Plan
- `backend/src/abacus_tools/evals/tax_entity_part2.py`: models, graders, `FROZEN`, `run_suite`,
  `main`; `__main__` dispatches `--agent tax_memo_drafter | tax_recommender_modes`.
- `evals/tax_memo_drafter/suite.yaml` (Ridgeline memo cases, a seeded case per grader, a
  calibration set) and `evals/tax_recommender_modes/suite.yaml` (Monthly for the 6/30/2025 Pell
  Street transfer citing Assignment §3; §754 against the 28,595 placeholder; seeded cases).
- Test `backend/tests/unit/evals/test_t05t30_suites.py`.

## Partial
- `tax.memo_drafter` itself is T-05-T48 and the recommender's two modes ride T-05's later rows:
  these are the recorded fake-model outputs the prompts must meet. The calibration set's CPA
  labels stay `pending_cpa`; real-route runs need the evaluation account.

## Progress log
- `2026-11-12` — Suites written (DEC-4525); both pass on the fake model. Tests run at the end
  pass.
