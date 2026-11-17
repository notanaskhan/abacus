---
id: TASK-8518
title: "T-06-T09: Consumer contract tests for the T07 and T08 stubs"
spec: SPEC-702
acceptance_criteria: [AC-1, AC-16, AC-34]
risk_zone: amber
status: in-review
branch: t06-t09-consumer-tests
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: T-06-T09
---

## Objective
Spec section: docs/plan/epics/T-06.md §8. Consumer contract tests for T07 and T08 (pytest plus TypeScript fixture assertions); assert every golden figure named in T07 and fail on a missing classification tag.

## Plan (amber)
1. `backend/tests/contracts/t06_entity_depth/test_t06t09_consumers.py`: 733,500 = 169,500 + 360,000 + 204,000; 46.0 + 31.5 + 22.5 = 100.0 with each share matching its numerator; PTET 64,096; Σ box 2 = 1,231,600; outside basis 17,943,095 with Pell Street II off 28,595; every field of every TaxDepth* and Relationship* model classified; return figures TRI; a walled graph omits the Feld household with no count; every operation keeps its action and 501.
2. `apps/web/src/fixtures/contracts/t06-entity-depth.contract.test.ts` typed by the generated client.
3. Fix the suite found: optional money fields (`Money | None`) lost their tag inside the union; they are `MaybeMoney`, tagged outside it.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5518). pytest 82 passed (run once); tsc clean. Gates and tests run once at the S49 end pass (build first, test last).
