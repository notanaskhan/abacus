---
id: TASK-6829
title: "A-07-T53 gaps: DV-2 Locked · sealed, DV-4 Request EQR…, DV-6 required-sent counts; DV-3, DV-8 and the help store recorded"
spec: SPEC-644
acceptance_criteria: [AC-1]
risk_zone: green
status: in-progress
branch: s36f-a07-t53
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-12
updated: 2026-11-12
plan_key: A-07-T53
---

## Objective
Close the deviations TASK-6821 left open where the data exists; record the rest with owners.

## Built
- DV-2: `AUD-25/copy.ts` reads "Locked · sealed". Its unit test, `a07-independent.ac.test.tsx`, and
  the j03 19 and j18 6 journeys assert it.
- DV-4: `AUD-23/LiveReport.tsx` shows "Request EQR…" (`POST /v1/audits/{id}/eqr/request`).
- DV-6: `AUD-24/IssuanceLive.tsx` and `AUD-25/ArchiveLive.tsx` show "Governance Communications ·
  n of m required sent" through `governanceWords` (domain/completion-live). The hosts read
  `governanceListOptions`.
- Screen contracts AUD-18, 22, 23, 24 and 25 were updated; DEC-3420.

## Partial / flagged
- DV-3 is open: there is no workpaper link on the EQR checklist items.
- DV-8 is partly applied: there is no generated-document download route, and the AUD-28 and
  AUD-30 chips wait on Q-05.
- The help store is G-04's (G-04-T04/T10/T19/T20, S47–S50). The guide stays an import source.

## Progress log
- `2026-11-12` — Built. vitest for AUD-23/24/25, a07-independent and TAX-04 live: 129 passed.
