---
id: TASK-2527
title: T-02-T29 ADR-078 independent AC tests for T-02's tax-return backend
spec: SPEC-502  # AC-8, AC-10, AC-11, AC-19, AC-20; T-02 §3.1 to §3.4
acceptance_criteria: [AC-8, AC-10, AC-11, AC-19, AC-20]
risk_zone: amber
status: done
epic: T-02
plan_key: T-02-T29
branch: s20c-t02-t29
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-10-31
updated: 2026-10-31
---

## Objective
Independent tests for T-02-T07, T09, T10, T13 and T18: guard table, wall-safe tiles and totals,
due-date pins, overview figures only from approved imports, consent-gated suggestions with zero
gateway calls, footing.

Acceptance (backlog row): "Tests written in notanaskhan's session pass on main and fail if a
guarded transition succeeds without its gate." (Solo edition: written from the SPEC and epic.)

## Plan
- `backend/tests/integration/test_t02t29_tax_returns_independent.py` on T-02-T09's board seed.

## Progress log
- `2026-10-31` — Built on `s20c-t02-t29` off main. 10 passed.
