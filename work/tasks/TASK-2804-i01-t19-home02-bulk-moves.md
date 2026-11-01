---
id: TASK-2804
title: I-01-T19 bulk sign-off, reassign and snooze in HOME-02
spec: SPEC-000  # I-01-T19 row and docs/screens/HOME-02.md
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: I-01
plan_key: I-01-T19
branch: s23-i01-t19 (stacked on s23-i01-t20)
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "Scenario e signs 4 sections through SHL-12 f with per-item results, a snoozed gate
  leaves the queue and every badge, and reassign lists only eligible people."

## Plan (amber)
- Files: HOME-02 `index.tsx` (Select mode, bulk bar, SHL-12 f), `Detail.tsx` (Reassign… and
  Snooze until… menus, never optimistic), `copy.ts`; kit `IssueItem.check` (additive) and
  `format.ts` `hourIn`/`zonedInstant`; review `ReassignCandidateOut.display_name` (additive, names
  via `identity.names_of`), `make generate`; fixtures for snooze, reassign, candidates, bulk.
- No migration, matrix, flag or registry edit.
- Tests: I-01-T20's `__ac__/home02.ac.test.tsx` sections 3–4 (unedited), run at the end review.
- Rollback: revert; `home.approvals` stays the gate.

## Progress log
- `2026-11-01` — built; tsc (whole web), eslint and prettier clean. Tests at the S23 end review.

## Decisions made during this task
DEC-1853.
