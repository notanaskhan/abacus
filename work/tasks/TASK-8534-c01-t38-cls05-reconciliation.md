---
id: TASK-8534
title: "C-01-T38: CLS-05 Reconciliation states a-g"
spec: SPEC-655
acceptance_criteria: []
risk_zone: green
status: in-review
branch: c01-t38-cls05
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: C-01-T38
---

## Objective
CLS-05 states a, a2, a3, b, c, d (read-only), e, f, g on T3 two-pane: rec sheet with tally strip and aging block; statement viewer lighting rec line and statement line both ways; account picker; Propose AJE drawer with the agent draft and a human Propose; blocked SHL-12; stale pill; carry forward; savings-requested empty viewer. AC: hover and keyboard focus light the pair both ways, the drawer's Propose is the only path to a proposed entry, Reconciled shows only after the L1 sign-off.

## Plan (green)
1. fixtures/seed/close-reconciliation.ts: states b (Run 1, off 380.00), c (AJE-06 proposed), d (signed, recorded JE 48218, #2281 carried forward), g Savings 4436 (statement requested Sep 1), the 4410 register; scenarios/CLS-05.ts
2. screens/CLS-05: copy, index (CLS05 on closeReconciliationOptions and closeRegisterOptions; match lighting by region; Drawer with the agent draft via AgentText and a human Propose; Dialog listing sign-off blockers), CLS-05.test.tsx; screens/kit-close-data.ts re-exports the draft
3. routes/firm/closes.tsx: /closes/$closeId/accounts/$accountRef renders CLS-05

## Progress log
- `2026-11-17` — Built; CLS-05 vitest 15 pass (CLS-04 + CLS-05 31), tsc and eslint clean. Item labels compose kind, check number and date: the reconciliation contract carries no payee, so 'Highline Espresso Service' and the other payees show only in the Detail register. Purple tracing uses the match-bg / match-line tokens. The SHL-12 sign-off itself and SHL-10 review open in the live swap (C-01-T43). Gates and tests run once at the S49 end pass (build first, test last).
