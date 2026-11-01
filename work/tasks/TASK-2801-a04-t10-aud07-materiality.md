---
id: TASK-2801
title: A-04-T10 AUD-07 Materiality on T2 with dock
spec: SPEC-620
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-04
plan_key: A-04-T10
branch: s23-a04-t10
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "AUD-07 a-e render from fixtures at Tier C, Hannah's radios are disabled under the
  banner, and no threshold is computed in the browser."

## Plan
1. Tests first: `apps/web/src/screens/AUD-07/AUD-07.test.tsx` (a–e, slider via preview, Decide,
   dock, C-20 states).
2. Fixtures `seed/aud07.ts` + `scenarios/AUD-07.ts`; canvas hook in `screens/AUD-07/Materiality.tsx`
   wired into AUD-02's cockpit for `?section=materiality`; gallery and manifest (fixture).
3. Additive contract fields on the A-04-T01 stub (period end, caption, specific note, prior-year
   rate), `make generate`.
Rollback: revert; the flag stays off.

## Progress log
- `2026-11-01` — built; prettier, eslint and tsc clean on touched files. Tests written, run at the
  S23 end review; e2e parity (Tier C) is A-04-T40's lock, not run here.

## Decisions made during this task
DEC-1851.
