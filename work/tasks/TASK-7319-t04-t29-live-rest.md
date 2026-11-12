---
id: TASK-7319
title: "T-04-T29 (rest): the review workspace's live layer: SSE invalidation topics for return counts with polling fallback, 409 blockers in words, DEC-24 Undo for approvals"
spec: SPEC-649
acceptance_criteria: [AC-13]  # the freeze window and the live path
risk_zone: green
status: in-review
branch: s37-t04-t29
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: T-04-T29
---

## Objective (row)
On staging Kevin approves documents, Samuel edits a field with a reason and signs off a section,
counts update on a second tab within 2 s, and every 409 renders its blocker in words.

## Built (reconciled with TASK-6828, DEC-3419, on main first)
TASK-6828 (#1720) landed the live hosts for TAX-04 to TAX-07 and TXI-01, `live-core.ts` (topic
keys, `useReturnLive`, `blockerWords`) and four invalidation kinds while this row was building.
The duplicate here (a `tax_return.counts_changed` event, `TAX-04/live.ts` with its own hooks,
`Blockers.tsx`, the fixture frame's stream) was dropped at the restack: `live.ts` would have
shadowed main's `live.tsx` in module resolution. What stays:
- `tax/return_events.py`: `sign_off.went_stale` and `issue.assigned` invalidate the engagement
  topic (both move "Review n"/"Issues n"; neither was registered). An entry another module
  registered is never replaced.
- `screens/TAX-04/live.tsx`: Approve's toast offers Undo for 10 s (DEC-24), which posts the
  reversal; the Unapprove button stays.
- Test: `screens/TAX-04/live.test.tsx` "an approval's toast offers Undo for 10 s".

## Partial
- TASK-6828's partials stand: the staging walk, TAX-04's 501 routes, and artboard parity under
  T-04-T47. The final-approval request and Unapprove of any live approval are built in TASK-7322
  (DEC-4320).

## Progress log
- `2026-11-12` — Built (S37). Prettier clean; vitest written, run at the end pass.
- `2026-11-12` — Restacked on main 46a8a067f: reconciled with #1720 (above). TAX-04 vitest 30
  passed.
