---
id: TASK-7710
title: T-05-T47 S41 protected bundle (flag renewals, prompt variant flags, suite registration)
plan_key: T-05-T47
spec: SPEC-651
acceptance_criteria: [AC-15.1]
risk_zone: red
status: in-review
branch: t05-t47-protected-bundle
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
No T-05 or T-04 flag expires before the extension season ends, and every new capability has a
registered suite and a prompt variant flag.

## Plan (red, protected registries)
- `docs/architecture/feature-flags/tax.yaml` (+ regenerated `kernel/_flags.py`): three variant
  flags. `abacus_tools/codegen/eval_suites.py` (+ regenerated `ai_gateway/_eval_suites.py`):
  v2 specs and the recommender's tax modes.
- Rollback: revert; the capabilities lose eligibility (fail closed) and the flags disappear.

## Built
- The three prompt variant flags; the suites of tax.account_mapper, tax.agreement_reader,
  tax.memo_drafter (and the other v2 capabilities with suites) and the two recommender modes
  are registered for the gateway's eligibility check.

## Partial
- Flag renewals: none needed in repo time (all six expire 2027-05-07; DEC-4713). The plan's
  Aug 14, 2028 date maps to the flag calendar's renewal before their last train.
- Fake-model responders for the three new prompts are the evals' (T-05-T30 recorded outputs);
  real-model runs are T-05-T64's.

## Progress log
- 2026-11-13: registries edited and regenerated; tests not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4713 | the bundle's contents and the renewal call | no |
