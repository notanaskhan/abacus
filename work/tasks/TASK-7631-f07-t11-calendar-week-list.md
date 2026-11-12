---
id: TASK-7631
title: F-07-T11 T13 Week and List views and the RulePopover
plan_key: F-07-T11
spec: SPEC-652
acceptance_criteria: [F2, F3]  # T13b–d render; popover after 250 ms hover and on focus; risk in words
risk_zone: green
status: in-review
branch: f07-t11-calendar-week-list
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
Week view, List view on IndexList with the Rule column, the RulePopover with hover intent and
focus, and the filtered-empty state.

## Plan
- `packages/ui/src/templates/calendar/{rule-popover.tsx,week-list.tsx,week-list.test.tsx}`;
  `types.ts` (chip stage, initials, team, blockers, title; `CalendarListCopy`); DueChip and
  MonthGrid/CalendarLayout gain `onFocusChip`; exports in `calendar/index.ts`.

## Partial
- The popover's positioning against its anchor is the host's (the kit returns the anchor);
  TPL-13's specimen wiring and fixtures are F-07-T12 (S41).

## Progress log
- `2026-11-12` — Views and popover built (DEC-4626). Tests at the end pass.
