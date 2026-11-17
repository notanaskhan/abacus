---
id: TASK-8507
title: "C-02-T08: Consumer contract tests on the C8 v2 and C20 v2.1 stubs"
spec: SPEC-700
acceptance_criteria: [AC-3, AC-4]
risk_zone: red
status: in-review
branch: c02-t08-consumer-contract-tests
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: C-02-T08
---

## Objective
Spec section: docs/plan/epics/C-02.md §8. pytest and TypeScript fixture assertions for CLS-07 a-g, CLS-11 a-e and the POR-08 card B posted refs, so a breaking posting, console or write-grant schema fails before a screen task starts.

## Plan (red)
1. `backend/tests/contracts/c08_adjustments/test_c02t08_posting_consumer.py`: CLS-07 a tallies foot by code (5 · 34,920.00 = 20,020.00 + 14,900.00), c2 dry run 35,300.00, d QBO 48213-48218, e failed alone, f no policy status, g no Post for attest; every operation declared with its action and 501, agent denied.
2. `backend/tests/contracts/c20_integrations/test_c02t08_w1_consumer.py`: CLS-11 a tiles and pane, b the July batch, c/d health states, POR-16 consent copy v2 only, client owner alone grants with fresh MFA, firm switch security_admin alone; every operation declared.
3. `apps/web/src/fixtures/contracts/c08-posting.contract.test.ts` and `c20-w1.contract.test.ts`: typed with the generated client, validated against OpenAPI.
4. The C8 v2 stub now types statuses with the generated StrEnums (no posting-status string constants in adjustments code).
5. Amended A-06-T17's `test_no_matrix_action_posts` under ADR-344: exactly `posting_batch.post` is allowed, and only with agent/system denied, fresh MFA, independence and the W1 entry off, attest refused and policy never.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5507). Ruff clean; tsc clean on the new fixtures; suites run at the end pass. Gates and tests run once at the S49 end pass (build first, test last).
