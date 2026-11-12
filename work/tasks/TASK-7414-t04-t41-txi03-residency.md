---
id: TASK-7414
title: "T-04-T41: TXI-03 State residency and allocation states a-e in fixture mode on T6 two-pane (560, 806)"
spec: SPEC-649
acceptance_criteria: [AC-8]  # AC-8.1 to AC-8.5
risk_zone: green
status: in-review
branch: s38-t04-t41
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: T-04-T41
---

## Objective
TXI-03a-e render from scenarios, the tables foot to the acceptance checklist, cells deep-link to
TXI-01 fields and TXI-02 treatment 7, and Send is absent for the agent and for non-reviewers.

## Plan
- `apps/web/src/screens/TXI-03/`: `copy.ts` (the handoff spec's copy, facts, options, both tables
  and the notes, verbatim, no "$"), `Residency.tsx` (control bar, tally strip, cited facts, the ask
  card with the Recommended tag, Confirm for reviewers, the Ask the client sheet with Send for
  reviewers only, the allocation and credit tables, the loading skeleton; cells deep-link),
  `index.tsx`, `TXI-03.test.tsx` (14 pass).
- Gallery `registerScreen("TXI-03")` (a–e); `/tax-returns/$returnId/residency` draws frame a in
  fixture mode.
- Rollback: revert.

## Partial
- The live host (reading T-04-T39's `GET …/residency` and `GET …/state-allocation`, the SHL-10
  confirmation, POR-04's send) lands with the T-04 live-swap row.

## Progress log
- `2026-11-12` — Built (S38). 14 vitest pass (TXI-02 and TXI-03: 27); biome clean.
