---
id: TASK-7513
title: T-04-T53 hardening (mutation floor, p95 budgets) for the individual return
plan_key: T-04-T53
spec: SPEC-649  # T-04 §10 (ADR-079)
acceptance_criteria: [AC-10]  # nightly mutation meets the protected floor; the p95 budgets hold on staging
risk_zone: red
status: in-review
branch: t04-t53-hardening
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
A mutation floor (ADR-079, target at least 75%) on `tax/compute/individual` and the tax tools,
with survivor triage; p95 budgets (review tree ≤ 300 ms for 41 documents, worksheet fields ≤ 250
ms, approve ≤ 500 ms) under the busy-season profile.

## Plan
- `abacus_tools/quality/mutation.py`: scope `tax/individual` (the individual engines, `tax/tools.py`,
  `tax/agent_tools.py`), matched before the broad `compute` glob.
- `backend/mutation-thresholds.yaml` and `coverage-thresholds.yaml` (protected): `tax/individual: 0`,
  raised to the first weekly baseline after triage (the P-10-T52 pattern, DEC-4402);
  `pyproject.toml` `only_mutate` lists the files.
- `abacus_tools/loadtest/t04_budgets.py`: the three budgets and `breaches`.
- `tests/unit/tax/test_t04t53_hardening.py`: scope mapping, floor present, budgets, and boundary
  tests killing the likely survivors (183 vs 184 days, abode, the credit's lesser-of, half-up,
  both QBI arms and the at-limit case, largest remainder, PTET half-up, IT-201 due/overpaid/exact).

## Partial
- The floor is set to 0 until the first nightly baseline; reaching 75% and the staging p95 run need
  the nightly mutation job and staging.

## Progress log
- `2026-11-12` — Built (DEC-4513). Tests run at the S39 end pass.
