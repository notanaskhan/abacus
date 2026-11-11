---
id: TASK-6828
title: "T-04-T29 (continued): live hosts for TAX-04, TAX-05, TAX-06, TAX-07 and TXI-01; return-count invalidations; refusal words"
spec: SPEC-649
acceptance_criteria: [AC-4]
risk_zone: amber
status: in-progress
branch: s36f-t04-t29
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-12
updated: 2026-11-12
plan_key: T-04-T29
---

## Objective (row)
Fixture-to-live swap for the P0 screens on staging: live RW-1 and WS-1 routes, SSE invalidation
topics for return counts with polling fallback, blocked states from 409 blockers, DEC-24 Undo for
approvals. TASK-6822 built the issue detail's read side; this builds the rest that runs without
staging.

## Plan (amber)
- SPA: `screens/TAX-04/live-core.ts` (topic keys, `useReturnLive`, `blockerWords`), live hosts
  `TAX-04/live.tsx`, `TAX-05/live.tsx` (TXI-01 via `?ws=`), `TAX-06/live.tsx`, `TAX-07/live.tsx`,
  mounted by `routes/firm/tax-review.tsx` on live builds only (lazy chunks).
- Server: `review.events.IssueStatusChanged` emitted on create, move, system resolve and resolve
  on approval; `tax.review_tree.DocumentApprovalChanged` on approve and reverse; six
  invalidations in `notifications/realtime.register`; `section_id` on `WorksheetSectionOut`
  (additive, `docs/contracts/tax-worksheets.md`); client regenerated.
- Tests: `apps/web/src/screens/TAX-04/live.test.tsx` (13), `tests/unit/tax/test_t04t29_live_counts.py`,
  `tests/integration/test_t04t29_live_counts.py`; the worker's exact event set.
- Rollback: the routes' live branch is behind `tax.review_workspace` already; reverting the
  commit removes the events (no migration).

## Partial (flagged)
- The staging walk: staging is not up.
- The final-approval request: it waits on SHL-12 h's assignee picker. The route and its words
  are ready.
- Unapprove covers only approvals made in this session; the tree carries no approval id.
- TAX-07 titles read the action ("Document · approved"), not T-04's kind verbs.
- TAX-04's leadsheets, links and K-1 matrix routes still answer 501 (T-04-T22 and later rows).
- The live hosts reuse the kit, not the artboards' exact layout; T-04-T47 owns parity.

## Progress log
- `2026-11-12` — Built. TAX-04 live vitest 13 passed; the unit test 4 passed. Integration runs
  at the end pass. DEC-3419.
