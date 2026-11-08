---
id: TASK-6114
title: "A-05-T52 EBP-08 Participant accounts summary, a to e on fixtures, in the AUD-02 cockpit"
spec: SPEC-000  # row (A-05-T52)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-05
plan_key: A-05-T52
branch: s30-a05-t52
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
The handoff's EBP-08 (T6 statement grammar inside the T2 cockpit): Rollforward, BrokerWindow and Vesting tabs, tally strip, statement with group rows and totals, running skeleton and pill, signed-off state.

## Plan
- `apps/web/src/screens/EBP-08/`: `copy.ts` (verbatim handoff copy), `Accounts.tsx` (`useAccountsCanvas`, `PARTICIPANT_ACCOUNTS = ebp_08`), `index.tsx`, `scenarios.ts`, `EBP-08.test.tsx`.
- Fixtures: `fixtures/seed/ebp08.ts` (A-05-T46's shapes, the spec's figures), `fixtures/scenarios/EBP-08.ts` (a to e, off).
- `screens/AUD-02/index.tsx`: Testing › Participant Accounts composes the canvas; manifest note.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). tsc shows no errors in the new files (the generated client's existing errors are unrelated); eslint and prettier clean.

## Decisions made during this task
None.
