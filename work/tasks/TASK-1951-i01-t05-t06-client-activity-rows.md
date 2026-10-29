---
id: TASK-1951
title: "I-01-T05/T06 remainder: HOME-01a's client activity rows in the fixture and the screen"
spec: SPEC-313
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: I-01
plan_key: I-01-T05
branch: s11p-i01-t06
worktree: ../abacus-s11p
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Close the I-01-T05/T06 partials: T11's right column is on main (S12) and T12's projection is in
review (#591), so the a frame's six activity rows render verbatim from the fixture, and live rows
draw a sentence from their code. T24's h and i bands stay S35.

## Plan
- Contract (additive): `ClientActivityOut.labels` (read-time names); `make generate`.
- SPA: `activityLines` per code, copy in `screens/HOME-01/copy.ts`, icons keyed by T12's codes.
- Fixture: Daniel's six rows (`fixtures/seed/home.ts`), office-filtered.
- Tests: `HOME-01.test.tsx` (a's six rows in order, office-denver, d empty).
- Rollback: revert; the field is optional and ignored by older clients.

## Progress log
- 2026-10-28: built; DEC-1001. eslint and tsc clean; Vitest runs at the batch's end review.
  Follow-up for I-01-T12's owner: fill `labels` on the live read.
