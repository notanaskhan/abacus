---
id: TASK-3273
title: A-04-T32 AUD-09 internal control and exceptions screen
spec: SPEC-000  # row (SPEC-620 AC6)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-04
plan_key: A-04-T32
branch: s27-a04-t32
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"AUD-09 a-e render live at Tier C and f from fixtures until A-06 registers, the failed state quotes
the run error verbatim, and no control sets a concluded severity."

## Built
- `apps/web/src/screens/AUD-09/` (`Controls.tsx`, `copy.ts`, `index.tsx`, `scenarios.ts`, test):
  the Internal Control row's canvas in the AUD-02 cockpit. Exceptions sheet with letters B–E,
  header row 1, data rows 2–8 from `GET …/internal-control/exceptions`; severity pills (AU-C 265
  words or "Exception for resolution", COSO in column E); the cell footer with its citations
  (`GET /v1/citations/{id}`); the O1 picker (`PATCH …/proposed-severity`, proposal only); the row
  menu (Send to Findings, Convert to misstatement on a misstatement candidate, Request evidence…);
  the Internal Control tab over `GET …/processes` (a SOC 1 row reads "<name> SOC 1" from
  `GET …/service-organizations`); the failed state (rail row `failed`: header only, "No evidence
  written.", the dock card quoting the failed run's `state_reason` verbatim with Retry →
  `POST …/workpapers/{id}/drafts {mode: ic}`).
- AUD-02 renders it for `?section=internal_control`; route `/audits/$auditId/controls`
  (`?sheet=internal-control`, `?cell=D2`); manifest path set (status stays planned until T38's parity).
- Fixtures: `fixtures/seed/aud09.ts`, `fixtures/scenarios/AUD-09.ts` (a–f, off, not_allowed).

## Progress log
- 2026-11-04: built; tsc and eslint clean on the new files. Tests written, run at the end pass.
- Found in passing (end pass): `domain/audits/completion-contract.test.ts:104` type comparison
  (A-07-T06) and `packages/ui/src/status.ts` missing disc `check` (A-07-T03 vocabulary).

## Decisions made during this task
DEC-2253.
