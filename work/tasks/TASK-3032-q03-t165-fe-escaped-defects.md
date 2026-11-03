---
id: TASK-3032
title: Q-03-T165 front-end escaped-defect fix-forward, 2027 Q3 part 4
spec: SPEC-000  # row
acceptance_criteria: [AC-1]  # every escaped UI defect of the period has a fix and a test, logged with the layer that missed it
risk_zone: green
status: in-review
epic: Q-03
plan_key: Q-03-T165
branch: s25-q03-t165
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"Every escaped UI defect of the period has a fix and a test, logged with the layer that missed it."
The period's UI defects were fixed on main by #1106 (DEC-2078); this row adds the screen-state
tests the journeys alone held, and logs each.

## Plan (green)
- `KNW-02.review.test.tsx`: the standards `<dl>` holds only `<dt>`/`<dd>` groups (ED-317).
- `packages/ui/src/layout/shell.test.tsx`: the firm menu is named with no firm (ED-320).
- `docs/quality/escaped-defects.md`: ED-317 to ED-321. ED-318 and ED-319 keep their journeys as
  the test: both live in the gallery artboards, which no unit test renders.
- Rollback: revert. Tests and docs only.

## Progress log
- 2026-11-03: built. UI layout 58 passed; KNW-02 15 passed.

## Decisions made during this task
None (the fixes are DEC-2078's).
