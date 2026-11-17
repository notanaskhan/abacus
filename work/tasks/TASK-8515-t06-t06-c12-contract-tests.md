---
id: TASK-8515
title: "T-06-T06: C12 contract tests for both consumer shapes (AUD-38 and CLS-12)"
spec: SPEC-702
acceptance_criteria: [AC-28, AC-29, AC-31]
risk_zone: amber
status: in-review
branch: t06-t06-c12-contract-tests
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: T-06-T06
---

## Objective
Spec section: docs/plan/epics/T-06.md §8. C12 contract tests for AUD-38 and CLS-12: pytest against the stub plus TypeScript fixture assertions, wired into the provider's CI; fail if any account choice lacks a source or a close_lock payload omits the locked-close reference.

## Plan (amber)
1. Contract: review accounts must name a source; preview and landing carry `locked_close_id`, required for close_lock (and, on the preview, only for it).
2. C12 models renamed TbHandoff* (a generic PreviewOut collided in the generated client).
3. `backend/tests/contracts/c12_tb_handoff/test_t06t06_c12_consumers.py` (11 tests) and `apps/web/src/fixtures/contracts/c12-tb-handoff.contract.test.ts`.
4. Rollback: revert.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5515). pytest 11 passed (run once); tsc clean on the fixture. Gates and tests run once at the S49 end pass (build first, test last).
