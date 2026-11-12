---
id: TASK-7630
title: F-07-T10 T13 CalendarLayout and MonthGrid
plan_key: F-07-T10
spec: SPEC-652
acceptance_criteria: [AC-6]  # T13a Tier D geometry; role=grid navigation
risk_zone: green
status: in-review
branch: f07-t10-calendar-month
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The T13 calendar kit's month: subbar, Sunday-start grid, firm-local today, out-of-month and
holiday labels, DueChip risk variants with done and postponed, "+n more" with computed fit and the
day popover; keyboard grid navigation.

## Plan
- `packages/ui/src/templates/calendar/{types.ts,dates.ts,due-chip.tsx,month-grid.tsx,
  calendar-layout.tsx,index.ts,calendar.test.tsx}`; exported from `packages/ui/src/index.ts`.
- DECISIONS.md conflict-log row; DEC-4625.

## Partial
- Tier D's measured parity run (Playwright `e2e/visual`) is the end pass's; geometry constants are
  asserted in the unit test. The Export control raises an intent (CSV/ICS menu is §11 Q2).
- The 10 px done check draws at 12 px (icon registry floor).

## Progress log
- `2026-11-12` — Kit built (DEC-4625). Tests at the end pass.
