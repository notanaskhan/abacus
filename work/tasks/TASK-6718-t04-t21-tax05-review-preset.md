---
id: TASK-6718
title: "T-04-T21: TAX-05 Review preset states a-f in fixture mode on T3 452x3"
spec: SPEC-649
acceptance_criteria: [AC-2]
risk_zone: green
status: in-review
branch: s35-t04-t21
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: T-04-T21
---

## Objective
TAX-05a-f render from scenarios, approving Statement A moves Review 37 to 36 with toast 'Approved for manager review · Samuel Ito', and the matrix foots 307,900 / 4,600 / 1,550 / 150,000 and Item L 1,912,500.

## Plan
`apps/web/src/screens/TAX-05/` (new): `copy.ts` (the handoff's tree rows, matrix rows with the 2024
column, worksheet rows, copy verbatim), `Review.tsx` (`ReviewPreset` on three 452 panes: tree with
Flag, Check and Info micro-pills at the viewer's level, the draft K-1 with box 5 and the Interest
Income row lit together, the Sch E – K-1 matrix or the Worksheets rows, the All approved banner and
"Request final approval…" disabled with its reason while the Draft K-1 exists), `TAX-05.test.tsx`.
`docs/screens/TAX-05.md` status fixture.

## Partial
- The tree draws the handoff's visible rows (the top of the 41), not all 41; the counts come from
  the frame (37, 36) as the server's `review_count` would. SHL-09, SHL-12 h, SHL-15 and TAX-06 are
  the host's overlays (callbacks here); the live wiring is with the TAX-04 host.

## Progress log
- `2026-11-10` — Built; tests written, not run (end pass).
