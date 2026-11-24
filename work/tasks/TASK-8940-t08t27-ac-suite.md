---
id: TASK-8940
title: "T-08-T27: ADR-078 independent AC suite #1 for T-08"
spec: SPEC-710
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-t08t27
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: T-08-T27
---

## Objective
ADR-078 independent AC suite #1 for AY's amber T-08 code: cohort approval and idempotent execution, deadline rules and risk tiers, walls and admin metadata, two-year flags, acceptance and staleness.

## Done
- backend/tests/integration/backfill/test_t08t27_ac_suite.py (4 tests): AC-18 portal 403 on /v1/filing-deadlines*; AC-24 preparer refused accept (403, nothing written) and another firm 404; AC-36/34 flag-off 404 on two-year and filing deadlines
- Earlier T-08 service suites (t08t09/t10/t11/t12/t20/t44) hold AC-1..AC-15 and AC-21..AC-25 at the service boundary

## Progress log
- `2026-11-23` — 2026-11-23: written from SPEC-710 §5 and the matrix only; follows DEC-137 (flag expiry) and DEC-43. Integration run in the end pass.
