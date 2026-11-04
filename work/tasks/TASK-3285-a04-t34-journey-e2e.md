---
id: TASK-3285
title: A-04-T34 journey E2E for J03 planning steps 8 to 10b
spec: SPEC-000  # row (SPEC-620 AC4, AC6, AC7)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-04
plan_key: A-04-T34
branch: s27-a04-t34
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
J03 planning steps with assertInvariants and axeStep on every step; fixme naming the epic for steps
not yet live.

## Built
- `apps/web/e2e/journeys/J03-ebp-audit.spec.ts`: "J03 planning (A-04-T34)": j03 9 (AUD-08 d, EP
  approved), j03 10a (AUD-09 d, the IC pack failure and Retry), j03 10a2 (AUD-09 b, D2's
  citations) in fixture mode; j03 8 (AUD-07, no route), 8b (AUD-05 adopt, P-10 run) and 10b
  (AUD-10, A-04-T37) fixme with their owners.
- `apps/web/src/fixtures/screen-scenarios.ts`: AUD-08 and AUD-09 registered on Northwind's audit.

## Progress log
- 2026-11-04: written; tsc and eslint clean; run at the end pass. Partial: j04 steps 4 to 6 and
  j23 step 2 full-stack wait for AUD-04/05's Granite Peak scenarios and the staging stack.
