---
id: TASK-2927
title: S24 end pass CI repair; firm initial bundle budget 300 KB (founder decision)
spec: SPEC-000  # #1074's red CI; chapter 04 §1 rule 13 and §11; scripts/bundle-budget.mjs
acceptance_criteria: [AC-1]  # #1095's CI run green on the S24 end-pass tree
risk_zone: green
status: in-review
epic: F-05
plan_key: F-05-T17
branch: s24-end-pass-fix
worktree: scratchpad worktree of this session (branch s24-end-pass-fix)
created: 2026-11-02
updated: 2026-11-02
---

## Objective
Make the S24 end-pass tree (#1074) green so it can land on main.

## Scope
Root causes and fixes are in #1095's body and DEC-1972 to DEC-1975. The firm initial budget
goes from 250 KB to 300 KB (DEC-1975): `BUDGETS.firm` in `apps/web/scripts/bundle-budget.mjs`,
its two test files and chapter 04's budget lines. Rollback: revert.

## Progress log
- 2026-11-02: fixes built; unit shard 2, ci-contracts, journeys, ci-frontend and check-fast run
  locally. Firm initial 260.0 KB was the only stage-1 red; Ayush raised the budget to 300 KB.
